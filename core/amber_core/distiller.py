"""真人蒸馏管线：分块提炼 → 证据核验 → 确定性合并 → 断点续跑。

纪律（继承 relationship-companion）：
- 证据引文必须能在来源块中命中（归一化后），未命中丢弃并计数——画像可回溯。
- 合并是确定性的（不调 LLM）：清单型字段并集、lore 键控去重、冲突保留双方并记 uncertainties。
- 块级状态机（pending/done/failed），resume 时已完成块跳过并复用其片段；重跑幂等。
- 日志只记状态与计数，不记聊天正文。
"""

from __future__ import annotations

import json
import re
import unicodedata

from .providers import LLMClient, ProviderError
from .schema import Block, BlockState, CompanionProfile, DistillRun, Evidence, ProfileFragment

SYSTEM_PROMPT = (
    "你是人格蒸馏器。从聊天记录片段中提炼「{name}」(direction=self 的说话人) 的稳定人格特征。"
    "只输出一个 JSON 对象，字段："
    'traits(特质短语数组)、behavior_rules(行为/语言习惯数组)、taboos(忌讳话题数组)、humor(幽默风格数组)、'
    'scene_tone(对象，键为场景名如 {{"场景": "语气描述"}})、'
    'lore_candidates(对象数组 {{"title","content","keys"(空格分隔触发词)}})、'
    "memories(重要事实数组)、uncertainties(不确定项数组)、"
    'evidence(对象数组 {{"quote":"记录中的原句片段(8-30字)","message_index":块内序号从0开始}})。'
    "quote 必须是记录中逐字存在的原句片段；不要编造。片段中没有把握的字段输出空。"
)

# 归一化删除类：所有空白/标点/符号（中文标点与引号均为 Unicode \W），只保留文字与数字
DROP_PUNCT_RE = re.compile(r"[\s\W_]+", re.UNICODE)


def normalize_text(s: str) -> str:
    """证据核验用的归一化：NFKC + 去标点空白 + 小写。"""
    return DROP_PUNCT_RE.sub("", unicodedata.normalize("NFKC", s)).lower()


def extract_json(text: str) -> dict:
    """容错解析 LLM JSON：剥 ```json 围栏、截取首尾大括号。"""
    t = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", t, re.DOTALL)
    if fence:
        t = fence.group(1)
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end <= start:
        raise ValueError(f"LLM 输出不含 JSON 对象：{t[:120]!r}")
    return json.loads(t[start : end + 1])


def parse_fragment(raw: dict, block: Block) -> tuple[ProfileFragment, int]:
    """raw dict → (ProfileFragment, dropped_evidence)。

    证据核验：quote 归一化后必须命中块内原文（message_index 指定行优先，越界则全块兜底），未命中丢弃计数。
    """
    frag = ProfileFragment()
    frag.traits = [str(x) for x in (raw.get("traits") or []) if str(x).strip()]
    frag.behavior_rules = [str(x) for x in (raw.get("behavior_rules") or []) if str(x).strip()]
    frag.taboos = [str(x) for x in (raw.get("taboos") or []) if str(x).strip()]
    frag.humor = [str(x) for x in (raw.get("humor") or []) if str(x).strip()]
    st = raw.get("scene_tone") or {}
    if isinstance(st, dict):
        frag.scene_tone = {str(k): str(v) for k, v in st.items() if str(v).strip()}
    lore = raw.get("lore_candidates") or []
    if isinstance(lore, list):
        for item in lore:
            if isinstance(item, dict) and str(item.get("content") or "").strip():
                frag.lore_candidates.append(
                    {
                        "title": str(item.get("title") or "").strip() or str(item.get("content"))[:20],
                        "content": str(item["content"]).strip(),
                        "keys": str(item.get("keys") or "").strip(),
                    }
                )
    frag.memories = [str(x) for x in (raw.get("memories") or []) if str(x).strip()]
    frag.uncertainties = [str(x) for x in (raw.get("uncertainties") or []) if str(x).strip()]

    norm_messages = [normalize_text(m.content) for m in block.messages]
    whole = "".join(norm_messages)
    dropped = 0
    for ev in raw.get("evidence") or []:
        if not isinstance(ev, dict):
            continue
        quote = str(ev.get("quote") or "").strip()
        if len(quote) < 2:
            dropped += 1
            continue
        norm_quote = normalize_text(quote)
        if not norm_quote:
            dropped += 1
            continue
        try:
            idx = int(ev.get("message_index") or 0)
        except (TypeError, ValueError):
            idx = -1
        if 0 <= idx < len(norm_messages) and norm_quote in norm_messages[idx]:
            frag.evidence.append(Evidence(quote=quote, message_index=idx))
        elif norm_quote in whole:
            frag.evidence.append(Evidence(quote=quote, message_index=0))
        else:
            dropped += 1
    return frag, dropped


def merge_fragments(fragments: list[ProfileFragment], name: str) -> CompanionProfile:
    """确定性合并：清单并集保序去重；lore 按 title 键控去重，同 title 不同内容保留首见并记 uncertainties。"""
    profile = CompanionProfile(name=name)

    def union(items: list[str], seen: set[str]) -> list[str]:
        out = []
        for it in items:
            key = normalize_text(it)
            if key and key not in seen:
                seen.add(key)
                out.append(it)
        return out

    s_traits: set[str] = set()
    s_rules: set[str] = set()
    s_taboos: set[str] = set()
    s_humor: set[str] = set()
    s_mem: set[str] = set()
    s_unc: set[str] = set()
    lore_by_title: dict[str, dict[str, str]] = {}
    conflicts: list[str] = []

    for frag in fragments:
        profile.traits += union(frag.traits, s_traits)
        profile.behavior_rules += union(frag.behavior_rules, s_rules)
        profile.taboos += union(frag.taboos, s_taboos)
        profile.humor += union(frag.humor, s_humor)
        profile.memories += union(frag.memories, s_mem)
        profile.uncertainties += union(frag.uncertainties, s_unc)
        for scene, tone in frag.scene_tone.items():
            profile.scene_tone.setdefault(scene, tone)
        for lore in frag.lore_candidates:
            key = normalize_text(lore["title"]) or normalize_text(lore["content"])[:40]
            existing = lore_by_title.get(key)
            if existing is None:
                lore_by_title[key] = dict(lore)
            elif normalize_text(existing["content"]) != normalize_text(lore["content"]):
                conflicts.append(f"lore「{lore['title']}」内容冲突，已保留首见")
        profile.style_examples += [f"「{ev.quote}」" for ev in frag.evidence[:2]]

    profile.lore = list(lore_by_title.values())
    profile.uncertainties += union(conflicts, s_unc)
    seen: set[str] = set()
    profile.style_examples = [x for x in profile.style_examples if not (x in seen or seen.add(x))]
    return profile


class DistillPipeline:
    """蒸馏管线。llm 可为任意实现 chat(system, user, json_mode) 的客户端（测试用 FakeLLMClient）。

    断点续跑：块产物（fragment）随 DistillRun 携带（fragments_by_block），
    resume 新实例时 done 块直接复用片段，不重复调用 LLM。
    """

    def __init__(self, llm: LLMClient, max_attempts: int = 2):
        self.llm = llm
        self.max_attempts = max_attempts

    def _render_user(self, block: Block, name: str) -> str:
        lines = []
        for i, m in enumerate(block.messages):
            who = name if m.direction == "self" else "对方"
            lines.append(f"[{i}] {who}: {m.content}")
        return "\n".join(lines)

    def run(self, blocks: list[Block], name: str, resume: DistillRun | None = None) -> DistillRun:
        run = resume or DistillRun(profile=CompanionProfile(name=name))
        states = run.state_map()
        for block in blocks:
            st = states.get(block.block_id) or BlockState(block_id=block.block_id)
            if st.status == "done" and block.block_id in run.fragments_by_block:
                continue  # 断点续跑：已完成块复用片段
            user = self._render_user(block, name)
            frag: ProfileFragment | None = None
            dropped = 0
            err = ""
            for _ in range(self.max_attempts):
                try:
                    result = self.llm.chat(SYSTEM_PROMPT.format(name=name), user, json_mode=True)
                    run.usage["calls"] += 1
                    run.usage["prompt_tokens"] += result.prompt_tokens
                    run.usage["completion_tokens"] += result.completion_tokens
                    frag, dropped = parse_fragment(extract_json(result.text), block)
                    break
                except (ValueError, json.JSONDecodeError) as e:
                    err = str(e)  # 调用已成功返回但内容不可用：chat 计数已在上方记账
                except ProviderError as e:
                    err = str(e)
                    run.usage["calls"] += 1  # 调用已发起但未返回：补记账
            if frag is None:
                st.status, st.error, st.attempts = "failed", err[:200], st.attempts + 1
            else:
                st.status, st.error = "done", ""
                run.fragments_by_block[block.block_id] = frag
                run.dropped_evidence += dropped
            run.block_states = [s for s in run.block_states if s.block_id != st.block_id] + [st]
            run.block_states.sort(key=lambda s: s.block_id)

        fragments = [run.fragments_by_block[i] for i in sorted(run.fragments_by_block)]
        run.profile = merge_fragments(fragments, name)
        run.profile.evidence_stats = {
            "verified": sum(len(f.evidence) for f in fragments),
            "dropped_total": run.dropped_evidence,
            "blocks_done": sum(1 for s in run.block_states if s.status == "done"),
            "blocks_failed": sum(1 for s in run.block_states if s.status == "failed"),
        }
        run.failed_blocks = [s.block_id for s in run.block_states if s.status == "failed"]
        return run
