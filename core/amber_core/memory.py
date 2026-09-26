"""四层记忆存储：raw → episodic → semantic → core。

隔离纪律（继承 relationship-companion schema3）：
- 隔离双键 profile_id × owner 写在 SQL WHERE，跨角色/跨用户的行在查询层即不存在；
  不做"查全表再 Python 过滤"，不依赖 exclude_ids。
- CHECK 约束层 + 复合索引；写坏数据在数据库层被拒。
- 拟人遗忘：episodic 按半衰期衰减（MemoryBank），低于阈值归档（不删，"降权不删"）；
  semantic 不衰减只降权；core 用户可编辑，不参与遗忘。
- 三因子召回（Generative Agents）：recency × relevance × importance；
  P0 relevance 用词法 Jaccard，嵌入相似度接口留给 provider 注入。
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .schema import MEMORY_LAYERS, MemoryRecord

SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT NOT NULL,
    owner TEXT NOT NULL,
    layer TEXT NOT NULL CHECK (layer IN ('raw','episodic','semantic','core')),
    content TEXT NOT NULL,
    importance REAL NOT NULL DEFAULT 5.0 CHECK (importance >= 0 AND importance <= 10),
    created_at TEXT NOT NULL,
    last_accessed TEXT NOT NULL,
    decay_score REAL NOT NULL DEFAULT 1.0,
    archived INTEGER NOT NULL DEFAULT 0,
    meta TEXT NOT NULL DEFAULT '{}',
    UNIQUE(profile_id, owner, layer, content)
);
CREATE INDEX IF NOT EXISTS idx_memory_scope ON memories(profile_id, owner, layer, archived);
"""

_HALF_LIFE_DAYS = {"raw": 30.0, "episodic": 14.0, "semantic": 3650.0, "core": 3650.0}
_ARCHIVE_BELOW = 0.05


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class MemoryStore:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    # ---------- 写入 ----------

    def add(
        self,
        profile_id: str,
        owner: str,
        layer: str,
        content: str,
        importance: float = 5.0,
        meta: dict | None = None,
        now: str | None = None,
    ) -> int:
        if layer not in MEMORY_LAYERS:
            raise ValueError(f"layer must be one of {MEMORY_LAYERS}")
        if not content.strip():
            raise ValueError("content must be non-empty")
        if not profile_id.strip() or not owner.strip():
            raise ValueError("profile_id/owner must be non-empty")
        ts = now or _utcnow()
        meta_json = json.dumps(meta or {}, ensure_ascii=False)
        cur = self.conn.execute(
            "INSERT INTO memories (profile_id, owner, layer, content, importance, created_at, last_accessed, meta)"
            " VALUES (?,?,?,?,?,?,?,?)"
            " ON CONFLICT(profile_id, owner, layer, content) DO UPDATE SET last_accessed=excluded.last_accessed",
            (profile_id.strip(), owner.strip(), layer, content.strip(), float(importance), ts, ts, meta_json),
        )
        self.conn.commit()
        return int(cur.lastrowid or 0)

    def edit(self, profile_id: str, owner: str, memory_id: int, new_content: str) -> None:
        """用户编辑（core 层承诺：可查看、可修正）。越界 id 不存在即抛错，不静默。"""
        cur = self.conn.execute(
            "UPDATE memories SET content=? WHERE id=? AND profile_id=? AND owner=?",
            (new_content.strip(), memory_id, profile_id, owner),
        )
        self.conn.commit()
        if cur.rowcount == 0:
            raise LookupError(f"memory {memory_id} not found in scope")

    def delete(self, profile_id: str, owner: str, memory_id: int) -> None:
        cur = self.conn.execute(
            "DELETE FROM memories WHERE id=? AND profile_id=? AND owner=?",
            (memory_id, profile_id, owner),
        )
        self.conn.commit()
        if cur.rowcount == 0:
            raise LookupError(f"memory {memory_id} not found in scope")

    # ---------- 遗忘 ----------

    def apply_decay(self, now: str | None = None) -> int:
        """全库衰减（桌面端定期调用）：decay = 0.5 ** (Δdays / half_life)。低于阈值且非 core 的 episodic/raw 归档。"""
        ts = now or _utcnow()
        rows = self.conn.execute(
            "SELECT id, profile_id, owner, layer, last_accessed, decay_score, archived FROM memories WHERE archived=0"
        ).fetchall()
        archived = 0
        for row in rows:
            last = _parse_dt(row["last_accessed"])
            delta_days = max((_parse_dt(ts) - last).total_seconds() / 86400, 0.0) if last else 0.0
            decay = (row["decay_score"] or 1.0) * (0.5 ** (delta_days / _HALF_LIFE_DAYS[row["layer"]]))
            flag = 1 if (decay < _ARCHIVE_BELOW and row["layer"] in ("raw", "episodic")) else 0
            archived += flag
            self.conn.execute(
                "UPDATE memories SET decay_score=?, archived=? WHERE id=?",
                (decay, flag, row["id"]),
            )
        self.conn.commit()
        return archived

    # ---------- 召回 ----------

    def recall(
        self,
        profile_id: str,
        owner: str,
        query: str,
        top_k: int = 5,
        layers: tuple[str, ...] | None = None,
        now: str | None = None,
        relevance_fn=None,
    ) -> list[MemoryRecord]:
        """三因子召回。隔离：WHERE 双键；archived 默认排除。

        relevance_fn(query, content) -> [0,1]：可注入嵌入相似度；缺省词法 Jaccard。
        """
        ts = now or _utcnow()
        layer_filter = ""
        params: list = [profile_id, owner]
        if layers:
            layer_filter = f" AND layer IN ({','.join('?' for _ in layers)})"
            params += list(layers)
        rows = self.conn.execute(
            "SELECT * FROM memories WHERE profile_id=? AND owner=?" + layer_filter + " AND archived=0",
            params,
        ).fetchall()
        scored = []
        for row in rows:
            rec = _to_record(row)
            delta_days = 0.0
            last = _parse_dt(rec.last_accessed)
            if last:
                delta_days = max((_parse_dt(ts) - last).total_seconds() / 86400, 0.0)
            rec.decay_score = rec.decay_score * (0.5 ** (delta_days / _HALF_LIFE_DAYS[rec.layer]))
            recency = max(rec.decay_score, 0.01)
            rel = relevance_fn(query, rec.content) if relevance_fn else _jaccard(query, rec.content)
            if rel <= 0.0:
                continue  # 零相关不召回（宁缺勿滥）
            importance = max(rec.importance, 0.1) / 10.0
            scored.append((recency * rel * importance, rec))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        top = [rec for _, rec in scored[:top_k]]
        if top:
            ids_sql = ",".join("?" for _ in top)
            self.conn.execute(
                f"UPDATE memories SET last_accessed=? WHERE id IN ({ids_sql})",
                [ts, *(r.id for r in top)],
            )
            self.conn.commit()
        return top

    def count(self, profile_id: str | None = None, owner: str | None = None) -> int:
        """计数（可选过滤单维度，用于体检；绝不两键皆空做全库查询）。"""
        where, params = [], []
        if profile_id:
            where.append("profile_id=?")
            params.append(profile_id)
        if owner:
            where.append("owner=?")
            params.append(owner)
        if not where:
            raise ValueError("count 需要 profile_id 或 owner 至少一个（防全库裸查）")
        row = self.conn.execute(f"SELECT COUNT(*) AS n FROM memories WHERE {' AND '.join(where)}", params).fetchone()
        return int(row["n"])


def _parse_dt(s: str) -> datetime | None:
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _to_record(row: sqlite3.Row) -> MemoryRecord:
    return MemoryRecord(
        id=row["id"],
        profile_id=row["profile_id"],
        owner=row["owner"],
        layer=row["layer"],
        content=row["content"],
        importance=row["importance"],
        created_at=row["created_at"],
        last_accessed=row["last_accessed"],
        decay_score=row["decay_score"],
        archived=bool(row["archived"]),
        meta=json.loads(row["meta"] or "{}"),
    )


def _jaccard(query: str, content: str) -> float:
    """词法相关度兜底：字符 bigram Jaccard。"""
    def grams(s: str) -> set[str]:
        s = "".join(ch for ch in s if not ch.isspace())
        return {s[i : i + 2] for i in range(max(len(s) - 1, 0))} or {s}

    q, c = grams(query), grams(content)
    if not q or not c:
        return 0.0
    return len(q & c) / len(q | c)
