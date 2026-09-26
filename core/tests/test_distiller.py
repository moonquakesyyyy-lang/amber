"""蒸馏管线测试：全链路 / 证据核验 / 确定性合并 / 断点续跑 / 失败重试。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from amber_core.distiller import (
    DistillPipeline,
    extract_json,
    merge_fragments,
    normalize_text,
    parse_fragment,
)
from amber_core.providers import FakeLLMClient
from amber_core.schema import Block, Message, ProfileFragment


def _block(texts: list[str], block_id: int = 0) -> Block:
    msgs = [
        Message(ts=str(1700000000 + i), sender_id="s", sender_name="小夏", direction="self", content=t)
        for i, t in enumerate(texts)
    ]
    return Block(block_id=block_id, messages=msgs, start_ts=msgs[0].ts, end_ts=msgs[-1].ts)


def _fragment_json(traits=None, rules=None, lore=None, evidence=None, memories=None) -> str:
    return json.dumps(
        {
            "traits": traits or [],
            "behavior_rules": rules or [],
            "taboos": [],
            "humor": [],
            "scene_tone": {"闲聊": "轻快"},
            "lore_candidates": lore or [],
            "memories": memories or [],
            "uncertainties": [],
            "evidence": evidence or [],
        },
        ensure_ascii=False,
    )


def test_extract_json_fences_and_noise():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('前置噪声 {"a": {"b": 2}} 尾部噪声') == {"a": {"b": 2}}
    import pytest
    with pytest.raises(ValueError):
        extract_json("没有大括号")


def test_evidence_verification_drops_fabricated():
    block = _block(["今天加班到十点才吃上饭", "周末想去看海"])
    raw = json.loads(_fragment_json(
        traits=["爱吐槽加班"],
        evidence=[
            {"quote": "加班到十点", "message_index": 0},   # 命中（子串+标点容忍）
            {"quote": "我喜欢周游世界", "message_index": 0},  # 编造 → 丢
            {"quote": "看海", "message_index": 99},        # 索引越界但全文命中 → 保
            {"quote": "x", "message_index": 0},           # 过短 → 丢
        ],
    ))
    frag, dropped = parse_fragment(raw, block)
    assert len(frag.evidence) == 2
    assert dropped == 2
    assert frag.traits == ["爱吐槽加班"]


def test_pipeline_full_run_and_merge():
    blocks = [
        _block(["今天加班好累啊，就想吃火锅", "你也是"], 0),
        _block(["我周末从来不睡懒觉", "嘿嘿"], 1),
    ]
    llm = FakeLLMClient([
        _fragment_json(traits=["热爱美食"], rules=["常吐槽加班"],
                       lore=[{"title": "养了只猫", "content": "她养了只叫布丁的橘猫", "keys": "猫 布丁"}],
                       evidence=[{"quote": "加班好累", "message_index": 0}]),
        _fragment_json(traits=["作息规律"], rules=["不睡懒觉"],
                       lore=[{"title": "养了只猫", "content": "她的猫叫布丁，橘色", "keys": "猫"}],
                       evidence=[{"quote": "从来不睡懒觉", "message_index": 0}]),
    ])
    run = DistillPipeline(llm).run(blocks, "小夏")
    assert run.failed_blocks == []
    assert run.usage["calls"] == 2
    p = run.profile
    assert p.traits == ["热爱美食", "作息规律"]          # 保序并集
    assert p.behavior_rules == ["常吐槽加班", "不睡懒觉"]
    assert len(p.lore) == 1                             # 同 title 键控去重，首见保留
    assert p.lore[0]["content"].startswith("她养了只叫布丁的橘猫")
    assert p.scene_tone == {"闲聊": "轻快"}
    assert "「加班好累」" in p.style_examples
    assert run.profile.evidence_stats["verified"] == 2
    assert run.profile.evidence_stats["blocks_done"] == 2


def test_pipeline_resume_skips_done_blocks():
    blocks = [_block(["第一块内容"], 0), _block(["第二块内容"], 1)]
    llm = FakeLLMClient([_fragment_json(traits=["A"]), "不是JSON"])
    run = DistillPipeline(llm, max_attempts=2).run(blocks, "小夏")
    assert run.failed_blocks == [1]
    assert llm.replies == [] and llm.calls and run.usage["calls"] == 3  # 第一块1次+第二块2次

    llm2 = FakeLLMClient([_fragment_json(traits=["B"])])
    calls_before = run.usage["calls"]
    run2 = DistillPipeline(llm2).run(blocks, "小夏", resume=run)
    assert run2.failed_blocks == []
    assert run2.profile.traits == ["A", "B"]
    assert run.usage["calls"] - calls_before == 1  # resume 就地延续账本；done 块零重调
    assert "第二块内容" in llm2.calls[0]["user"]  # 只重跑了失败块


def test_merge_conflicting_lore_records_uncertainty():
    f1 = ProfileFragment(lore_candidates=[{"title": "猫", "content": "橘猫布丁", "keys": "猫"}])
    f2 = ProfileFragment(lore_candidates=[{"title": "猫", "content": "奶牛猫", "keys": "猫"}])
    p = merge_fragments([f1, f2], "小夏")
    assert len(p.lore) == 1 and p.lore[0]["content"] == "橘猫布丁"
    assert any("冲突" in u for u in p.uncertainties)


def test_normalize_tolerance():
    assert normalize_text("加班，好累！") == normalize_text("加班好累")
    assert normalize_text("Hello，World") == "helloworld"
