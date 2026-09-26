"""SillyTavern 角色卡 V3 互通层。

蒸馏画像 ⇄ 角色卡同构（调研 §1.3）：画像→V3 卡导出（生态互通卖点）；
带 amber extensions 的卡可无损往返。遵循 spec：未知字段必须可被他人忽略，
amber 自有数据全部收进 data.extensions.amber 命名空间。
"""

from __future__ import annotations

from typing import Any

from .schema import CompanionProfile

SPEC = "chara_card_v3"
SPEC_VERSION = "3.0"
AMBER_NS = "amber"


def profile_to_card_v3(profile: CompanionProfile, first_mes: str = "") -> dict[str, Any]:
    """CompanionProfile → chara_card_v3 JSON。

    - description：persona_summary + traits 渲染
    - mes_example：蒸馏 style_examples（本人原话，声音的最佳预测器）
    - character_book：profile.lore → entries（关键词触发，含 secondary_keys 兼容）
    - extensions.amber：完整画像 + 忌讳 + 行为规则 + 场景语气（无损往返载体）
    """
    desc_lines = [profile.persona_summary or profile.merge_summary()]
    if profile.traits:
        desc_lines.append("性格特质：" + "、".join(profile.traits))
    if profile.behavior_rules:
        desc_lines.append("行为习惯：" + "；".join(profile.behavior_rules))
    entries = []
    for i, lore in enumerate(profile.lore):
        entries.append(
            {
                "id": i,
                "keys": [k for k in str(lore.get("keys", "")).split() if k],
                "content": lore["content"],
                "comment": lore.get("title", ""),
                "enabled": True,
                "insertion_order": 100 + i,
                "constant": False,
                "position": "before_char",
                "extensions": {},
            }
        )
    card = {
        "spec": SPEC,
        "spec_version": SPEC_VERSION,
        "data": {
            "name": profile.name,
            "description": "\n".join(desc_lines),
            "personality": "、".join(profile.traits[:12]),
            "scenario": "",
            "first_mes": first_mes,
            "mes_example": "\n".join(profile.style_examples),
            "creator_notes": "由琥珀（Amber）从真人聊天记录蒸馏生成；每条设定可在 amber.extensions 回溯证据。",
            "system_prompt": "",
            "post_history_instructions": "",
            "alternate_greetings": [],
            "character_book": {"entries": entries},
            "tags": ["amber"],
            "extensions": {
                AMBER_NS: {
                    "version": 1,
                    "persona_summary": profile.persona_summary,
                    "traits": profile.traits,
                    "behavior_rules": profile.behavior_rules,
                    "taboos": profile.taboos,
                    "humor": profile.humor,
                    "scene_tone": profile.scene_tone,
                    "memories": profile.memories,
                    "style_examples": profile.style_examples,
                    "evidence_stats": profile.evidence_stats,
                }
            },
        },
    }
    return card


def card_to_profile(card: dict[str, Any]) -> CompanionProfile:
    """V3/V2 卡 → CompanionProfile（导入方向）。

    优先读 extensions.amber（无损）；否则从通用字段粗提取（P0 级：description/personality 入 summary，
    character_book 入 lore）。任何来源都不得让卡片内容进入私有记忆层——导入物一律是角色级公共资产。
    """
    data = card.get("data") or card  # V2 兼容：data 节点或顶层
    amber = (data.get("extensions") or {}).get(AMBER_NS) or {}
    name = str(data.get("name") or "").strip()
    if not name:
        raise ValueError("角色卡缺少 name")
    profile = CompanionProfile(name=name)
    profile.persona_summary = str(amber.get("persona_summary") or data.get("description") or "")
    profile.traits = [str(x) for x in (amber.get("traits") or _split_cn(str(data.get("personality") or "")))]
    profile.behavior_rules = [str(x) for x in (amber.get("behavior_rules") or [])]
    profile.taboos = [str(x) for x in (amber.get("taboos") or [])]
    profile.humor = [str(x) for x in (amber.get("humor") or [])]
    profile.scene_tone = {str(k): str(v) for k, v in (amber.get("scene_tone") or {}).items()}
    profile.memories = [str(x) for x in (amber.get("memories") or [])]
    profile.style_examples = [str(x) for x in (amber.get("style_examples") or _split_examples(str(data.get("mes_example") or "")))]  # noqa: E501
    profile.evidence_stats = {str(k): int(v) for k, v in (amber.get("evidence_stats") or {}).items()}
    book = data.get("character_book") or {}
    for entry in book.get("entries") or []:
        content = str(entry.get("content") or "").strip()
        if not content:
            continue
        keys = entry.get("keys") or []
        if isinstance(keys, str):
            keys = keys.split()
        profile.lore.append(
            {
                "title": str(entry.get("comment") or content[:20]),
                "content": content,
                "keys": " ".join(str(k) for k in keys),
            }
        )
    return profile


def _split_cn(s: str) -> list[str]:
    return [p for p in s.replace("，", "、").split("、") if p.strip()]


def _split_examples(s: str) -> list[str]:
    return [p.strip() for p in s.splitlines() if p.strip()]
