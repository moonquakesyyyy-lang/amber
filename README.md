# 琥珀（Amber）

> 本地优先的 AI 情感陪伴软件 —— 用你自己的聊天记录，亲手蒸馏出属于你的数字角色。

**琥珀** 让你把导出的聊天记录（微信 / QQ / Telegram / 通用格式）在**本地**蒸馏成一个有据可查的数字角色：说话风格、行为习惯、共同记忆、忌讳与幽默——全部结构化保存、可查证、可修正，并兼容 SillyTavern 角色卡生态。

## 核心理念

- **数据主权**：聊天记录、蒸馏结果、记忆全部保存在你的设备上。开发者不设云端、不经手任何数据；LLM 调用走你自己的 API key（或本地 Ollama / vLLM，零外发）。
- **渠道无关**：软件本身就是聊天界面（Android 优先）。微信机器人、QQ、Telegram 只是可选外接渠道——核心能力不依赖任何渠道。
- **蒸馏有据**：每条画像都挂证据引文，可回溯到原始记录；可解释、可修正。
- **记忆隔离**：角色之间记忆严格隔离（SQL 层强制），共享知识按角色分组。
- **调教生态**：角色卡 V2/V3 导入导出、世界书（官方语义）、宏引擎、作者注、注入位置——继承酒馆生态全部调教手段。

## 架构总览

见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)；决策依据与竞品调研见 [docs/research/20260927-fusion-research.md](docs/research/20260927-fusion-research.md)。

- **App**（主体）：华灯（rikkahub huadeng fork）基座，Kotlin/Compose，本地 Room 存储
- **core/**：核心引擎 Python 参考实现（导入/分块/蒸馏/角色卡/记忆），为 Kotlin 移植提供可运行 spec，同时直接服务桌面伴侣端
- **桌面伴侣端**（规划）：重型蒸馏分担

## 快速开始（核心引擎参考实现）

```bash
pip install -e .
pytest core/tests -q
```

```python
from amber_core.importer import import_file
from amber_core.chunker import chunk_messages
from amber_core.distiller import DistillPipeline
from amber_core.card import profile_to_card_v3

messages = import_file("export.json", source="telegram")   # 统一内部格式
blocks = chunk_messages(messages, block_size=100)          # 分块
pipeline = DistillPipeline(llm=my_openai_compatible_client) # 用户自持 key
run = pipeline.run(blocks, "她的名字")                       # 断点续跑、证据核验
card = profile_to_card_v3(run.profile)                     # SillyTavern V3 卡
```

## 许可证

AGPL-3.0（基座华灯/RikkaHub 为 AGPL-3.0；本仓库承袭）。见 [LICENSE](LICENSE)。

## 状态

P0 引擎参考实现进行中，任务状态见 [docs/tasks/TASKS.md](docs/tasks/TASKS.md)。
