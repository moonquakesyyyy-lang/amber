# 琥珀（Amber）· 新一代本地优先 AI 情感陪伴软件 — 融合调研报告

- 日期：2026-09-27
- 代号：**琥珀 / Amber**（暂定名：蒸馏=把真人时光封存成琥珀；最终名称待用户拍板）
- 调研人：ZCode-GLM（用户直接授权）
- 结论先行：**以华灯（rikkahub huadeng fork，AGPL-3.0）为 Android 基座，叠加「聊天记录导入 → 真人蒸馏 → 记忆隔离 → 情感陪伴」核心层，全流程本地化，开发者不经手任何用户数据；relationship-companion 的引擎资产作为参考实现平移。**

---

## 0. 岔路口的最终裁决（决策记录）

用户在推进中经历两次方向修正，此处固化最终决策，防止后续 Agent 拿旧方向接续：

| 被否决的方向 | 否决原因 |
|---|---|
| ~~AstrBot 插件继续做深（relationship-companion 单线）~~ | 深度绑定 AstrBot 宿主与云端部署；用户聊天记录与蒸馏结果要经过开发者云端，隐私模型错误；渠道绑死微信 |
| ~~把 AstrBot 的微信接口搬进酒馆 App~~ | ① 微信接入的真实主体是外部协议网关（wechatpadpro 类容器），App 直连需要 7×24 常驻后台，Android 杀后台=微信掉线漏消息；② 微信平台本身频控/封号风险多，把命脉拴在微信上方向就错了；③ 依然解决不了"记录过云端"的隐私问题 |
| ~~AstrBot 服务端作为陪伴核心、App 作为前端接入~~ | 仍是"记录/蒸馏过服务端"模型；用户想清楚后明确：**渠道无关、本地优先** |

### 最终产品定义

> **一个让用户亲手打造"属于自己的 AI 情感陪伴机器人"的本地优先软件。**

1. **原料在用户手里**：微信/QQ/TG 等聊天记录由用户自行导出（提供工具链指引），软件只读"明文产物"。
2. **蒸馏在本地**：导入的记录分块蒸馏成结构化人格画像（数字角色）。LLM 调用走**用户自己的 API key 直连**（或本地 Ollama/vLLM，零外发）；开发者不设任何中转服务器。
3. **结果在本地**：画像、世界书、记忆全部存本地 SQLite，导出/备份/迁移自由。
4. **渠道无关**：软件本身就是聊天界面（Android App 优先）；微信机器人、QQ、Telegram 只是**可选的外接渠道**，接不接、什么时候接由用户决定——核心能力不依赖任何渠道。
5. **能力四件套**：真人记录蒸馏角色 ＋ 记忆隔离 ＋ 角色卡生态兼容（SillyTavern V2/V3）＋ 调教系统（世界书/宏/注入位置/作者注）。
6. **隔离三义**：角色之间记忆严格隔离（防止 A 角色知道 B 角色的事）；共享世界书按角色分组；未来多人共用设备时"关系"维度天然可扩展。

---

## 1. 竞品与生态调研

### 1.1 开源客户端生态（可直接作为基座/机制来源）

| 项目 | 许可证 | 形态 | 活跃度 | 关键可借鉴点 |
|---|---|---|---|---|
| **SillyTavern** | AGPL-3.0 | Node.js + Web UI | 33.8k★，极活跃 | 角色卡 V2/V3 规范、World Info 完整语义、extensions 开放字段模式 |
| **RikkaHub（上游）** | AGPL-3.0 | Android 原生（Kotlin/Compose/Room/Koin） | 7.86k★，极活跃 | 多模块骨架、`ai` 抽象层屏蔽 Provider 差异、消息分支（swipe）、MCP 集成 |
| **华灯 fork** | AGPL-3.0 | Android 原生 | 单维护者，2026-09-26 仍在推送 | **酒馆兼容全套已完成**：V2/V3 无损导入（含世界书/PHI/深度提示）、世界书官方语义对齐、宏引擎 2.0、作者注、角色卡导出 PNG/JSON、缓存省 token、Jev 决策、主动消息、AI 群聊、插件系统 |
| **RisuAI** | GPL-3.0 | Svelte+Tauri/Capacitor | 活跃 | 长期记忆"压缩+摘要分级"管线；CCv3 规范主导者，assets/内嵌世界书兼容参照 |
| **MaiBot（麦麦）** | GPL-3.0 | Python + QQ 协议端 | 活跃 | 海马体记忆（构建/遗忘/整合）、**意愿/兴趣驱动主动发言（非定时器）**、情绪状态机、关系分层、"最像而不是好"设计理念 |
| **ChatterUI** | AGPL-3.0 | React Native + llama.rn | 2.8k★ | 端上 GGUF 推理的离线最小范本 |
| **Backyard AI** | 闭源 | 桌面 | — | 零配置开箱体验、角色包=模型参数+世界书+语音打包分发 |

**许可证矩阵**：ST / RikkaHub / 华灯 = AGPL-3.0；RisuAI / MaiBot = GPL-3.0（可单向并入 AGPL）；Backyard = 闭源（只借鉴体验）。
**裁决**：以华灯为基座 ⇒ 整体 AGPL-3.0 发行。纯客户端分发不触发 AGPL 网络条款；本软件"本地优先、开发者不经手数据"的定位与 AGPL 精神天然一致。

### 1.2 SillyTavern World Info 官方语义（调教引擎的兼容基线，务必逐条对齐）

- 触发三模式：`constant`（常驻）/ 关键词 / 向量化（embedding 激活）
- Scan Depth：扫描最近 N 条消息；0=仅递归条目+作者注
- 预算：按 max-context 百分比或绝对 token 数，耗尽即停；优先级 = constant → Order 大者 → 直接命中 > 递归触发
- Probability：触发后按百分比注入；sticky 期间跳过概率检查
- Timed effects（按消息数）：sticky（保持 N 条）/ cooldown（N 条内不可再触发）/ delay（不足 N 条不激活）；仅当前聊天生效，swipe/删末条清除
- Recursion：Max Recursion Steps；每条目可设递归豁免；Min Activations 与 Recursion Steps 互斥
- Selective：AND ANY / AND ALL / NOT ANY / NOT ALL（过滤键支持正则）；Inclusion Group 同组互斥按权重随机
- 插入：Order 越大越靠近上下文末；Position 多档（角色定义前后/示例前后/作者注上下文/@D 深度+role）
- 中文注意：默认关闭"全词匹配"

### 1.3 记忆与蒸馏技术栈选型

**导出工具链（蒸馏原料）**：
- 微信：MemoTrace/留痕（LC044/WeChatMsg，15k★）导出 JSON/CSV/HTML/TXT，PC 微信 3.x 可用；**微信 4.0 兼容是社区痛点**（老一代内存搜钥方案大面积失效，PyWxDump 已删库）——**不自研解密，只做"产物文件适配器"**；iOS 走官方备份 + iMazing/WechatExporter 路线
- QQ：QQNT SQLCipher 加密，社区工具（murmur 等）逆向属性强、随版本易碎——同样只收"用户自备产物"
- **Telegram：官方导出 machine-readable JSON，黄金标准，原生支持**
- 结论：统一内部 schema（JSONL：`{ts, sender_id, sender_name, direction, content, type, source}`）+ 4 个适配器（TG JSON / MemoTrace JSON·CSV / 通用 JSONL·CSV / 兜底）

**记忆架构（单机 App 现实选型）**：
- 学 MemGPT/Letta 的分层思想，不引框架；抄 Mem0 的 ADD/UPDATE/DELETE 记忆合并管线（纯 Python，可插 sqlite-vec）
- MemoryBank 遗忘曲线做"拟人遗忘"（episodic 衰减、semantic 只降权不删）
- Generative Agents 三因子检索打分（recency×relevance×importance）+ 定期 reflection 回写画像
- 结论：**SQLite 一把梭四层**：`raw_messages` → `episodic`（日/周摘要）→ `semantic`（结构化事实+画像）→ `core`（常驻记忆块）；v1 不引向量库服务，sqlite-vec 足够
- 隔离语义平移：relationship-companion schema3 的 `companion_shared` / `relationship_private` 双作用域 + SQL 层 WHERE 强制隔离 + frozen ScopeContext，单机版简化为 `profile_id`（角色）× `owner`（用户），保留 CHECK/复合外键/失败关闭的纪律

**蒸馏路线**：
- **提示词画像路线为主**（分块→LLM 提炼→确定性合并→证据引文核验→结构化画像）：可解释、可修正、成本只是用户自己的 key、手机可分批后台跑（状态机断点续跑）
- LoRA 端侧训练 2026 年内手机不现实，留作桌面端可选增值（MLX/QLoRA → llama.cpp 挂载推理）
- Second-Me（Apache-2.0）的 HMM 给出"先结构化记忆、再轻量个性化"的两段式印证
- ST 社区"本人克隆"方法论：风格/口癖进卡片 mes_example，事实进 lorebook，卡片本体精简——**画像字段与卡字段一一映射，蒸馏产出"结构化画像 + V3 角色卡"双产物**

### 1.4 闭源产品形态提炼（产品经理视角，知识截止 2025-2026 上半年）

- **Replika**：关系等级（XP/级别）、日记、语音/AR 通话、按用户状态触发的主动关怀（早上问好/深夜共情）、付费点=语音+关系功能。留存内核：**"它记得我"的确认感**（定期引用用户说过的话）。
- **Character.AI**：角色生态与低门槛创作、群聊；人格一致性靠社区打磨的开场+示例对话。
- **星野/Talkie（MiniMax）**：卡片化角色 + 剧情推进 + 共鸣度养成；中文陪伴的"关系推进可视化"（好感度/阶段）做得最显性。
- **Glow / X Eva（小冰）**：情感计算框架——情绪状态连续性（上一轮的情绪延续到下一轮）、人格一致性评分；X Eva 主打"复刻真人"（声线+人格），验证了**真人克隆是真实需求**。
- **Kindroid**：记忆分层（可编辑的核心记忆 + 自动长期记忆）、Journeys（剧情线）、照片生成；用户最买账的是**"记忆可查看可编辑"带来的掌控感**。
- **Chai / Nastia**：记忆量分级付费——证明记忆深度是用户愿付费的核心价值。

**A. 留存 Top 5 机制**（新软件必须内建）：
1. 主动开场/主动关怀（有"自己的生活"的主动，不是定时器广播——参考 MaiBot 意愿模型 + relationship-companion proactive 策略参数）
2. 记忆被记住的"被了解感"（召回的记忆以自然口吻提及，Kindroid 式可查看可编辑）
3. 纪念日与仪式感（认识 N 天、生日、重要事件——relationship-companion 的 pending_events/anniversary 语义）
4. 关系阶段推进（称呼变化、话题深度变化——星野的共鸣度可视化）
5. 情绪连续性（上轮情绪延续；情绪状态机影响语气与表情包选择——MaiBot/小冰）

**B. "像真人"感知来源排序**：记忆召回 > 语气风格一致 > 知道用户生活细节 > 主动行为 > 称呼/昵称。对应技术：四层记忆 + 蒸馏画像的 traits/behavior_rules + 场景语气。

**D. 隐私/本地化诉求**：强且增长（Reddit/贴吧大量"聊天记录会不会被拿去训练"焦虑；Second-Me 一周 6k★ 是直接证据）；但用户不愿牺牲体验，所以"本地优先 + 用户自己的 key"必须同时把体验做满。

---

## 2. 自有资产盘点（relationship-companion → 琥珀）

一手勘察结论（2026-09-27，plugin/ 共 79 个 .py）：

- **仅 10 个文件耦合 AstrBot**，且 8 个只是 `from astrbot.api import logger`（换 Python logging 即可）；真正宿主耦合集中在 `main.py`（插件钩子层，不迁移）与 distillation 的 runner/adapter（`Context`/`StarTools` 取 Provider——新软件直接用自带 providers.py）
- **`persona_engine/providers.py` 自带 OpenAI 兼容多 Provider 客户端**（纯 urllib，glm/doubao/自定义中转/**local: Ollama/vLLM 零外发**），密钥环境变量/本地文件，不落 git——蒸馏引擎天然不依赖任何宿主
- persona_engine 25 个模块（蒸馏/预算账本/证据核验/盲评门禁/合并器）+ 运行时记忆/场景索引/turn_recall/表情包/主动策略/气泡防抖，全部纯 Python + SQLite
- 隔离纪律成熟：schema3 双作用域、复合外键、失败关闭、迁移工具、1693 项测试——**工程纪律直接继承**

**平移清单**：
| 资产 | 平移方式 |
|---|---|
| 蒸馏管线（分块/提炼/合并/证据核验/预算/断点续跑） | 复制 + 去 astrbot 化，作为"引擎参考实现"（Python）；Kotlin 端按同一 spec 重写 |
| 双作用域记忆 schema | 语义平移到 Room（Kotlin）+ Python 侧保留为桌面伴侣端 |
| 主动沟通策略（时段/频率/冷却/概率） | 参数与策略表平移，触发源改"App 前台服务 + 意愿模型" |
| 表情包情绪匹配/防重复 | 平移 |
| 气泡防抖/分条 | 平移（App 端对应多气泡发送） |
| 盲评/eval 门禁 | 平移为"像不像"自评工具 |

## 3. 新软件架构（琥珀 v0 架构决议）

```text
┌────────────────────────────────────────────────────────┐
│  琥珀 Android App（华灯 huadeng fork 基座，AGPL-3.0）      │
│  已有：UI/主题、LLM 直连(用户key)、角色卡V2/V3、世界书引擎、 │
│        宏引擎、作者注、消息分支、Jev、缓存优化、插件系统      │
│                                                        │
│  新增核心层（本项目的差异化）：                            │
│  ┌──────────────────────────────────────────────┐      │
│  │ A. 记录导入器   TG JSON / MemoTrace / 通用JSONL  │      │
│  │ B. 蒸馏引擎     分块→提炼→合并→证据核验→画像+V3卡  │      │
│  │ C. 四层记忆     raw→episodic→semantic→core       │      │
│  │                （profile×owner 隔离 + 遗忘曲线）  │      │
│  │ D. 情感产品层   主动关怀(意愿模型)、纪念日、情绪连续、 │      │
│  │                表情包、关系阶段                     │      │
│  │ E. 外接渠道(可选) 微信bot/QQbot/TG bot 接入器      │      │
│  └──────────────────────────────────────────────┘      │
│  存储：Room(SQLite) 本地，导出/备份自由                    │
└────────────────────────────────────────────────────────┘
        ↕ （可选）局域网/文件互通
┌────────────────────────────────────────────────────────┐
│  桌面伴侣端（Python，复用 relationship-companion 引擎）    │
│  重型蒸馏数千条记录、向量化、reflection 合成；             │
│  产物=画像+V3卡+记忆包，文件方式交回 App                   │
└────────────────────────────────────────────────────────┘
```

**为什么不纯自研 App**：华灯已把调教层（角色卡/世界书/宏/作者注/缓存/Jev）做到官方对齐，fork 起步省 6-12 个月；AGPL 保证永远开源可审计——与"用户数据主权"的产品承诺互证。
**风险**：华灯单维护者、star 少，需在 P0 阶段审计其代码质量与上游合并健康度（DIVERGENCE.md 维护良好，2026-09-03 刚合过上游，是积极信号）；构建需 de-google（stub google-services.json）。

## 4. MVP 功能优先级（调研结论）

1. 聊天记录导入（TG/MemoTrace/JSONL）+ 本地存储
2. 蒸馏引擎（分批后台 + 断点续跑 + 证据核验）→ 画像 + V3 角色卡双产出
3. 四层记忆 + 三因子召回 + 遗忘曲线 + 记忆可查看可编辑
4. 陪伴对话（复用基座全部调教能力 + 情绪连续性 + 气泡防抖）
5. 主动关怀（意愿驱动 + 时段/冷却/概率护栏 + 纪念日）
之后：表情包、语音、桌面伴侣端、外接渠道、群聊、LoRA。

## 5. 后续阅读

- 架构细则与任务分解：`../ARCHITECTURE.md`、`../tasks/TASKS.md`
- 华灯分歧地图（一手）：`D:\codex\AI_Workspace\projects\rikkahub-huadeng\DIVERGENCE.md`
- relationship-companion 引擎：`D:\codex\AI_Workspace\projects\AstrBot\relationship-companion\`（ARCHITECTURE.md / ROADMAP_V2.md）
