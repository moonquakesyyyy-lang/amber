"""审查整改验收测试（P1-1/P1-2/Q-5/Q-6/Q-7 Python 侧）。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from amber_core.importer import inspect_file, sniff_format
from amber_core.novel import chunk_novel
from amber_core.providers import FakeLLMClient
from tools.distill_novel import distill_novel

CHAT_JSONL = "\n".join([
    json.dumps({"ts": "2026-01-01T10:00:00", "sender_name": "小夏", "content": "早上好呀"}, ensure_ascii=False),
    json.dumps({"ts": "2026-01-01T10:01:00", "sender_name": "小夏", "content": "今天天气不错"}, ensure_ascii=False),
    json.dumps({"ts": "2026-01-01T10:02:00", "sender_name": "我", "content": "是啊"}, ensure_ascii=False),
    json.dumps({"ts": "2026-01-01T10:03:00", "sender_name": "我", "content": "中午吃什么"}, ensure_ascii=False),
])
NOVEL_TXT = "第一章 入山\n\n沈青临背着旧剑走进山门。\n\n第二章 试剑\n\n苏晚晴微笑着出招。"


def _write(tmp_path, name, content):
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


# ---------- P1-1：格式预检 ----------

def test_sniff_format_chat_and_novel(tmp_path):
    p = _write(tmp_path, "chat.jsonl", CHAT_JSONL)
    assert sniff_format(p) == "chat"
    p2 = _write(tmp_path, "book.txt", NOVEL_TXT)
    assert sniff_format(p2) == "novel"


def test_sniff_format_unsupported_clear_error(tmp_path):
    p = _write(tmp_path, "file.docx", "binary-ish")
    with pytest.raises(ValueError, match="不支持的文件格式"):
        sniff_format(p)
    p2 = _write(tmp_path, "noext", "x")
    with pytest.raises(ValueError, match="无扩展名"):
        sniff_format(p2)


# ---------- Q-7：inspect_file 说话人检视 ----------

def test_inspect_file_senders_and_samples(tmp_path):
    p = _write(tmp_path, "chat.jsonl", CHAT_JSONL)
    info = inspect_file(p)
    assert info["total"] == 4
    names = [s["name"] for s in info["senders"]]
    assert set(names) == {"小夏", "我"}
    top = info["senders"][0]
    assert top["name"] == "小夏" and top["count"] == 2
    assert any("早上好" in s for s in top["samples"])


# ---------- P1-2：全部失败不产产物 / 部分失败带缺失 ----------

def _novel_blocks():
    return chunk_novel(NOVEL_TXT + "\n" + NOVEL_TXT, chunk_chars=200)


def test_all_blocks_failed_raises(tmp_path):
    text = NOVEL_TXT + "\n" + NOVEL_TXT
    llm = FakeLLMClient(["不是JSON"] * 10)  # 每块两次尝试全部失败
    with pytest.raises(RuntimeError, match="均蒸馏失败"):
        distill_novel(text, "测试书", llm, max_blocks=2, chunk_chars=200)


def test_partial_failure_reports_missing(tmp_path):
    text = NOVEL_TXT + "\n" + NOVEL_TXT
    # 块1 成功、块2 两次失败 → 部分失败
    llm = FakeLLMClient([
        json.dumps({"characters": [{"name": "沈青临", "identity": "剑修", "traits": ["勇"],
                                    "speaking_style": "", "relationships": ""}],
                    "lore_candidates": [], "memories": [], "evidence": []}, ensure_ascii=False),
        "坏输出", "坏输出",
    ])
    result = distill_novel(text, "测试书", llm, max_blocks=2, chunk_chars=200)
    assert result["report"]["blocks_done"] == 1
    assert result["report"]["blocks_failed"] == 1
    assert result["report"]["blocks_processed"] == 2
    assert len(result["report"]["failed_block_ids"]) == 1


# ---------- Q-4（数据结构层）：世界书独立、卡不内嵌 ----------

def test_worldbook_separate_from_cards(tmp_path):
    text = NOVEL_TXT + "\n" + NOVEL_TXT
    llm = FakeLLMClient([
        json.dumps({"characters": [{"name": "沈青临", "identity": "剑修", "traits": ["勇"],
                                    "speaking_style": "", "relationships": ""}],
                    "lore_candidates": [{"title": "青云宗", "content": "宗门", "keys": "青云宗"}],
                    "memories": ["入山"], "evidence": []}, ensure_ascii=False),
        json.dumps({"characters": [{"name": "苏晚晴", "identity": "宗主独女",
                                    "traits": ["温软"], "speaking_style": "", "relationships": ""}],
                    "lore_candidates": [], "memories": ["试剑"], "evidence": []}, ensure_ascii=False),
    ])
    result = distill_novel(text, "测试书", llm, max_blocks=2, chunk_chars=200)
    assert result["worldbook"]["entries"], "世界书应独立存在"
    for card in result["cards"]:
        # Q-4：卡不内嵌世界书（由 App 导入时统一绑定，避免重复创建）
        assert card["data"]["character_book"]["entries"] == []
