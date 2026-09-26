# 琥珀（Amber）架构

版本 v0 草案（2026-09-27）。定位与岔路口裁决见 [research/20260927-fusion-research.md](research/20260927-fusion-research.md)。

## 1. 三端形态

| 端 | 技术 | 职责 |
|---|---|---|
| **App（主体）** | 华灯 huadeng fork（Kotlin/Compose/Room，AGPL-3.0） | 聊天界面、LLM 直连（用户 key）、角色卡/世界书/宏引擎、新增核心层 A-E |
| **桌面伴侣端（可选）** | Python（`core/` 包） | 重型蒸馏、向量化、reflection；产物文件交回 App |
| **外接渠道（可选）** | 各平台 bot 接入器 | 微信/QQ/TG bot 作为附加入口，非必需 |

## 2. App 内新增核心层

| 层 | 模块（拟） | 职责 | 关键语义 |
|---|---|---|---|
| A 记录导入 | `importer` | TG JSON / MemoTrace JSON·CSV / 通用 JSONL → 统一消息 | 只读明文产物；统一 schema `{ts,sender_id,sender_name,direction,content,type,source}` |
| B 蒸馏引擎 | `distiller` | 分块 → LLM 提炼 → 确定性合并 → 证据核验 → 画像+V3卡 | 状态机断点续跑；分批后台；证据引文可回溯；预算账本 |
| C 四层记忆 | `memory` | raw→episodic→semantic→core；三因子召回；遗忘曲线 | `profile_id × owner` 双键隔离写在 SQL WHERE；episodic 衰减、semantic 降权；记忆可查看/编辑/删除 |
| D 情感产品 | `companion` | 主动关怀（意愿模型+时段/冷却/概率护栏）、纪念日、情绪连续、表情包、关系阶段 | 主动性是"她自己的生活"，不是定时器广播 |
| E 外接渠道 | `channels` | 各 bot 接入器（P5 再做） | 渠道只是入口，核心能力零依赖渠道 |

## 3. 蒸馏管线（P0 参考实现已定 spec）

```text
统一消息(JSONL)
  → chunker（默认 100 条/块 + 时间断档切分）
  → 每块 LLM 提炼 → ProfileFragment（traits/behavior_rules/taboos/humor/scene_tone/lore 候选 + 证据引文）
  → deterministic merge（清单型字段并集、键控去重、冲突保留双方+标记）
  → 证据核验（引文须在原记录中命中，未命中降权/丢弃）
  → CompanionProfile
  → 双产物：结构化画像（本地 DB）+ SillyTavern CCv3 角色卡 JSON（生态互通）
```

- LLM 客户端：OpenAI 兼容（含 `local` Ollama/vLLM 零外发档），密钥用户自持
- 断点续跑：块级状态机（pending/done/failed）+ 账本；重跑幂等
- 隐私红线：任何块内容只进用户直连的 LLM 与本地库；日志只记状态不记正文

## 4. 记忆模型

四层：`raw_messages`（原文）→ `episodic`（日/周摘要，遗忘曲线衰减）→ `semantic`（结构化事实/画像，ADD/UPDATE/DELETE 合并）→ `core`（常驻记忆块，用户可编辑）。

召回打分 = `recency(指数衰减) × relevance(嵌入相似/词法兜底) × importance(写入时 LLM 评 1-10)`。

隔离：所有私有读写 SQL 必带 `profile_id`（角色）与 `owner`（用户）双键 + CHECK/复合外键；跨角色查询在 SQL 层即不存在（继承 relationship-companion schema3 纪律：不靠应用层过滤、不靠 exclude_ids）。

## 5. 工程纪律（继承 relationship-companion 实践）

- 文档驱动：任务状态唯一来源 `docs/tasks/TASKS.md`；执行记录独立留档
- 测试优先：核心层全量 pytest；隔离/隐私用污染探针
- 发布纪律：版本、构建信息、变更记录；AGPL-3.0 全程携带
- 隐私门禁：仓库不含真实账号/记录；示例数据一律合成
