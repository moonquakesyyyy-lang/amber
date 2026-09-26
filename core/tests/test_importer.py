"""导入适配器测试：TG JSON / JSONL / CSV / MemoTrace 容错 / 方向判定 / 错误可诊断。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from amber_core.importer import ImportError_, import_file
from amber_core.schema import DIRECTION_SELF


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def test_telegram_json_with_entity_array(tmp_path):
    data = {
        "messages": [
            {"type": "service", "actor": "服务号"},
            {"type": "message", "id": 1, "date_unixtime": "1700000000", "from": "小夏", "from_id": "user1",
             "text": [{"type": "plain", "text": "早"}, "安呀"]},
            {"type": "message", "id": 2, "date_unixtime": "1700000100", "from": "我", "from_id": "user2",
             "text": "早安！"},
            {"type": "message", "id": 3, "date_unixtime": "1700000200", "from": "小夏", "from_id": "user1",
             "text": ""},
        ]
    }
    p = _write(tmp_path, "result.json", json.dumps(data, ensure_ascii=False))
    msgs = import_file(p, source="telegram", self_names={"我"})
    assert len(msgs) == 2  # service/空文本剔除
    assert msgs[0].direction == DIRECTION_SELF or msgs[0].direction == "other"
    assert any(m.content == "早安呀" or m.content == "早安" for m in msgs)
    assert msgs[-1].content == "早安！"


def test_generic_jsonl_and_csv(tmp_path):
    row1 = json.dumps({"ts": "2026-01-01T10:00:00", "sender_name": "小夏", "content": "今天好累"}, ensure_ascii=False)
    row2 = json.dumps(
        {"ts": "2026-01-01T10:01:00", "sender_name": "我", "content": "抱抱", "direction": "other"},
        ensure_ascii=False,
    )
    p1 = _write(tmp_path, "a.jsonl", "\n".join([row1, row2, "", "{bad json"]))
    msgs = import_file(p1, source="generic_jsonl", self_names={"小夏"})
    assert [m.content for m in msgs] == ["今天好累", "抱抱"]
    assert msgs[0].direction == DIRECTION_SELF
    assert msgs[1].direction == "other"  # 显式 direction 优先于名字判定

    p2 = _write(tmp_path, "b.csv", "sender,content,ts\n小夏,今晚吃什么,2026-01-02\n我,火锅,2026-01-02\n")
    msgs2 = import_file(p2, source="generic_csv", self_names={"小夏"})
    assert [m.direction for m in msgs2] == [DIRECTION_SELF, "other"]


def test_memotrace_adapter_and_is_sender_priority(tmp_path):
    data = [
        {"type": "1", "content": "在吗", "talker": "小夏", "StrTime": "2026-01-03 10:00:00", "is_sender": 0},
        {"type": "1", "content": "在的", "talker": "我", "StrTime": "2026-01-03 10:00:05", "is_sender": 1},
        {"type": "3", "content": "[图片]", "talker": "小夏", "is_sender": 0},
    ]
    p = _write(tmp_path, "mt.json", json.dumps(data, ensure_ascii=False))
    msgs = import_file(p, source="memotrace", self_names=set())  # 不给名字也能靠 is_sender 判向
    assert [m.direction for m in msgs] == ["other", DIRECTION_SELF, "other"]
    assert msgs[2].type == "media"


def test_auto_sniff_and_errors(tmp_path):
    p = _write(tmp_path, "result.json", json.dumps({
        "messages": [{"type": "message", "date_unixtime": "1", "from": "A", "text": "hi"}]}, ensure_ascii=False))
    assert import_file(p, source="auto", self_names={"A"})[0].content == "hi"

    p_csv_bad = _write(tmp_path, "bad.csv", "foo,bar\n1,2\n")
    with pytest.raises(ImportError_, match="sender/content"):
        import_file(p_csv_bad, source="generic_csv")

    with pytest.raises(FileNotFoundError):
        import_file(tmp_path / "missing.json")

    p_empty = _write(tmp_path, "empty.jsonl", "\n\n")
    with pytest.raises(ImportError_, match="导入结果为空"):
        import_file(p_empty, source="generic_jsonl")

    p_txt = _write(tmp_path, "x.txt", "文本格式未支持")
    with pytest.raises(ImportError_, match="显式指定"):
        import_file(p_txt, source="auto")
