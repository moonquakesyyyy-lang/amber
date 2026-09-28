"""从 AstrBot relationship-companion 迁移角色资产到琥珀。

用法（在能读到 AstrBot 数据库的机器上）：
    python tools/import_from_astrbot.py --db <relationship_companion.db> [--name 小美] --out-dir <输出目录>

读取：companions.profile_json（结构化画像）+ pe_lore（世界书）+ memories（关系记忆）。
产出：<角色名>-琥珀角色卡.json（SillyTavern chara_card_v3，可直接在琥珀 App「助手→导入」使用）。
隐私：一切在本机完成，产出文件是用户自己的数据，不经任何第三方。
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path


def _load_profile(conn: sqlite3.Connection, name: str | None) -> tuple[str, dict]:
    if name:
        row = conn.execute(
            "SELECT name, profile_json FROM companions WHERE name = ?", (name,)
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT name, profile_json FROM companions ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()
    if row is None:
        raise SystemExit(f"未找到角色（name={name}）；可用角色："
                         + ", ".join(r[0] for r in conn.execute("SELECT name FROM companions")))
    return row["name"], json.loads(row["profile_json"])


def _flatten(items: list) -> list[str]:
    """画像清单字段兼容：元素可能是 str 或 {content: str, ...}（本地蒸馏早期格式）。"""
    out = []
    for it in items or []:
        if isinstance(it, str) and it.strip():
            out.append(it.strip())
        elif isinstance(it, dict) and str(it.get("content") or "").strip():
            out.append(str(it["content"]).strip())
    return out


def _split_keys(title: str, evidence: str) -> list[str]:
    """世界书触发词：title 全词优先，evidence 撷取 2-6 字实词片段兜底。"""
    keys = [k for k in re.split(r"[\s，。！？、/·（）()]+", title.strip()) if 1 <= len(k) <= 12]
    if evidence:
        m = re.search(r"(?:她|他|用户)?[:：]\s*(.{2,12})", evidence)
        if m:
            frag = re.sub(r"[^\w\u4e00-\u9fff]", "", m.group(1))
            if 2 <= len(frag) <= 12 and frag not in keys:
                keys.append(frag)
    return keys[:4] or [title.strip()[:12]]


def convert(db_path: Path, name: str | None, out_dir: Path) -> Path:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    display_name, p = _load_profile(conn, name)

    traits = _flatten(p.get("personality", {}).get("traits", []))
    style = p.get("speaking_style", {})
    rel = p.get("relationship_style", {})
    nicknames = _flatten(p.get("user_addressing", {}).get("nicknames_for_user", []))
    likes = _flatten(p.get("preferences", {}).get("likes", []))
    dislikes = _flatten(p.get("preferences", {}).get("dislikes", []))
    shared = p.get("shared_memories", []) or []
    rules = p.get("behavior_rules", []) or []
    uncertain = _flatten(p.get("uncertainties", []))

    # 行为规则拆分：玩笑梗/重要规则 vs 边界（taboos）
    core_rules = [r for r in rules if not r.startswith("尊重她的边界")]
    boundaries = [r.replace("尊重她的边界：", "") for r in rules if r.startswith("尊重她的边界")]

    # ---- description（本体精简原则：导航信息，细节进世界书/extensions）----
    desc = [f"{display_name}——{p.get('identity', {}).get('relationship_to_user', '重要关系对象')}。"]
    if p.get("personality", {}).get("temperament"):
        desc.append(f"气质：{p['personality']['temperament']}。")
    if style.get("tone"):
        desc.append("说话风格：" + "；".join(style["tone"][:5]) + "。")
    if style.get("punctuation_style"):
        desc.append(f"标点习惯：{style['punctuation_style']}。")
    phrases = style.get("common_phrases", []) or []
    if phrases:
        desc.append("高频口头禅（务必自然穿插）：" + "、".join(phrases[:30]) + "。")
    if nicknames:
        desc.append("对用户的称呼：" + "、".join(nicknames[:10]) + "。")
    if likes:
        desc.append("喜欢：" + "、".join(likes[:15]) + "。")
    if dislikes:
        desc.append("讨厌：" + "、".join(dislikes[:15]) + "。")
    if core_rules:
        desc.append("重要行为准则：" + core_rules[0])

    persona_summary = "。".join([
        p.get("personality", {}).get("temperament", ""),
        rel.get("affection_style", "") and f"表达爱意：{rel['affection_style']}",
        rel.get("comfort_style", "") and f"安慰方式：{rel['comfort_style']}",
        rel.get("conflict_style", "") and f"冲突风格：{rel['conflict_style']}",
    ]).strip("。 ")

    # ---- 世界书：pe_lore 全量（关键词触发注入，不常驻不爆上下文）----
    persona_id = conn.execute(
        "SELECT persona_id FROM pe_lore LIMIT 1"
    ).fetchone()
    lore_rows = conn.execute(
        "SELECT category, title, content, payload FROM pe_lore WHERE enabled = 1 "
        "AND (:name IS NULL OR persona_id = :name) ORDER BY updated_at",
        {"name": (persona_id["persona_id"] if persona_id else None) if name is None else name},
    ).fetchall()
    # persona_id 不是角色名；直接全量取 enabled 的（单人库即该角色的）
    lore_rows = conn.execute(
        "SELECT category, title, content, payload FROM pe_lore WHERE enabled = 1 ORDER BY updated_at"
    ).fetchall()

    entries = []
    for i, r in enumerate(lore_rows):
        payload = {}
        try:
            payload = json.loads(r["payload"] or "{}")
        except json.JSONDecodeError:
            pass
        evidence = str(payload.get("evidence") or "")
        entries.append({
            "id": i,
            "keys": _split_keys(r["title"], evidence),
            "content": f"[{r['category']}] {r['title']}：{r['content']}" + (f"（原话：{evidence}）" if evidence else ""),
            "comment": r["title"],
            "enabled": True,
            "insertion_order": 100 + int(float(payload.get("importance", 0.5)) * 50),
            "constant": False,
            "position": "before_char",
            "extensions": {"category": r["category"]},
        })
    # 喜好/边界也进世界书（常驻级：preference 用 constant=False 同样触发式）
    for d in dislikes[:40]:
        entries.append({
            "id": len(entries), "keys": _split_keys(d, ""), "content": f"[TABOO] {display_name}讨厌/忌讳：{d}",
            "comment": f"忌讳-{d[:12]}", "enabled": True, "insertion_order": 150,
            "constant": False, "position": "before_char", "extensions": {"category": "TABOO"},
        })

    # ---- 关系记忆（memories 表）----
    mem_rows = conn.execute(
        "SELECT memory_type, content, importance FROM memories "
        "WHERE deleted_at IS NULL AND content NOT NULL AND TRIM(content) != '' ORDER BY importance DESC"
    ).fetchall()
    memories = [r["content"] for r in mem_rows] + [m.get("content", "") for m in shared if isinstance(m, dict)]
    memories = [m for m in memories if m and m.strip()]

    card = {
        "spec": "chara_card_v3",
        "spec_version": "3.0",
        "data": {
            "name": display_name,
            "description": "\n".join(desc),
            "personality": "、".join(traits[:20]),
            "scenario": "",
            "first_mes": f"在呀，我是{display_name}。",
            "mes_example": "",
            "creator_notes": "由琥珀（Amber）从 AstrBot relationship-companion 资产迁移生成；世界书按关键词触发注入。",
            "system_prompt": "",
            "post_history_instructions": "",
            "alternate_greetings": [],
            "character_book": {"entries": entries},
            "tags": ["amber", "astrbot-migration"],
            "extensions": {
                "amber": {
                    "version": 1,
                    "source": "astrbot-relationship-companion",
                    "persona_summary": persona_summary,
                    "traits": traits,
                    "behavior_rules": core_rules,
                    "taboos": boundaries,
                    "humor": [],
                    "scene_tone": {},
                    "memories": memories,
                    "uncertainties": uncertain,
                    "style_examples": [phrases[i] for i in range(min(len(phrases), 24))],
                    "evidence_stats": {"lore_entries": len(entries), "memories": len(memories)},
                }
            },
        },
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{display_name}-琥珀角色卡.json"
    out.write_text(json.dumps(card, ensure_ascii=False, indent=1), encoding="utf-8")
    conn.close()
    print(f"OK {out}  (世界书 {len(entries)} 条 / 记忆 {len(memories)} 条 / 特质 {len(traits)} 条)")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True, help="relationship_companion.db 路径")
    ap.add_argument("--name", default=None, help="角色名（缺省取最近更新的角色）")
    ap.add_argument("--out-dir", default=".", help="输出目录")
    a = ap.parse_args()
    convert(Path(a.db), a.name, Path(a.out_dir))


if __name__ == "__main__":
    main()
