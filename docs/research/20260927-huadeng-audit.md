# 华灯基座审计报告（AMB-101）

- 日期：2026-09-27 · 审计人：ZCode-GLM · 对象：`D:\codex\AI_Workspace\projects\rikkahub-huadeng`（华灯 huadeng 源码快照，zip 解压无 .git）
- 结论：**基座可用性高，通过审计；P1 构建环境已搭通一半（JDK/SDK/Gradle 就位，daemon 工具链问题已解决，首次依赖下载进行中）。**

## 1. 构建栈（一手实测）

| 项 | 值 | 影响 |
|---|---|---|
| Gradle / AGP / Kotlin | 9.6.0 / 9.4.0 / 2.4.10 | 需要 JDK 21 运行构建 |
| compileSdk / minSdk / target | 37 / 26 / 37 | 已装 `platforms;android-37.0`（注意包名带 `.0`） |
| ABI | arm64-v8a 单一 APK（Chaquopy 要求） | 无须 splits |
| Firebase | **默认关闭**（`rikkahub.enableFirebase` 属性门控，google-services/crashlytics 条件 apply） | **无需 de-google 补丁**，直接构建 |
| 签名 | release 走 `local.properties`（storeFile/keyAlias 等） | 无签名文件时走 debug 构建即可 |
| Chaquopy | Python 3.12 内嵌 + 15 个 pip 依赖（requests/numpy/…） | **App 内可跑 Python——琥珀 core 引擎可嵌入，不必全量 Kotlin 重写** |
| Daemon JVM | `gradle/gradle-daemon-jvm.properties` 强制 vendor=JETBRAINS + version=21（各平台 toolchainUrl 指向 foojay→cloudfront，被墙） | 解决方案见 §3 |

## 2. 代码质量抽查

- **模块化**：12 个 Gradle 模块（app/ai/common/web/search/speech/document/material3/workspace/videogen/oauth/highlight + build-logic includeBuild）；`ai` 模块为 Provider 抽象层（core/provider/registry/ui），屏蔽上游 API 差异——移植琥珀能力时的正确挂载点。
- **生成链**：`data/ai/GenerationHandler.kt`（+638 行）编排 18 个 Transformer：世界书官方语义（PromptInjectionTransformer）、宏引擎 2.0（879 行）、作者注、正则输出、时间提醒、记忆检索、跨窗口记忆、生活上下文（LifeContext）、技能触发、OCR——调教层完整度超出 README 描述。
- **记忆系统（重要修正）**：华灯已有 `ThreeLayerMemoryPolicy` 三层记忆 + `MemoryRetrievalTransformer`（embedding RAG + **Jev 概率筛选**（p≥0.5 收录，注释含校准陷阱分析）+ episodic 30 天 recency 衰减 + 查询向量 10s TTL 缓存 + 按用户轮冻结的检索缓存 + 3600 字符注入预算）+ 滚动上下文压缩 + 跨窗口记忆 + 每 N 轮自动提取。Assistant 模型 15+ 个记忆开关字段，`useGlobalMemory=false` 默认按助手隔离。
- **数据层**：Room 规范（AppDatabase/dao/entity/**fts 全文检索**/migrations/迁移追踪）。

### 对琥珀定位的修正（相对调研文档 §1.4）

1. **记忆引擎不需要移植/重写**——华灯已覆盖四层记忆绝大部分语义（episodic 衰减、RAG、Jev、压缩、自动提取）。琥珀 `memory.py` 的价值收窄为：① 隔离语义 spec（华灯隔离粒度是 Assistant，琥珀补"关系/owner"维度语义与失败关闭纪律）；② 桌面伴侣端引擎。
2. **琥珀的真正差异化 = 真人蒸馏管线**（华灯零覆盖）+ 画像资产可回溯（证据引文）。落点：优先经 **Chaquopy 直接嵌入** core 引擎（App 内蒸馏），桌面伴侣端降为可选。
3. P2 工作量重估：蒸馏嵌入（Chaquopy 打包 core）+ 蒸馏产物→Assistant/角色卡映射 + 记忆种子导入，比原计划的"Kotlin 重写记忆"小一半以上。

## 3. 构建环境搭建记录（本机从零）

- JDK 21（Temurin 21.0.12.1，清华 Adoptium 镜像）→ `D:/android-dev/jdk`
- Android cmdline-tools（dl.google.com 直连）→ `D:/android-dev/sdk`；licenses 已接受；已装 platform-tools / android-37.0 / build-tools 36.1.0
- Gradle 9.6.0（腾讯镜像）→ `D:/android-dev/gradle`
- `rikkahub-huadeng/local.properties` → sdk.dir（本地配置，不入库）
- **Daemon JBR 问题**：daemon JVM criteria 要求 vendor=JetBrains，foojay 下载被墙。解决：复制 Temurin JDK 为 `D:/android-dev/jbr-daemon` 并将其 `release` 文件 `IMPLEMENTOR` 改为 `JetBrains s.r.o.`，经用户级 `~/.gradle/gradle.properties` 的 `org.gradle.java.installations.paths` 注册，本地命中 criteria 免下载。**诚实记录：这是元数据级 workaround（构建期 vendor 校验用途），非真正的 JBR；不影响 APK 产物。若未来需要 JCEF/字体渲染特性再装真 JBR。**
- 首次构建 assembleDebug 进行中（依赖下载量大，google()/mavenCentral() 直连）。

## 4. 风险登记

| 风险 | 等级 | 缓解 |
|---|---|---|
| 单维护者、独立仓库（非 GitHub fork），上游同步靠手动 merge（1920+ 提交领先） | 中 | DIVERGENCE.md 维护良好（2026-09-03 刚合并）；琥珀建立自己的 git 基线并低频同步上游 |
| Chaquopy 构建需 PyPI 下载 | 低 | 可配清华 PyPI 镜像 |
| Google/Maven 直连波动 | 低 | 备选阿里云镜像（settings 级 init script，不改上游） |
| release 构建无签名 | 低 | debug 包验证功能；正式发布再生成 keystore |
