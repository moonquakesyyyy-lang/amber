"""聊天记录导入适配器。

只读"用户自备的明文导出产物"，不做任何解密（隐私与合规红线，见调研文档 §1.3）。
支持：Telegram 官方 JSON（黄金标准）、通用 JSONL（统一 schema 直读）、
通用 CSV、MemoTrace（留痕）JSON 尽力适配。未知格式给出可诊断错误。
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .schema import DIRECTION_OTHER, DIRECTION_SELF, Message

SUPPORTED_SOURCES = ("telegram", "generic_jsonl", "generic_csv", "memotrace", "auto")


class ImportError_(ValueError):
    """导入失败（格式不识别/缺关键列），message 应可指导用户换导出格式。"""


def _norm_sender(sender: str, self_names: set[str]) -> str:
    return DIRECTION_SELF if sender.strip() in self_names else DIRECTION_OTHER


def _entity_text(text: object) -> str:
    """Telegram text 字段兼容：字符串或 [{type,_text|text}] 实体数组。"""
    if isinstance(text, str):
        return text
    if isinstance(text, list):
        parts = []
        for item in text:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(str(item.get("_text") or item.get("text") or ""))
        return "".join(parts)
    return ""


def import_telegram(path: Path, self_names: set[str]) -> list[Message]:
    """Telegram Desktop 官方导出 result.json（machine-readable）。"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    out: list[Message] = []
    for i, m in enumerate(data.get("messages", [])):
        if not isinstance(m, dict) or m.get("type") != "message":
            continue
        content = _entity_text(m.get("text"))
        if not content.strip():
            continue
        sender = str(m.get("from") or m.get("actor") or "unknown")
        out.append(
            Message(
                ts=str(m.get("date_unixtime") or m.get("date") or i),
                sender_id=str(m.get("from_id") or sender),
                sender_name=sender,
                direction=_norm_sender(sender, self_names),
                content=content,
                source="telegram",
            )
        )
    return out


def import_generic_jsonl(path: Path, self_names: set[str]) -> list[Message]:
    """统一 schema JSONL：每行 {ts,sender_name,content[,sender_id,direction,type,source]}。

    坏行跳过不中断（宽容导入：长记录单行损坏不应阻塞整体，Telegram 官方导出亦有非法 JSON 坑）。
    """
    out: list[Message] = []
    for line_no, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue  # 坏行跳过；行号与总数不匹配即为诊断线索
        if not isinstance(row, dict):
            continue
        content = str(row.get("content") or "")
        if not content.strip():
            continue
        sender = str(row.get("sender_name") or row.get("sender") or "unknown")
        direction = row.get("direction")
        if direction not in (DIRECTION_SELF, DIRECTION_OTHER):
            direction = _norm_sender(sender, self_names)
        out.append(
            Message(
                ts=str(row.get("ts") or line_no),
                sender_id=str(row.get("sender_id") or sender),
                sender_name=sender,
                direction=direction,
                content=content,
                type=str(row.get("type") or "text"),
                source=str(row.get("source") or "generic"),
            )
        )
    return out


def import_generic_csv(path: Path, self_names: set[str]) -> list[Message]:
    """通用 CSV：必需列 sender,content；可选 ts,type。"""
    out: list[Message] = []
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        cols = set(reader.fieldnames or [])
        if not {"sender", "content"} <= cols:
            raise ImportError_(f"CSV 缺必需列 sender/content，实际列：{sorted(cols)}")
        for i, row in enumerate(reader, 1):
            content = str(row.get("content") or "")
            if not content.strip():
                continue
            sender = str(row.get("sender") or "unknown")
            out.append(
                Message(
                    ts=str(row.get("ts") or i),
                    sender_id=sender,
                    sender_name=sender,
                    direction=_norm_sender(sender, self_names),
                    content=content,
                    type=str(row.get("type") or "text"),
                    source="generic",
                )
            )
    return out


def import_memotrace(path: Path, self_names: set[str]) -> list[Message]:
    """MemoTrace（留痕）导出 JSON 尽力适配：字段名随版本漂移，做归一化容错。

    约定优先读取：sender/talker/is_sender 与 content/message、ts/timestamp/create_time。
    is_sender 存在时优先于名字判定方向（1=本人）。
    """
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    items = raw if isinstance(raw, list) else raw.get("messages") or raw.get("data") or []
    if not isinstance(items, list):
        raise ImportError_("MemoTrace JSON 顶层应为数组或含 messages/data 数组")
    out: list[Message] = []
    for i, m in enumerate(items):
        if not isinstance(m, dict):
            continue
        content = str(m.get("content") or m.get("message") or m.get("msg") or "")
        if not content.strip():
            continue
        sender = str(m.get("sender") or m.get("talker") or m.get("sender_name") or "unknown")
        if "is_sender" in m:
            direction = DIRECTION_SELF if str(m["is_sender"]) in ("1", "true", "True") else DIRECTION_OTHER
        else:
            direction = _norm_sender(sender, self_names)
        ts = m.get("ts") or m.get("timestamp") or m.get("create_time") or m.get("StrTime") or i
        mtype = str(m.get("type") or "text")
        if mtype.isdigit():
            mtype = "text" if mtype == "1" else "media"
        out.append(
            Message(
                ts=str(ts), sender_id=sender, sender_name=sender,
                direction=direction, content=content, type=mtype, source="memotrace",
            )
        )
    return out


def import_file(path: str | Path, source: str = "auto", self_names: set[str] | None = None) -> list[Message]:
    """入口：source=auto 时按扩展名+内容嗅探。self_names 用于方向判定（本人称谓，如昵称/备注名）。"""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    self_names = self_names or set()
    src = source
    if src == "auto":
        suffix = p.suffix.lower()
        try:
            head = p.read_text(encoding="utf-8", errors="ignore")[:2000]
        except OSError as e:
            raise ImportError_(f"无法读取文件：{e}") from e
        if suffix == ".jsonl":
            src = "generic_jsonl"
        elif suffix == ".csv":
            src = "generic_csv"
        elif suffix == ".json":
            src = "telegram" if '"messages"' in head and ('"type"' in head or '"from_id"' in head) else "memotrace"
        else:
            raise ImportError_(f"无法按扩展名识别格式（{suffix}），请显式指定 source={SUPPORTED_SOURCES}")
    impl = {
        "telegram": import_telegram,
        "generic_jsonl": import_generic_jsonl,
        "generic_csv": import_generic_csv,
        "memotrace": import_memotrace,
    }.get(src)
    if impl is None:
        raise ImportError_(f"未知 source={src!r}，支持：{SUPPORTED_SOURCES}")
    messages = impl(p, self_names)
    if not messages:
        raise ImportError_(f"导入结果为空（{p.name}, source={src}）：请检查导出格式与 self_names 设置")
    return messages
