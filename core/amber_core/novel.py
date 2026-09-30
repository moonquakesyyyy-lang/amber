"""小说蒸馏：把任意叙事长文本（小说）蒸馏为「多角色卡 + 共享世界书」。

与聊天记录蒸馏的差异：
- 输入不是对话而是叙事文本：无 sender/direction，按「段落消息」复用 Message 结构
  （sender_name="原文"，direction=other），蒸馏提示词与证据核验逻辑完全复用。
- 分块按字数而非条数/时间：段落聚合成 ~chunk_chars 字的块。
- 产物：从叙事中提炼人物集，每个主要角色生成一张 V3 卡；
  世界观/设定/关系/事件线进入共享世界书（可同时挂到多个助手）。

版权：工具不内置任何小说内容；用户自备文本、自产自用。
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from .schema import Block, Message

# ---------- 导入 ----------

def load_novel_text(path: str | Path) -> str:
    """TXT / EPUB → 纯文本。EPUB 按 spine 顺序抽取全部 XHTML 文本。"""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    suffix = p.suffix.lower()
    if suffix == ".txt":
        text = p.read_text(encoding="utf-8", errors="ignore")
        return _clean_text(text)
    if suffix == ".epub":
        with zipfile.ZipFile(p) as z:
            htmls = sorted(n for n in z.namelist() if n.endswith((".xhtml", ".html", ".htm")))
            parts = []
            for name in htmls:
                raw = z.read(name)
                try:
                    root = ElementTree.fromstring(raw)
                except ElementTree.ParseError:
                    continue
                # 去标签取文本：命名空间无关处理
                for el in root.iter():
                    if el.tag.rsplit("}", 1)[-1] in ("p", "h1", "h2", "h3", "div") and el.text:
                        parts.append(el.text.strip())
                    elif el.tag.rsplit("}", 1)[-1] == "title" and el.text:
                        parts.append(el.text.strip())
        return _clean_text("\n".join(parts))
    raise ValueError(f"不支持的格式：{suffix}（支持 .txt / .epub）")


def _clean_text(text: str) -> str:
    lines = [ln.strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


# ---------- 分块 ----------

def chunk_novel(text: str, chunk_chars: int = 3000) -> list[Block]:
    """按段落聚合为 ~chunk_chars 字的块；一章尽量不跨块（识别 第X章/第X回 标题行起新块）。"""
    if chunk_chars < 200:
        raise ValueError("chunk_chars must be >= 200")
    paragraphs = [p for p in text.split("\n") if p.strip()]
    chapter_re = re.compile(r"^\s*(第[零一二三四五六七八九十百千万0-9]+[章节回卷]|Chapter\s+\d+|序章|楔子|尾声)")

    blocks: list[Block] = []
    cur: list[Message] = []
    cur_len = 0
    base_ts = 1000000  # 叙事文本无时间概念，用序号充当稳定 ts

    def flush() -> None:
        nonlocal cur, cur_len
        if cur:
            blocks.append(
                Block(
                    block_id=len(blocks),
                    messages=list(cur),
                    start_ts=str(base_ts + len(blocks)),
                    end_ts=str(base_ts + len(blocks)),
                )
            )
            cur = []
            cur_len = 0

    for para in paragraphs:
        if chapter_re.match(para) and cur:
            flush()  # 章界起新块
        # 超长段落按句切分（Message 粒度=段落/句组，供证据核验定位）
        pieces = _split_long(para, 600)
        for piece in pieces:
            if cur_len + len(piece) > chunk_chars and cur:
                flush()
            cur.append(
                Message(
                    ts=str(base_ts + len(blocks)),
                    sender_id="novel",
                    sender_name="原文",
                    direction="other",
                    content=piece,
                )
            )
            cur_len += len(piece)
    flush()
    return blocks


def _split_long(para: str, max_len: int) -> list[str]:
    if len(para) <= max_len:
        return [para]
    sentences = re.split(r"(?<=[。！？!?…])", para)
    out: list[str] = []
    buf = ""
    for sen in sentences:
        if len(buf) + len(sen) > max_len and buf:
            out.append(buf)
            buf = sen
        else:
            buf += sen
    if buf:
        out.append(buf)
    return out


# ---------- 小说模式蒸馏提示词 ----------

NOVEL_SYSTEM_PROMPT = (
    "你是小说蒸馏器。下面是一部小说的连续片段（可能截取自中间，前后文缺失是正常的）。"
    "请从中提炼：\n"
    '1. characters：本片段中出现的人物（只提取有姓名/明确称谓的），每个人物输出 '
    '{"name","identity"(身份一句话),"traits"(性格特质数组,2-6条),"speaking_style"(说话风格：'
    "语气/口头禅/句式，若有直接引语务必概括其语言习惯),\"relationships\"(与其它人物的关系一句话)}。\n"
    "2. lore_candidates：世界观设定/地点/物品/规则/势力，{\"title\",\"content\",\"keys\"}。\n"
    "3. memories：重要事件与情节进展（一句话一条，含人物名）。\n"
    "4. evidence：最能代表某个角色性格或说话风格的原句，{\"quote\": \"原文片段(8-30字，逐字摘录)\","
    "\"message_index\": 该句所在段落序号(从0开始)}。\n"
    "要求：只依据片段内文本，不推测片段外剧情；quote 必须逐字摘录；人物无名可称时用其称谓。"
    "只输出一个 JSON 对象："
    '{"characters":[...],"lore_candidates":[...],"memories":[...],"evidence":[...]}'
)


def render_novel_user(block: Block) -> str:
    return "\n".join(f"[{i}] {m.content}" for i, m in enumerate(block.messages))


# ---------- 多角色拆分 ----------

def character_profile_text(chars: list[dict]) -> str:
    """把块级 characters 合并视图渲染为人物清单文本（供合并器/测试断言）。"""
    out = []
    for c in chars:
        out.append(
            f"{c.get('name','?')}（{c.get('identity','')}）："
            + "、".join(c.get("traits", []))
            + f"；风格：{c.get('speaking_style','')}"
            + (f"；关系：{c['relationships']}" if c.get("relationships") else "")
        )
    return "\n".join(out)


# ---------- 共享蒸馏流程（App 桥接与 PC 工具共用） ----------

NOVEL_EVIDENCE_PROMPT_ADDendum = (
    'evidence 每条格式改为 {"quote":...,"message_index":...,"speaker":"该句的说话人姓名，'
    '无法确定时填 null"}。'
)


def distill_novel_blocks(
    blocks,
    book_name: str,
    llm,
    max_characters: int = 5,
    progress=None,
    retry_block_ids=None,
    carry: dict | None = None,
) -> dict:
    """小说蒸馏共享实现（审查 P1-2 / Q-5）。

    carry：上次运行的部分聚合（_state_for_retry），重试 failed 块时合并，不丢已有数据。

    失败语义：
    - 单块失败跳过并计数，不中断全书；
    - 全部块失败 → 抛 RuntimeError（调用方置 job 为 failed，不产出成功产物）；
    - 部分失败 → 正常返回，report.blocks_failed 带缺失数量（调用方支持重试）。

    引文归属（Q-5）：evidence 必须带 speaker 且 speaker 在该块人物集中才归属；
    speaker 缺失或未识别的引文进入 pending_quotes（标记待核验），绝不按
    「人名出现在整块文本」猜测分配。

    retry_block_ids：重试模式，只蒸馏这些块（其它复用传入的聚合结果）。
    """
    from .distiller import extract_json, normalize_text

    todo = blocks if retry_block_ids is None else [b for b in blocks if b.block_id in retry_block_ids]
    if carry:
        char_counter = dict(carry.get("char_counter", {}))
        char_data = dict(carry.get("char_data", {}))
        lore_by_title = dict(carry.get("lore_by_title", {}))
        memories = list(carry.get("memories", []))
        seen = set(carry.get("seen", []))
    else:
        char_counter = {}
        char_data = {}
        lore_by_title = {}
        memories = []
        seen = set()
    pending_quotes: list = []
    failed_blocks: list = []
    calls = 0

    for bi, block in enumerate(todo):
        try:
            result = llm.chat(
                NOVEL_SYSTEM_PROMPT + NOVEL_EVIDENCE_PROMPT_ADDendum,
                render_novel_user(block),
                json_mode=True,
            )
            calls += 1
            raw = extract_json(result.text)
        except Exception as e:  # noqa: BLE001
            failed_blocks.append(block.block_id)
            if progress:
                progress(bi, len(todo), f"块 {block.block_id} 失败：{e}")
            continue
        norm_all = "".join(normalize_text(m.content) for m in block.messages)
        for c in raw.get("characters") or []:
            if not isinstance(c, dict) or not str(c.get("name") or "").strip():
                continue
            name = str(c["name"]).strip()
            char_counter[name] = char_counter.get(name, 0) + 1
            d = char_data.setdefault(
                name,
                {"traits": [], "quotes": [], "speaking_style": "", "identity": "", "relationships": []},
            )
            d["identity"] = d["identity"] or str(c.get("identity") or "")
            d["speaking_style"] = d["speaking_style"] or str(c.get("speaking_style") or "")
            for t in c.get("traits") or []:
                t = str(t).strip()
                if t and t not in d["traits"]:
                    d["traits"].append(t)
            rel = str(c.get("relationships") or "").strip()
            if rel and rel not in d["relationships"]:
                d["relationships"].append(rel)
        for lo in raw.get("lore_candidates") or []:
            if not isinstance(lo, dict) or not str(lo.get("content") or "").strip():
                continue
            title = str(lo.get("title") or "").strip() or str(lo["content"])[:20]
            key = normalize_text(title)
            if key and key not in lore_by_title:
                lore_by_title[key] = {
                    "title": title,
                    "content": str(lo["content"]).strip(),
                    "keys": str(lo.get("keys") or "").strip(),
                }
        for m in raw.get("memories") or []:
            m = str(m).strip()
            nm = normalize_text(m)
            if m and nm and nm not in seen:
                seen.add(nm)
                memories.append(m)
        for ev in raw.get("evidence") or []:
            if not isinstance(ev, dict):
                continue
            quote = str(ev.get("quote") or "").strip()
            nq = normalize_text(quote)
            if len(quote) < 4 or not nq or nq not in norm_all:
                continue  # 引文核验不过 → 丢弃
            speaker = str(ev.get("speaker") or "").strip()
            if speaker and speaker in char_data:
                if quote not in char_data[speaker]["quotes"]:
                    char_data[speaker]["quotes"].append(quote)
            else:
                # Q-5：无主引文标记待核验，不猜归属
                pending_quotes.append({"quote": quote, "block_id": block.block_id, "speaker": speaker or None})
        if progress:
            progress(bi, len(todo), f"块 {block.block_id} 完成")

    if todo and len(failed_blocks) == len(todo):
        raise RuntimeError(f"全部 {len(todo)} 个块均蒸馏失败，不生成产物")

    max_characters = max_characters
    top = sorted(char_counter, key=lambda n: char_counter[n], reverse=True)[:max_characters]

    entries = []
    for i, lo in enumerate(lore_by_title.values()):
        entries.append({
            "id": i,
            "keys": [lo["title"]] + [k for k in lo["keys"].split() if k],
            "content": "[设定] " + lo["title"] + "：" + lo["content"],
            "comment": lo["title"],
            "enabled": True,
            "insertion_order": 100 + i,
            "constant": False,
            "position": "before_char",
        })
    for j, m in enumerate(memories[:60]):
        hit = [n for n in top if n in m][:3]
        entries.append({
            "id": len(entries) + j,
            "keys": hit or [book_name],
            "content": "[事件] " + m,
            "comment": m[:16],
            "enabled": True,
            "insertion_order": 200 + j,
            "constant": False,
            "position": "before_char",
        })

    cards = []
    for name in top:
        d = char_data[name]
        desc = [name + "——" + (d["identity"] or "本书人物") + "。"]
        if d["traits"]:
            desc.append("性格：" + "、".join(d["traits"][:12]) + "。")
        if d["speaking_style"]:
            desc.append("说话风格：" + d["speaking_style"] + "。")
        if d["relationships"]:
            desc.append("人物关系：" + "；".join(d["relationships"][:5]) + "。")
        desc.append("你正与读者（用户）在《" + book_name + "》的世界中互动，保持人物的言行逻辑与语言习惯。")
        cards.append({
            "spec": "chara_card_v3",
            "spec_version": "3.0",
            "data": {
                "name": name,
                "description": chr(10).join(desc),
                "personality": "、".join(d["traits"][:12]),
                "scenario": "《" + book_name + "》的世界。用户是穿越进书中世界的读者。",
                "first_mes": "（" + name + " 注意到你的到来）……你是谁？为何在此？",
                "mes_example": chr(10).join("「" + q + "」" for q in d["quotes"][:6]),
                "creator_notes": "由琥珀从《" + book_name + "》蒸馏生成，证据引文已核验并归属到人物。",
                "system_prompt": "",
                "post_history_instructions": "",
                "alternate_greetings": [],
                "character_book": {"entries": []},
                "tags": ["amber", "novel", book_name],
                "extensions": {
                    "amber": {
                        "version": 1,
                        "source": "novel:" + book_name,
                        "persona_summary": desc[0],
                        "traits": d["traits"],
                        "style_examples": d["quotes"][:8],
                        "evidence_stats": {"mention_count": char_counter[name]},
                    }
                },
            },
        })

    return {
        "mode": "novel",
        "cards": cards,
        "worldbook": {"name": book_name + "·世界书", "entries": entries},
        "report": {
            "book": book_name,
            "blocks_total": len(blocks),
            "blocks_processed": len(todo),
            "blocks_done": len(todo) - len(failed_blocks),
            "blocks_failed": len(failed_blocks),
            "failed_block_ids": failed_blocks,
            "llm_calls": calls,
            "characters_found": len(char_counter),
            "memories": len(memories),
            "lore_entries": len(lore_by_title),
            "pending_quotes": pending_quotes,
            "mention_stats": {n: char_counter[n] for n in top},
        },
        "_state_for_retry": {"blocks": blocks, "char_data": char_data, "char_counter": char_counter,
                             "lore_by_title": lore_by_title, "memories": memories, "seen": seen},
        "failed_block_ids": failed_blocks,
    }
