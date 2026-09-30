"""小说蒸馏 CLI：输入一本小说 → 输出多张角色卡 + 共享世界书。

用法：
    python core/tools/distill_novel.py --input 小说.txt --name 书名 \
        --base-url https://你的中转/v1 --api-key sk-xxx --model your-model \
        [--max-characters 5] [--max-blocks 0] [--out dist/novel]

产物（dist/novel/<书名>/）：
    角色卡-<角色名>.json × N   （SillyTavern V3，直接导入琥珀/酒馆）
    世界书-<书名>.json         （共享世界书：世界观/事件线，可挂到任意助手）
    distill-report.json        （蒸馏账本：块数/调用数/人物提及统计）

隐私：文本只发往你配置的 LLM 端点；全部产物在本机。
版权：请使用你拥有或公版的文本，产物自用。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from amber_core import novel
from amber_core.chunker import Block
from amber_core.distiller import normalize_text
from amber_core.providers import LLMClient, LLMConfig


def _parse_block(raw: dict, block: Block) -> tuple[list[dict], list[dict], list[str], int]:
    """解析块输出：人物/lore/记忆 + 证据核验（quote 须逐字命中块内文本）。"""
    chars = []
    for c in raw.get("characters") or []:
        if isinstance(c, dict) and str(c.get("name") or "").strip():
            chars.append(
                {
                    "name": str(c["name"]).strip(),
                    "identity": str(c.get("identity") or "").strip(),
                    "traits": [str(t) for t in (c.get("traits") or []) if str(t).strip()],
                    "speaking_style": str(c.get("speaking_style") or "").strip(),
                    "relationships": str(c.get("relationships") or "").strip(),
                }
            )
    lore = []
    for lo in raw.get("lore_candidates") or []:
        if isinstance(lo, dict) and str(lo.get("content") or "").strip():
            lore.append(
                {
                    "title": str(lo.get("title") or "").strip() or str(lo["content"])[:20],
                    "content": str(lo["content"]).strip(),
                    "keys": str(lo.get("keys") or "").strip(),
                }
            )
    memories = [str(m) for m in (raw.get("memories") or []) if str(m).strip()]

    norm_messages = [normalize_text(m.content) for m in block.messages]
    whole = "".join(norm_messages)
    verified_quotes: list[str] = []
    for ev in raw.get("evidence") or []:
        if not isinstance(ev, dict):
            continue
        quote = str(ev.get("quote") or "").strip()
        if len(quote) < 4:
            continue
        nq = normalize_text(quote)
        if nq and (nq in whole):
            verified_quotes.append(quote)
    return chars, lore, memories, verified_quotes


def distill_novel(
    text: str,
    book_name: str,
    llm: LLMClient,
    max_characters: int = 5,
    max_blocks: int = 0,
    chunk_chars: int = 3000,
    progress=None,
) -> dict:
    """PC 工具入口：委托 amber_core.novel.distill_novel_blocks 共享实现。"""
    blocks = novel.chunk_novel(text, chunk_chars=chunk_chars)
    if max_blocks > 0:
        blocks = blocks[:max_blocks]
    if not blocks:
        raise ValueError("小说文本为空或无法分块")
    return novel.distill_novel_blocks(blocks, book_name, llm, max_characters=max_characters, progress=progress)


def _name_keys(text: str, names: list[str]) -> list[str]:
    """事件句中出现的角色名作为触发词。"""
    return [n for n in names if n in text]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="小说文件（.txt/.epub）")
    ap.add_argument("--name", required=True, help="书名（用于卡与世界书命名）")
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--api-key", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--max-characters", type=int, default=5, help="输出角色卡数（按提及度取前 N）")
    ap.add_argument("--max-blocks", type=int, default=0, help="限制蒸馏块数（0=全书；试跑建议 5）")
    ap.add_argument("--chunk-chars", type=int, default=3000)
    ap.add_argument("--out", default="dist/novel", help="输出目录")
    a = ap.parse_args()

    text = novel.load_novel_text(a.input)
    print(f"[novel] 文本 {len(text)} 字")
    llm = LLMClient(
        config=LLMConfig(base_url=a.base_url, api_key=a.api_key, model=a.model),
        temperature=0.3,
    )

    def progress(i: int, total: int, msg: str) -> None:
        print(f"[novel] {msg}")

    result = distill_novel(
        text, a.name, llm,
        max_characters=a.max_characters, max_blocks=a.max_blocks,
        chunk_chars=a.chunk_chars, progress=progress,
    )

    out_dir = Path(a.out) / a.name
    out_dir.mkdir(parents=True, exist_ok=True)
    for card in result["cards"]:
        p = out_dir / f"角色卡-{card['data']['name']}.json"
        p.write_text(json.dumps(card, ensure_ascii=False, indent=1), encoding="utf-8")
        mention = card["data"]["extensions"]["amber"]["evidence_stats"]["mention_count"]
        print(f"[novel] {p.name}  (提及 {mention} 次)")
    wb = out_dir / f"世界书-{a.name}.json"
    wb.write_text(json.dumps(result["worldbook"], ensure_ascii=False, indent=1), encoding="utf-8")
    rep = out_dir / "distill-report.json"
    rep.write_text(json.dumps(result["report"], ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[novel] {wb.name}（{len(result['lorebook']['entries'])} 条） / distill-report.json")
    print(f"[novel] 全部产物在：{out_dir}——把角色卡和世界书导入琥珀即可开聊")


def json_import_ns():
    from amber_core.card import AMBER_NS

    return AMBER_NS


if __name__ == "__main__":
    main()
