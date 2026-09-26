"""蒸馏分块器：按条数 + 时间断档切分，保持上下文完整。"""

from __future__ import annotations

from datetime import datetime, timedelta

from .schema import Block, Message


def _parse_ts(ts: str) -> datetime | None:
    """尽力解析 ISO8601 / 纯数字时间戳（秒），失败返回 None（不影响分块，只影响断档）。"""
    ts = ts.strip()
    if ts.isdigit():
        return datetime.fromtimestamp(int(ts))
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def chunk_messages(messages: list[Message], block_size: int = 100, gap_hours: float = 6.0) -> list[Block]:
    """切分规则：满 block_size 条强制切块；相邻消息间隔 > gap_hours 提前切块。

    非文本消息（图片/语音）计入条数但不作为断档判断依据的时间点同样有效。
    """
    if block_size < 1:
        raise ValueError("block_size must be >= 1")
    if not messages:
        return []
    ordered = sorted(messages, key=lambda m: m.ts)
    gap = timedelta(hours=gap_hours)
    blocks: list[Block] = []
    current: list[Message] = []
    prev_dt: datetime | None = None

    def flush() -> None:
        if current:
            blocks.append(
                Block(
                    block_id=len(blocks),
                    messages=list(current),
                    start_ts=current[0].ts,
                    end_ts=current[-1].ts,
                )
            )
            current.clear()

    for m in ordered:
        dt = _parse_ts(m.ts)
        if current and (
            len(current) >= block_size or (prev_dt and dt and (dt - prev_dt) > gap)
        ):
            flush()
        current.append(m)
        if dt:
            prev_dt = dt
    flush()
    return blocks
