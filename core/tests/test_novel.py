"""小说蒸馏测试：导入/分块/FakeLLM 端到端/人物拆分/证据核验/世界书构建。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from amber_core import novel
from amber_core.novel import chunk_novel, load_novel_text
from amber_core.providers import FakeLLMClient
from tools.distill_novel import _parse_block, distill_novel

SAMPLE = """第一章 入山

少年背着一把旧剑，走进云雾缭绕的山门。他叫沈青临，是山下沈家最后一个修士。
"师父说过，剑修一途，宁折不弯。"他低声念叨，像是在给自己打气。

守山的老道眯着眼打量他："小小年纪，一个人上山？"
沈青临拱手："回前辈，晚辈想拜入青云宗。"
老道笑了："青云宗可不好进，三年一考，十不存一。"

第二章 试剑

试剑台上，沈青临遇上了苏晚晴。她是宗主的独女，剑法凌厉，性情却是出名的温软。
"你出招吧，我让你三剑。"苏晚晴微笑着说。
沈青临摇头："剑修无让。"
这一句话让围观弟子哗然—— ten 年来没人敢对小姐说这种话。
"""


@pytest.fixture()
def novel_file(tmp_path):
    p = tmp_path / "sample.txt"
    p.write_text(SAMPLE, encoding="utf-8")
    return p


def test_load_and_chunk(novel_file):
    text = load_novel_text(novel_file)
    assert "沈青临" in text
    blocks = chunk_novel(text, chunk_chars=200)
    assert len(blocks) >= 2  # 章界强制切分
    # 章界起新块：第二章应在新块开头
    assert any("第二章" in b.messages[0].content for b in blocks)
    # 消息复用：sender=原文，direction=other
    assert all(m.sender_name == "原文" for b in blocks for m in b.messages)


def test_chunk_min_size_validation():
    with pytest.raises(ValueError):
        chunk_novel("短文本", chunk_chars=10)


def test_parse_block_evidence_verification():
    block = novel.chunk_novel(SAMPLE, chunk_chars=3000)[0]
    raw = {
        "characters": [
            {"name": "沈青临", "identity": "山下沈家最后一个修士", "traits": ["宁折不弯", "少年心气"],
             "speaking_style": "短句直白，剑修气概", "relationships": "苏晚晴：试剑台初遇"},
        ],
        "lore_candidates": [{"title": "青云宗", "content": "三年一考十不存一的宗门", "keys": "青云宗"}],
        "memories": ["沈青临独自入山拜师"],
        "evidence": [
            {"quote": "剑修一途，宁折不弯", "message_index": 1},
            {"quote": "我从不编造台词", "message_index": 0},  # 编造 → 丢
        ],
    }
    chars, lore, mems, quotes = _parse_block(raw, block)
    assert chars[0]["name"] == "沈青临" and len(chars[0]["traits"]) == 2
    assert lore[0]["keys"] == "青云宗"
    assert quotes == ["剑修一途，宁折不弯"]  # 编造证据被核验丢弃


def _fake_reply() -> str:
    return json.dumps(
        {
            "characters": [
                {"name": "沈青临", "identity": "剑修少年", "traits": ["宁折不弯"],
                 "speaking_style": "短句", "relationships": "苏晚晴：对手"},
                {"name": "苏晚晴", "identity": "宗主独女",
                 "traits": ["温软", "剑法凌厉"], "speaking_style": "微笑着说话",
                 "relationships": "沈青临：对手"},
            ],
            "lore_candidates": [{"title": "青云宗", "content": "三年一考的宗门", "keys": "青云宗"}],
            "memories": ["沈青临入山", "试剑台初遇"],
            "evidence": [
                {"quote": "剑修无让", "message_index": 0, "speaker": "沈青临"},
                {"quote": "青云宗可不好进", "message_index": 0, "speaker": None},
            ],
        },
        ensure_ascii=False,
    )


def test_distill_end_to_end(novel_file):
    text = load_novel_text(novel_file)
    llm = FakeLLMClient([_fake_reply(), _fake_reply()])
    result = distill_novel(text, "测试小说", llm, max_characters=2, chunk_chars=500)

    names = [c["data"]["name"] for c in result["cards"]]
    assert names == ["沈青临", "苏晚晴"]  # 按提及度排序
    assert result["cards"][0]["data"]["extensions"]["amber"]["evidence_stats"]["mention_count"] == 2
    assert result["worldbook"]["entries"], "世界书应包含设定与事件"
    assert any("[事件]" in e["content"] for e in result["worldbook"]["entries"])
    assert result["report"]["llm_calls"] == 2
    # Q-5：无主引文进 pending（绝不按整块包含猜测归属）
    pend = result["report"]["pending_quotes"]
    assert len(pend) == 1 and pend[0]["quote"] == "青云宗可不好进" and pend[0]["speaker"] is None
    # P1-2：成功/已处理分开统计
    assert result["report"]["blocks_done"] == 2 and result["report"]["blocks_processed"] == 2


def test_character_cards_shape(novel_file):
    text = load_novel_text(novel_file)
    llm = FakeLLMClient([_fake_reply(), _fake_reply()])
    result = distill_novel(text, "测试小说", llm, max_characters=2, chunk_chars=500)
    cards = result["cards"]
    assert len(cards) == 2
    assert cards[0]["spec"] == "chara_card_v3"
    c = cards[0]["data"]
    assert "宁折不弯" in c["description"]
    assert "《测试小说》" in c["scenario"]
    assert c["extensions"]["amber"]["source"] == "novel:测试小说"
    # Q-5：带 speaker 的核验引文归入对应角色卡
    assert any("剑修无让" in ex for ex in c["mes_example"].splitlines())


def test_epub_support(tmp_path):
    """EPUB 基础支持：zip 内 xhtml 文本抽取。"""
    import zipfile

    epub = tmp_path / "book.epub"
    with zipfile.ZipFile(epub, "w") as z:
        z.writestr("mimetype", "application/epub+zip")
        z.writestr(
            "OEBPS/ch1.xhtml",
            "<html><body><h1>第一章</h1><p>沈青临入山。</p><p>山中无岁月。</p></body></html>",
        )
    text = load_novel_text(epub)
    assert "沈青临入山" in text and "山中无岁月" in text
