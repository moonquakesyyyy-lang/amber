"""琥珀核心数据模型。

统一内部格式与蒸馏产物定义；所有层（导入/分块/蒸馏/卡片/记忆）共享本模块。
字段设计对齐 relationship-companion 的工程纪律：显式作用域、证据可回溯、清单型字段并集合并。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# 统一消息方向：self=蒸馏对象本人（角色原型），other=对方（用户）
DIRECTION_SELF = "self"
DIRECTION_OTHER = "other"

MEMORY_LAYERS = ("raw", "episodic", "semantic", "core")


@dataclass
class Message:
    """统一内部消息格式（所有导入适配器归一到的目标）。"""

    ts: str  # ISO8601 或可比较时间字符串
    sender_id: str
    sender_name: str
    direction: str  # DIRECTION_SELF / DIRECTION_OTHER
    content: str
    type: str = "text"  # text/image/voice/...：非文本参与计数但不参与蒸馏正文
    source: str = ""  # telegram / memotrace / generic / ...

    def __post_init__(self) -> None:
        if self.direction not in (DIRECTION_SELF, DIRECTION_OTHER):
            raise ValueError(f"direction must be self|other, got {self.direction!r}")
        if not isinstance(self.ts, str) or not self.ts.strip():
            raise ValueError("ts must be a non-empty string")


@dataclass
class Block:
    """蒸馏分块：条数或时间断档切出的一段原文。"""

    block_id: int
    messages: list[Message]
    start_ts: str
    end_ts: str


@dataclass
class Evidence:
    """证据引文：必须能在来源块中命中（归一化后）。"""

    quote: str
    message_index: int  # 块内序号


@dataclass
class ProfileFragment:
    """单块蒸馏产物（LLM JSON 解析目标）。所有清单型字段在合并时做并集/键控去重。"""

    traits: list[str] = field(default_factory=list)
    behavior_rules: list[str] = field(default_factory=list)
    taboos: list[str] = field(default_factory=list)
    humor: list[str] = field(default_factory=list)
    scene_tone: dict[str, str] = field(default_factory=dict)  # 场景→语气描述
    lore_candidates: list[dict[str, str]] = field(default_factory=list)  # {title, content, keys}
    memories: list[str] = field(default_factory=list)  # 重要关系事实
    uncertainties: list[str] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)


@dataclass
class CompanionProfile:
    """合并后的结构化人格画像（蒸馏最终产物）。"""

    name: str
    persona_summary: str = ""
    traits: list[str] = field(default_factory=list)
    behavior_rules: list[str] = field(default_factory=list)
    taboos: list[str] = field(default_factory=list)
    humor: list[str] = field(default_factory=list)
    scene_tone: dict[str, str] = field(default_factory=dict)
    lore: list[dict[str, str]] = field(default_factory=list)  # {title, content, keys}
    memories: list[str] = field(default_factory=list)
    uncertainties: list[str] = field(default_factory=list)  # 冲突/存疑项（人工复核入口）
    style_examples: list[str] = field(default_factory=list)  # 本人原话示例（mes_example）
    evidence_stats: dict[str, int] = field(default_factory=dict)  # 核验统计

    def merge_summary(self) -> str:
        parts = [p for p in (f"特质：{'、'.join(self.traits[:8])}" if self.traits else "",
                             f"习惯：{'；'.join(self.behavior_rules[:5])}" if self.behavior_rules else "",
                             f"幽默感：{'；'.join(self.humor[:3])}" if self.humor else "") if p]
        return f"{self.name}，" + "。".join(parts) + "。" if parts else self.name


@dataclass
class BlockState:
    """蒸馏块状态机（断点续跑账本）。status: pending|done|failed"""

    block_id: int
    status: str = "pending"
    attempts: int = 0
    error: str = ""


@dataclass
class DistillRun:
    """一次蒸馏运行的总账。fragments_by_block 随账携带，使断点续跑跨实例可复用已完成块。"""

    profile: CompanionProfile
    block_states: list[BlockState] = field(default_factory=list)
    fragments_by_block: dict[int, ProfileFragment] = field(default_factory=dict)
    usage: dict[str, int] = field(default_factory=lambda: {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0})
    dropped_evidence: int = 0
    failed_blocks: list[int] = field(default_factory=list)

    def state_map(self) -> dict[int, BlockState]:
        return {s.block_id: s for s in self.block_states}


@dataclass
class MemoryRecord:
    """记忆条目（四层记忆）。隔离双键 profile_id × owner 写进 SQL WHERE。"""

    id: int
    profile_id: str
    owner: str
    layer: str  # raw / episodic / semantic / core
    content: str
    importance: float  # 0-10
    created_at: str
    last_accessed: str
    decay_score: float = 1.0  # 拟人遗忘：episodic 快衰减，semantic 只降权
    archived: bool = False
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.layer not in MEMORY_LAYERS:
            raise ValueError(f"layer must be one of {MEMORY_LAYERS}, got {self.layer!r}")
