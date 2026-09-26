"""角色卡互通测试：profile→V3 卡 spec 字段 / amber 无损往返 / V2 兼容导入。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from amber_core.card import card_to_profile, profile_to_card_v3
from amber_core.schema import CompanionProfile


def _profile() -> CompanionProfile:
    return CompanionProfile(
        name="小夏",
        persona_summary="爱吐槽加班的火锅爱好者",
        traits=["热爱美食", "作息规律"],
        behavior_rules=["常吐槽加班"],
        taboos=["不说教"],
        humor=["自嘲式幽默"],
        scene_tone={"闲聊": "轻快"},
        lore=[{"title": "养了只猫", "content": "她养了只叫布丁的橘猫", "keys": "猫 布丁"}],
        memories=["用户爱吃火锅"],
        style_examples=["「加班好累啊」"],
    )


def test_card_v3_spec_fields():
    card = profile_to_card_v3(_profile(), first_mes="在呀宝宝")
    assert card["spec"] == "chara_card_v3" and card["spec_version"] == "3.0"
    data = card["data"]
    assert data["name"] == "小夏"
    assert "热爱美食" in data["description"] and data["personality"].startswith("热爱美食")
    assert data["first_mes"] == "在呀宝宝"
    assert data["mes_example"] == "「加班好累啊」"
    entries = data["character_book"]["entries"]
    assert len(entries) == 1
    assert entries[0]["keys"] == ["猫", "布丁"] and entries[0]["enabled"] is True
    amber = data["extensions"]["amber"]
    assert amber["taboos"] == ["不说教"] and amber["evidence_stats"] == {}


def test_roundtrip_lossless_via_amber_namespace():
    p1 = _profile()
    p1.evidence_stats = {"verified": 5}
    card = profile_to_card_v3(p1)
    p2 = card_to_profile(card)
    assert p2.name == "小夏"
    assert p2.traits == p1.traits and p2.behavior_rules == p1.behavior_rules
    assert p2.taboos == p1.taboos and p2.humor == p1.humor
    assert p2.scene_tone == p1.scene_tone and p2.memories == p1.memories
    assert p2.lore == p1.lore and p2.style_examples == p1.style_examples
    assert p2.evidence_stats == {"verified": 5}


def test_v2_card_import_fallback():
    v2 = {
        "spec": "chara_card_v2",
        "data": {
            "name": "路人甲",
            "description": "一个测试角色",
            "personality": "温柔、话痨",
            "mes_example": "「你好呀」\n「今天天气不错」",
            "character_book": {"entries": [{"keys": ["天气"], "content": "TA 每天聊天气", "comment": "天气梗"}]},
        },
    }
    p = card_to_profile(v2)
    assert p.name == "路人甲"
    assert p.persona_summary == "一个测试角色"
    assert p.traits == ["温柔", "话痨"]
    assert p.style_examples == ["「你好呀」", "「今天天气不错」"]
    assert p.lore[0]["keys"] == "天气"

    import pytest
    with pytest.raises(ValueError):
        card_to_profile({"data": {"description": "no name"}})
