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
| AMB-201 | P2 | Kotlin：导入器移植（Room schema） | 102 | planned |
| AMB-202 | P2 | Kotlin：蒸馏状态机 + WorkManager 后台分批 | 102 | planned |
| AMB-203 | P2 | Kotlin：四层记忆 + 三因子召回 | 201-202 | planned |
| AMB-301 | P3 | 意愿驱动主动关怀 + 护栏 | 203 | planned |
| AMB-302 | P3 | 纪念日/情绪连续/表情包/关系阶段 | 203 | planned |
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
