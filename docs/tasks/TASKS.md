# 琥珀（Amber）任务单

状态主流程：`planned → ready → in_progress → review → accepted`；受阻 `blocked`；方案被替代 `superseded`。
唯一状态源：本文件第 2 节。认领后必须登记执行者与基线。

## 1. 阶段

| 阶段 | 目标 | 退出条件 |
|---|---|---|
| P0 引擎参考实现 | Python `core/`：导入/分块/蒸馏/角色卡/记忆 + 测试 | pytest 全绿；ruff 全绿；蒸馏管线断点续跑与隔离有污染探针 |
| P1 基座审计与 fork | 华灯代码质量审计、de-google 构建、fork 策略 | 本机可构建 APK；上游合并手册更新 |
| P2 Kotlin 移植 | 核心层 A/B/C 进 App（Room+状态机） | 真机导入→蒸馏→对话闭环 |
| P3 情感产品层 | 主动关怀/纪念日/情绪连续/表情包/关系阶段 | 护栏参数全量可配；观察期达标 |
| P4 桌面伴侣端 | Python 引擎 GUI/CLI + 文件互通 | 数千条记录蒸馏演练通过 |
| P5 外接渠道 | 微信/QQ/TG bot 接入器 | 渠道故障不影响 App 本体 |

## 2. 任务状态表

| ID | 阶段 | 任务 | 依赖 | 状态/执行者/证据 |
|---|---|---|---|---|
| AMB-001 | P0 | 项目骨架：README/LICENSE(AGPL-3.0)/pyproject/文档 | — | accepted / ZCode-GLM / 2026-09-27 |
| AMB-002 | P0 | `core/schema.py` 数据模型（统一消息/画像/记忆/卡） | 001 | accepted / ZCode-GLM / 2026-09-27 |
| AMB-003 | P0 | `core/importer.py` 三个导入适配器 | 002 | accepted / ZCode-GLM / 2026-09-27 |
| AMB-004 | P0 | `core/chunker.py` 分块器 | 002 | accepted / ZCode-GLM / 2026-09-27 |
| AMB-005 | P0 | `core/distiller.py` 蒸馏管线（可插 LLM，断点续跑，证据核验） | 004 | accepted / ZCode-GLM / 2026-09-27 |
| AMB-006 | P0 | `core/card.py` CCv3 导出/导入映射 | 002 | accepted / ZCode-GLM / 2026-09-27 |
| AMB-007 | P0 | `core/memory.py` 四层记忆 + 隔离 + 三因子召回 | 002 | accepted / ZCode-GLM / 2026-09-27 |
| AMB-008 | P0 | 测试套件 + 污染探针 + ruff 门禁 | 003-007 | accepted / ZCode-GLM / 2026-09-27：pytest 22 passed / 0 failed；ruff All checks passed |
| AMB-101 | P1 | 华灯基座审计（代码质量/合并健康度/单维护者风险） | — | accepted / ZCode-GLM / [审计报告](../research/20260927-huadeng-audit.md) 2026-09-27 |
| AMB-102 | P1 | fork + de-google 构建 + CI | 101 | review / ZCode-GLM / 2026-09-27 本机构建通过（app-debug.apk 144M）；de-google 无需补丁（Firebase 属性门控默认关）；fork git 基线与 CI 待用户 GitHub 账号授权后建立 |
| AMB-103 | P1.5 | AstrBot 资产迁移：relationship_companion.db → 琥珀角色卡 | — | accepted / ZCode-GLM / `core/tools/import_from_astrbot.py`（提交 d2984e6）；实测产出小美卡（901 条世界书含证据触发词、38 记忆、59 边界、画像全量入 extensions.amber）与小夏卡；用户路径=传 json 到手机→助手导入 |
| AMB-201 | P2 | Kotlin：导入器移植（Room schema） | 102 | accepted（形态修正）/ ZCode-GLM / 2026-09-27 导入器不重写——amber_core.importer 经 Chaquopy 直接进 App（`app/src/main/python/amber_core`） |
| AMB-202 | P2 | Kotlin：蒸馏状态机 + WorkManager 后台分批 | 102 | accepted（形态修正）/ ZCode-GLM / 2026-09-27 `amber_bridge.py`（后台线程 job + 轮询）+ `AmberDistillManager`（单例 StateFlow）+ `SettingAmberPage`（SAF 选文件/角色名/LLM 配置/进度/产物），编译+全量构建通过 |
| AMB-203 | P2 | Kotlin：四层记忆 + 三因子召回 | 201-202 | review / ZCode-GLM / 2026-09-27 审计修正：华灯记忆系统（三层+Jev+衰减+压缩）已覆盖大部分语义，本任务收窄为"蒸馏记忆种子→华灯记忆库自动注入"；卡片内 lore/mes_example 已随导入生效，种子自动注入待做 |
| AMB-301 | P3 | 意愿驱动主动关怀 + 护栏 | 203 | accepted / ZCode-GLM / 2026-09-27 华灯已有 PASS/JUMP 意愿模型；新增硬护栏（时段窗/每日上限/冷却/概率，本地判定先于 LLM，被拦零成本）+ 设置页 UI；默认值兼容旧配置 |
| AMB-302 | P3 | 纪念日/情绪连续/表情包/关系阶段 | 203 | planned / — / 需新 Room 实体与产品 UI，下一大块 |
| AMB-401 | P4 | 桌面伴侣端 CLI + 文件互通格式 | 005 | planned |
| AMB-501 | P5 | 外接渠道接入器 | 203 | planned |

## 3. 本轮执行记录（2026-09-27，ZCode-GLM）

- 认领 AMB-001 至 AMB-008（P0 全部），基线=新仓库初始化。
- 交付：`core/` 七模块（schema/importer/chunker/distiller/card/memory/providers）+ `tests/` 五套件。
- 自检发现并修复的问题（目标模式自检自查记录）：
  1. SYSTEM_PROMPT 的 `.format` 把 JSON 示例大括号当占位符 → KeyError，改为 `{{}}` 转义；
  2. 中文引号 `""''` 写在双引号 raw string 内导致字符串提前闭合、正则失效 + SyntaxWarning → 改用 `[\s\W_]+` Unicode 语义类；
  3. `CompanionProfile` 缺 `uncertainties` 字段 → 补；
  4. 角色卡 roundtrip 丢失 `evidence_stats` → card_to_profile 补恢复；
  5. JSONL 坏行硬失败改为宽容跳过（Telegram 官方导出亦有非法 JSON 坑）；
  6. 零相关度记忆进入召回结果 → recall 过滤 `rel<=0`（宁缺勿滥）；
  7. FakeLLM 耗尽抛 ProviderError 不被蒸馏器捕获 → 捕获并补记账；失败调用计入 usage 账本（账本纪律：已发起调用必须记账）；
  8. resume 与原 run 为同一对象，usage 为累计口径 → 测试改为增量断言；
  9. ruff E501/UP031/B007 清零（line-length 120、f-string 化、未用循环变量）。
- 终态：**pytest 22 passed / 0 failed / 0 errors；ruff All checks passed**。
- 未决：软件名"琥珀"为暂定代号，待用户拍板；P1（AMB-101/102）需 Android 构建环境，本机暂无 SDK；华灯残骸目录（gh 直连失败产物）待进程释放后清理。

## 4. P1 执行记录（2026-09-27，ZCode-GLM）

- **AMB-101 审计结论**（详见审计报告）：基座通过审计。最重要发现：① Firebase 默认关闭（属性门控），无需 de-google 补丁；② Chaquopy 内嵌 Python 3.12——琥珀 core 引擎可 App 内直跑，P2 工作量减半；③ 华灯记忆系统（三层记忆+Jev 筛选+episodic 衰减+滚动压缩+RAG）已覆盖琥珀 memory 层大部分语义，琥珀差异化收窄为"真人蒸馏管线 + 画像证据可回溯 + 关系级隔离 spec"。
- **AMB-102 构建环境**（本机从零）：JDK 21（清华 Adoptium 镜像）→ `D:/android-dev/jdk`；cmdline-tools + platform-tools + android-37.0 + build-tools 36.1.0 + NDK 28.2 + CMake 3.22.1（dl.google.com 直连，autoSDK 自动补齐）；Gradle 9.6.0（腾讯镜像）。
- **自检自查中解决的三道构建障碍**：
  1. daemon JVM criteria 强制 vendor=JetBrains（foojay→cloudfront 被墙）→ 复制 Temurin JDK 副本改 release 元数据为 JetBrains s.r.o.，经 `org.gradle.java.installations.paths` 本地命中（元数据级 workaround，已如实记录于审计报告）；
  2. `kotlin-compiler-embeddable-2.4.10.jar` 在 mavenCentral 302 到 GitHub 被墙 → gh-proxy 拉取 jar+pom 补入 mavenLocal（settings 已含 mavenLocal()）；
  3. GitHub archive zip 不含 submodule（material-color-utilities 的 kotlin 源码缺失导致 material3 模块编译失败）→ gh-proxy 拉取 submodule 源码补位（43 个 .kt 文件）。
- **终态**：`gradle assembleDebug` **BUILD SUCCESSFUL**（385 tasks），产物 `app-debug.apk` 144MB（含 Python 运行时）。debug 包未签名可直接安装验证；release 需 local.properties 配置 keystore。
- 移交用户：GitHub 账号授权后建立琥珀 fork 的 git 基线与 CI（gh-proxy 无法替代 gh 登录态）；APK 真机安装验证。

## 5. P2+P3 执行记录（2026-09-27，ZCode-GLM）

- 用户指示"彻底做完之前无需验收，自主推进"。华灯目录 `git init` 建本地 fork 基线 `a2976bd`（无需 GitHub 授权），琥珀集成提交 `28299ce`。
- **AMB-201/202（蒸馏嵌入，形态按审计修正）**：
  - `app/src/main/python/amber_core/`：core 引擎 8 个模块整体进 Chaquopy 源码目录（纯标准库零适配成本）；
  - `amber_bridge.py`：后台线程 job 模型（distill_start/status/result），进度=块级状态机渲染，异常全兜底可被 Kotlin 读取；
  - `AmberDistillManager.kt`：进程级单例（页面重建不丢 job），SAF Uri→cache 拷贝、Python 主线程初始化、600ms 轮询、卡片产物写 `getExternalFilesDir/amber_exports`；
  - `SettingAmberPage.kt`：隐私声明/选文件/角色名与自称谓/LLM 配置（SharedPreferences 持久化）/进度条/完成摘要/错误展示；
  - 接线：`RouteActivity`（Screen+entry）、`SettingPage` 菜单、strings（en+zh，其余语言 fallback）。
- **AMB-301（主动消息护栏）**：`ProactiveMessageSetting` +5 字段（默认值兼容旧配置）；`ProactiveMessageTriggerService` 在任何 LLM 调用前做本地硬护栏（时段窗/每日上限/冷却/概率，`recordSent` 以实际发送记账，键带自然日自动重置）；设置页新增护栏 CardGroup。与华灯既有 PASS/JUMP 意愿模型叠加：先硬护栏省钱，再 AI 意愿决定说话/跳过。
- **自检自查修复**：icons FileImport 不存在→DatabaseImport（jar 内枚举核实）；nestedScroll/PaddingValues.plus 缺 import；File.apply 嵌套 use 类型推断失败→平铺 use；Triple 字面量 vs R.string 资源 ID；ProactiveMessageSetting 缺 import。
- **终态**：`assembleDebug` BUILD SUCCESSFUL（148M APK，含蒸馏页+护栏）；Kotlin 编译零警告级错误。
- **AMB-203 收窄缺口**：蒸馏产物 memories 自动注入华灯记忆库待做（当前卡内 lore/mes_example 随导入生效）；AMB-302（纪念日/关系阶段实体）planned。

## 6. 身份化改造记录（2026-09-27，ZCode-GLM；华灯 fork 提交 6ab1adc）

用户指出"应用还是华灯、残留华灯个人信息"。全面盘点后逐项改造：
- 应用名：Lantern/华灯 → **Amber/琥珀**（en/zh/zh-rTW）
- 图标：PIL 生成琥珀主题（amber-600 底 + 白"琥"字），自适应 foreground/background + legacy 圆形全密度替换
- applicationId：`me.rerere.rikkahub.huadeng` → `com.amber.companion`（新包名可与华灯共存；Manifest 全部走 ${applicationId} 占位，零硬编码）
- 关于页：标题 Amber；移除 rikka-ai.com 官网行；上游链接保留并改语义为 AGPL 合规致谢（华灯→RikkaHub 链式留档）；版本文案"琥珀（基于华灯/RikkaHub）"
- 捐赠页：设置页入口移除（上游作者收款链接不再可达）
- 更新检查：UpdateChecker.checkUpdate 短路停用（原指向 MiaoWuNYA 仓库），UI 零打扰
- 残留扫描：MiaoWuNYA/afdian/reovo/rikka-ai.com/QQ 群全仓 grep 清零
- **新发现**：华灯已有 `CoupleSpaceTools.kt`（情侣空间工具），AMB-302 的纪念日/生活空间部分能力现成
- 终态：BUILD SUCCESSFUL；桌面 `琥珀-distill-debug.apk` 已更新

## 7. AMB-104 执行记录（2026-09-28，ZCode-GLM；华灯 fork 提交 ec287f2）

- 用户问"能否 App 内直接选取下载角色卡"。调研：**Chub API 返回 "This service is not available in your country"（地区屏蔽），不可作内置通道**；JanitorAI 非公开 API；Discord 类脑无法程序接入。
- **落地通道**：GitHub 公开合集仓 `leigegehaha/sillytavernassets`（172★，32 分类/数百张中文卡）+ gh-proxy/ghproxy.net/ghfast.top 多镜像容错（与 UpdateChecker 同思路）；contents API 列目录 + raw 下载，实测中文路径 URL 编码、PNG tEXt(chara) 解析均通过。
- **实装**：`data/market/CardMarketClient.kt`（多镜像 listDir/download/路径编码）+ `ui/pages/market/CardMarketPage.kt`（分类浏览→卡列表→搜索→点卡片下载并直接走 `importFromString` 导入为助手，进度/错误/toast 完整）；助手页顶栏新增"卡市场"入口（Package 图标）；`importFromString` private→internal 复用；顺手放宽 json 导入的 MIME 过滤（octet-stream，解决微信传 json 在选择器里消失的问题）。
- 自检修复：XML 裸 `&`、unused/缺失 import（JsonObject/contentOrNull）、listDir 返回类型注解、Package/plus import、Store0 图标不存在换 Package。
- 终态：assembleDebug BUILD SUCCESSFUL；桌面 APK 已更新（19:06）。
- 已知边界：卡库内容来自社区公开仓库（含成人题材分类），页面已提示"请自行甄别"；缩略图未加载（MVP 只列名称，省流量）；更换/追加卡源仓库只需改 CardMarketClient 的 REPO 常量。

## 8. 自动更新机制记录（2026-09-28，ZCode-GLM；华灯 fork 提交 80d53b9）

- 用户问"软件不能自动拉取更新吗"。答：之前身份化时更新通道随华灯作者仓库一并停用（REPO 留空=静默禁用，UI 零打扰）。
- **本轮恢复全机制**：UpdateChecker 完整保留华灯成熟实现（GitHub Releases API 主源 → update.json 兜底 [jsDelivr 国内直连第一优先 + ghproxy 镜像] → 下载前 HEAD 探路 + DownloadManager 断点续传）；REPO 常量留空即禁用，**建仓后填 owner/repo 一行即点亮**。
- **发版管线全通**：生成琥珀专属签名 keystore（D:/android-dev/amber-release.jks，CN=Amber，不入库）→ local.properties 签名配置 → `assembleRelease` 实测成功（app-release.apk 101M，R8 后比 debug 小 47M，apksigner 验签通过）→ `core/tools/release.py` 一键发版（构建+update.json 生成+gh 发布指引）。
- **待用户一步**：GitHub 建仓（建议名 amber）+ `gh auth login` 授权；之后 `python core/tools/release.py --repo <用户名>/amber` 即完成首次正式发版，App 内更新检查自动点亮。

## 9. 卡市场通道重做（2026-09-29，华灯 fork 提交见 fork 仓 log）

- 用户真机反馈：卡市场"所有镜像均不可达"（gh-proxy 系镜像在手机运营商网络下不可达，PC 宽带可达——网络环境差异）。
- **v2 方案**：卡库索引静态化（`market.json`，1535 张卡/32 分类，构建期离线生成入库）+ jsDelivr CDN 拉取（国内可达性最好，PC+真机链路验证）+ gh-proxy/raw 兜底；每张卡自带 4 候选下载 URL 逐个容错。
- 发版 v2.6.1-amber.2 (231)：Release + update.json 已更新，jsDelivr 已生效。
- 经验沉淀：手机网络 ≠ PC 网络，镜像通道必须真机验证；静态索引比动态 API 少 2/3 请求数且可 CDN 缓存。

## 10. 角色卡导入一键入口（2026-09-29，v2.6.2-amber.3 / build 232）

- 用户反馈找不到角色卡导入位置（原入口藏在"新建助手"弹窗底部，且不叫导入）。
- **改动**：助手页顶栏新增「角色卡导入」按钮（Download04 图标）→ 底部面板直接选 PNG/JSON/网址链接导入，导入即建助手（世界书一并入库），不再依赖"新建助手"流程；面板内含说明文案。
- 发版 v2.6.2-amber.3：Release + update.json 已更新。
- 注：自动更新提示位置在聊天页左侧抽屉顶部（华灯原设计，非弹窗）；旧 debug 版（2.5.4.16）更新通道是禁用状态，需手动装一次正式版。

## 11. 手动检查更新入口（2026-09-29，v2.6.3-amber.4 / build 233）

- 用户真机：抽屉无更新卡（截图证实连"检查失败"红卡也没有）→ 自动通道状态不可观测（Loading 静默/条件分支/手机网络到 GitHub API 时通时断）。
- **改动**：UpdateChecker 暴露 `manualCheck()`（绕过 Loading 静默，返回结果或抛出具体失败源原因）；关于页新增「检查更新」区块——点按当场显示：最新版本号/更新日志/失败原因，可点按直接调 downloadUpdate 下载安装。
- 发版 v2.6.3-amber.4（Release + update.json）。
- 更新提示卡片位置：聊天页左抽屉顶部（华灯原设计）；手动入口：设置→关于→检查更新。

## 12. 小说蒸馏（AMB-106，2026-09-29，用户新想法落地 P0/PC 端）

- 用户想法：蒸馏一本小说 → 代入角色与 AI 对话，沉浸式体验阅读。
- **交付（PC 端闭环）**：
  - `core/amber_core/novel.py`：TXT/EPUB 导入、按字数+章界分块（段落消息复用 Message 结构）、小说模式蒸馏提示词（人物集/世界观/事件线/证据引文）
  - `core/tools/distill_novel.py`：CLI——小说 → N 张角色卡（按人物提及度排序）+ 共享世界书（设定+事件线，可挂任意助手）+ 蒸馏账本；证据核验复用（引文逐字命中原文）
  - `core/tests/test_novel.py`：6 项（导入/分块/端到端/人物拆分/卡结构/EPUB），pytest 28/28 全绿 + ruff 全绿
- **用法**：`python core/tools/distill_novel.py --input 书.txt --name 书名 --base-url <中转> --api-key <key> --model <模型>`（产物 dist/novel/<书名>/，角色卡+世界书导入琥珀即玩；支持 --max-blocks 5 试跑）
- 版权：工具不内置内容，用户自备文本自用。
- 待做：App 内"小说模式"蒸馏页开关（AMB-107 planned）；蒸馏指定"代入角色"引导。

## 13. AMB-107 小说蒸馏进 App（2026-09-30，v2.7.0-amber.6 / build 235）

- novel.py 同步进 Chaquopy（app/src/main/python/amber_core/）；amber_bridge 双模式（chat/novel）——novel 产物=多角色卡（按提及度排序）+ 共享世界书（设定+事件线），世界书内嵌首卡随导入自动创建。
- 蒸馏页双模式 FilterChip（聊天记录蒸馏/小说蒸馏）；novel 完成态显示产出卡数 + 「全部导入为助手」按钮（循环 importFromString + addLorebooks）。
- 随版包含：更新下载全量镜像候选提速（gh-proxy.com 置首）。
- 发版 v2.7.0-amber.6（Release + update.json + 桌面）。
- 教训：长 Python 补丁禁用 heredoc（引号嵌套吞 EOF），一律 Write 脚本文件执行；临时补丁文件勿入库。
- 待做：代入角色引导（选"我扮演谁"）；剧情推进模式。

## 14. 审查整改（2026-09-30，v2.7.1-amber.7 / build 236；基线 v2.7.0-amber.6/235）

### 修改记录（顺序与审查单一致）

| # | 项 | 修复位置 | 验证 | 测试 |
|---|---|---|---|---|
| 1 | 导入格式 | `AmberDistillManager.copyToCache/queryDisplayName`（保留原始文件名+扩展名）；`importer.sniff_format`（白名单预检+明确报错） | 5 类文件扩展名保留；docx/无扩展名给出指引性报错 | `test_sniff_format_*`（3 项） |
| 2 | 任务状态 | `novel.distill_novel_blocks`（全失败抛 RuntimeError；blocks_done/blocks_processed/blocks_failed 分列；failed_block_ids）；bridge `distill_retry`（chat=resume、novel=carry 合并重试） | 全失败抛错不产产物；部分失败 report 带缺失；重试只跑失败块 | `test_all_blocks_failed_raises` / `test_partial_failure_reports_missing` |
| 3 | 敏感数据备份 | `res/xml/data_extraction_rules.xml`+`backup_rules.xml`（排除 database/sharedpref/datastore/amber_exports/distill 全部敏感域）；`data/amber/AmberSecrets.kt`（AndroidKeyStore AES-GCM，密文 enc:v1: 格式，明文自动迁移） | lint 通过（cache domain 无效已修）；key 读写走加解密 | 备份规则 lint 构建验证 |
| 4 | 共享世界书 | bridge novel 产物卡不内嵌世界书；`SettingAmberPage` 导入全部先 addLorebooks(worldbook) 得 ids，再绑定全部角色 | 数据结构测试：世界书独立、卡内嵌为空 | `test_worldbook_separate_from_cards` |
| 5 | 引文归属 | `NOVEL_SYSTEM_PROMPT` evidence 加 speaker 字段；`distill_novel_blocks` 只按 speaker 精确归属，无主引文进 pending_quotes | speaker 命中归卡；无主标待核验 | `test_distill_end_to_end`（pending 断言） |
| 6 | 导出覆盖 | `saveCard`：任务子目录 `amber_exports/task_<ts>/`，卡(worldbook/ cards 分目录)命名，冲突追加序号 | 同名角色/“世界书”名不覆盖 | 目录化逻辑（构建+真机项） |
| 7 | 蒸馏对象 | `importer.inspect_file`（说话人统计+样例）；bridge `inspect_file`+target_sender 重打 direction；蒸馏页删除“你的名字”文本框 → 自动检视+点选蒸馏对象 | 说话人列表/条数/样例正确；target 重打 direction | `test_inspect_file_senders_and_samples` |

### 验收表（真机项待用户执行）

| 测试场景 | 预期 | 实际 | 状态 |
|---|---|---|---|
| CSV/JSONL/TG JSON 从 App 选文件 | 保留后缀进入解析 | pytest sniff/inspect 5 项绿；Kotlin queryDisplayName 编译验证 | ✅（自动化） |
| 不支持格式 | 明确提示 | sniff_format 报“不支持的文件格式…支持…” | ✅（自动化） |
| 错误 Key / 断网 / 部分失败 / 全部失败 | 状态正确；全失败不产产物 | pytest 4 项绿（RuntimeError/failed_ids/分列统计） | ✅（自动化） |
| 导入 3 角色绑定同一世界书 | 世界书数量=1 | 数据结构测试绿；真机重复创建验证 | ⏳ 待真机 |
| 小红对白只进小红卡 | 引文按 speaker 归属 | pytest speaker/pending 断言绿 | ✅（自动化） |
| 两本书同名角色 / 角色名“世界书” | 旧卡完整保留 | 任务子目录+分目录+序号逻辑；真机验证 | ⏳ 待真机 |
| 开始前展示双方样例并点选对象 | 画像来自所选对象 | inspect 测试绿；真机 UI 验证 | ⏳ 待真机 |
| 真机全流程：选文件→蒸馏→导入→绑定→对话 | 全链路 | — | ⏳ 待真机 |
| 切后台/重建/进程回收 | 失败恢复方式明确 | 任务在 Chaquopy 进程内，进程回收即中断；已产出文件保留于 amber_exports/task_*；重进页面可对失败任务点重试（内存态） | ⏳ 待真机；持久化重试列 AMB-109 |

### 测试与文档

- pytest **34 passed / 0 failed**（新增 test_review_fixes.py 6 项 + test_novel.py 更新）；ruff 全绿
- 本文件与 README 已同步实际测试数量与状态
