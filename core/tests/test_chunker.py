"""分块器测试：条数切分 / 时间断档 / 边界。"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from amber_core.chunker import chunk_messages
from amber_core.schema import Message


def _msgs(n: int, start: datetime, step_min: int = 1) -> list[Message]:
    return [
        Message(
            ts=(start + timedelta(minutes=i * step_min)).isoformat(),
            sender_id="s", sender_name="小夏", direction="self", content=f"m{i}",
        )
        for i in range(n)
    ]


def test_size_split():
    blocks = chunk_messages(_msgs(250, datetime(2026, 1, 1)), block_size=100)
    assert [len(b.messages) for b in blocks] == [100, 100, 50]
    assert [b.block_id for b in blocks] == [0, 1, 2]
    assert blocks[0].start_ts < blocks[0].end_ts


def test_gap_split():
    msgs = _msgs(3, datetime(2026, 1, 1), step_min=1)
    later = _msgs(2, datetime(2026, 1, 1, 12, 0))  # 距上条 > 6h
    blocks = chunk_messages(msgs + later, block_size=100, gap_hours=6)
    assert len(blocks) == 2
    assert len(blocks[0].messages) == 3 and len(blocks[1].messages) == 2


def test_edges():
    assert chunk_messages([]) == []
    one = chunk_messages(_msgs(1, datetime(2026, 1, 1)))
    assert len(one) == 1 and one[0].block_id == 0

    import pytest
    with pytest.raises(ValueError):
        chunk_messages(_msgs(2, datetime(2026, 1, 1)), block_size=0)
