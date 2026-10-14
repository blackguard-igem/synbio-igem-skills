#!/usr/bin/env python3
"""Original local JSON-to-cue-card generator. Python >= 3.10; PDF needs ReportLab."""
from __future__ import annotations

import argparse
import html
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile

VERSION = "1.1.0"
MM = 72 / 25.4
MARGIN = 8 * MM
PALETTE = ("#176B70", "#895627", "#644A83", "#345D8A")


def text_value(value, label, maximum=30000, optional=False):
    if not isinstance(value, str) or (not optional and not value.strip()):
        raise ValueError(f"{label} must be a {'nonempty ' if not optional else ''}string")
    if len(value) > maximum:
        raise ValueError(f"{label} is too long (maximum {maximum} characters)")
    if any((ord(c) < 32 and c not in "\n\t\r") or 0xD800 <= ord(c) <= 0xDFFF for c in value):
        raise ValueError(f"{label} contains unsupported control characters")
    return value.replace("\r\n", "\n").replace("\r", "\n").replace("\t", "    ").strip()


def load_input(path):
    if path.stat().st_size > 5_000_000:
        raise ValueError("Input exceeds 5 MB")
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("Input must be a JSON object")
    unexpected = set(data) - {"version", "deck_title", "cards"}
    if unexpected:
        raise ValueError(f"Unknown input fields: {sorted(unexpected)}")
    if data.get("version") != "1.0":
        raise ValueError('Input version must be "1.0"')
    title = text_value(data.get("deck_title"), "deck_title", 120)
    cards = data.get("cards")
    if not isinstance(cards, list) or not 1 <= len(cards) <= 500:
        raise ValueError("cards must contain 1 to 500 cards")
    normalized = []
    for number, card in enumerate(cards, 1):
        label = f"Card {number}"
        if not isinstance(card, dict):
            raise ValueError(f"{label} must be an object")
        unexpected = set(card) - {"title", "speaker", "body", "notes", "source"}
        if unexpected:
            raise ValueError(f"{label} unknown fields: {sorted(unexpected)}")
        speakers = card.get("speaker")
        if isinstance(speakers, str):
            speakers = [speakers]
        if not isinstance(speakers, list) or not 1 <= len(speakers) <= 12:
            raise ValueError(f"{label} speaker must be a name or an array of 1 to 12 names")
        speakers = list(dict.fromkeys(text_value(s, f"{label} speaker", 40) for s in speakers))
        normalized.append({
            "id": f"C{number:03d}",
            "title": text_value(card.get("title"), f"{label} title", 100),
            "speaker": speakers,
            "body": text_value(card.get("body"), f"{label} body"),
            "notes": text_value(card.get("notes", ""), f"{label} notes", 10000, True),
            "source": text_value(card.get("source"), f"{label} source", 2000),
        })
    return {"version": "1.0", "deck_title": title, "cards": normalized}


def make_metrics(args, data):
    if args.format == "html":
        # Conservative one-em cell width, avoiding a platform font dependency.
        return lambda text, size: len(text) * size * 1.04, None
    if not args.font:
        raise ValueError("PDF requires --font with a local Chinese TrueType font")
    font_path = Path(args.font).resolve()
    if not font_path.is_file():
        raise ValueError(f"Font does not exist: {font_path}")
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except ImportError as exc:
        raise ValueError("PDF needs ReportLab: python -m pip install -r requirements.txt") from exc
    try:
        font = TTFont("CueFont", str(font_path), subfontIndex=args.font_index)
        pdfmetrics.registerFont(font)
    except Exception as exc:
        raise ValueError(f"Unable to load TrueType font: {exc}") from exc
    visible_text = "来源：见的完整来源提示：发言人·续卡结束页 /0123456789Cindex.html"
    visible_text += data["deck_title"]
    for card in data["cards"]:
        visible_text += card["title"] + " / ".join(card["speaker"]) + card["body"] + card["notes"] + card["source"]
    missing = sorted({c for c in visible_text if not c.isspace() and ord(c) not in font.face.charToGlyph})
    if missing:
        codes = ", ".join(f"{c} (U+{ord(c):04X})" for c in missing[:12])
        raise ValueError(f"Font is missing characters: {codes}")
    return lambda text, size: pdfmetrics.stringWidth(text, "CueFont", size), "CueFont"


def wrap_text(text, width, size, measure):
    """Wrap without deleting characters; prefer Latin word boundaries when possible."""
    result = []
    for paragraph in text.split("\n"):
        if not paragraph:
            result.append("")
            continue
        current = ""
        for char in paragraph:
            if measure(char, size) > width:
                raise ValueError("A character cannot fit the available page width")
            if current and measure(current + char, size) > width:
                space = current.rfind(" ")
                if space > len(current) // 2:
                    result.append(current[: space + 1])
                    current = current[space + 1 :] + char
                else:
                    result.append(current)
                    current = char
            else:
                current += char
        if current:
            result.append(current)
    return result


def layout_deck(data, args, measure):
    width, height = args.width_mm * MM, args.height_mm * MM
    inner = width - 2 * MARGIN
    body_size = args.body_pt
    pages = []
    for card in data["cards"]:
        titles = wrap_text(card["title"], inner, 16, measure)
        if len(titles) > 2:
            raise ValueError(f"{card['id']}: Title is too long for two lines")
        speakers = wrap_text("发言人：" + " / ".join(card["speaker"]), inner, 10, measure)
        if len(speakers) > 2:
            raise ValueError(f"{card['id']}: Speakers are too long for two lines")
        source = wrap_text("来源：" + card["source"], inner, 8, measure)
        if len(source) > 3:
            source = wrap_text(f"来源：见 index.html 的 {card['id']} 完整来源", inner, 8, measure)
        content_top = MARGIN + 12 + len(titles) * 21 + 6 + len(speakers) * 14 + 11
        content_bottom = height - MARGIN - 15 - len(source) * 11 - 9
        capacity = content_bottom - content_top
        if capacity < body_size * 1.55 * 3:
            raise ValueError(f"{card['id']}: Page leaves fewer than 3 body lines; enlarge page or reduce font")
        blocks = []
        for kind, text in (("body", card["body"]), ("notes", card["notes"])):
            if not text:
                continue
            size = body_size if kind == "body" else 10
            leading = size * 1.55
            sentences = re.split(r"(?<=[。！？；])|\n", text)
            for sentence in sentences:
                if not sentence:
                    continue
                if kind == "notes":
                    sentence = "提示：" + sentence
                lines = wrap_text(sentence, inner, size, measure)
                blocks.append([{"text": line, "size": size, "leading": leading, "kind": kind} for line in lines])
        chunks, current, used = [], [], 0
        for block in blocks:
            block_height = sum(line["leading"] for line in block)
            if current and block_height <= capacity and used + block_height > capacity:
                chunks.append(current)
                current, used = [], 0
            for line in block:
                if current and used + line["leading"] > capacity:
                    chunks.append(current)
                    current, used = [], 0
                current.append(line)
                used += line["leading"]
        if current:
            chunks.append(current)
        for part, lines in enumerate(chunks, 1):
            pages.append({"card": card, "code": f"{card['id']}-{part:02d}/{len(chunks):02d}",
                          "part": part, "parts": len(chunks), "titles": titles, "speakers": speakers,
                          "source_lines": source, "lines": lines, "content_top": content_top,
                          "content_bottom": content_bottom})
        if len(pages) > 5000:
            raise ValueError("Deck exceeds 5000 pages; split input into smaller decks")
    return pages


def escape(text):
    return html.escape(str(text), quote=True)


def render_html(path, pages, data, args, accent):
    sheets = []
    height = args.height_mm * MM
    for number, page in enumerate(pages, 1):
        lines = []
        y = page["content_top"]
        for line in page["lines"]:
            lines.append(f'<div class="line {line["kind"]}" style="top:{y:.3f}pt;font-size:{line["size"]}pt;line-height:{line["leading"]:.3f}pt">{escape(line["text"])}</div>')
            y += line["leading"]
        title_html = "<br>".join(escape(t) for t in page["titles"])
        speaker_html = "<br>".join(escape(s) for s in page["speakers"])
        source_html = "<br>".join(escape(s) for s in page["source_lines"])
        bottom = "续卡" if page["part"] < page["parts"] else "结束"
        sheets.append(f'''<section class="card" aria-label="{escape(page['code'])}">
<div class="serial">{escape(page['code'])}</div>
<h1>{title_html}</h1>
<div class="speaker" style="top:{MARGIN + 12 + len(page['titles']) * 21 + 6:.3f}pt">{speaker_html}</div>
{''.join(lines)}
<div class="source" style="top:{height - MARGIN - 15 - len(page['source_lines']) * 11:.3f}pt">{source_html}</div>
<div class="footer">{escape(page['card']['id'])} · {bottom}<span>{number} / {len(pages)}</span></div>
</section>''')
    doc = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(data['deck_title'])}</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;background:#e8eded;color:#172a32;font-family:"Microsoft YaHei","Noto Sans CJK SC",sans-serif}}
.card{{position:relative;width:{args.width_mm}mm;height:{args.height_mm}mm;background:#fff;margin:7mm auto;box-shadow:0 2px 14px #0002;break-after:page;page-break-after:always}}
.serial{{position:absolute;top:7pt;left:{MARGIN:.3f}pt;right:{MARGIN:.3f}pt;font-size:8pt;line-height:10pt;color:{accent};text-align:right}}
h1{{position:absolute;top:{MARGIN + 12:.3f}pt;left:{MARGIN:.3f}pt;right:{MARGIN:.3f}pt;font-size:16pt;line-height:21pt;font-weight:600;margin:0}}
.speaker{{position:absolute;left:{MARGIN:.3f}pt;right:{MARGIN:.3f}pt;color:{accent};font-size:10pt;line-height:14pt}}
.line{{position:absolute;left:{MARGIN:.3f}pt;right:{MARGIN:.3f}pt;white-space:pre}}
.notes{{color:#56616c}}.source{{position:absolute;left:{MARGIN:.3f}pt;right:{MARGIN:.3f}pt;font-size:8pt;line-height:11pt;color:#56616c}}
.footer{{position:absolute;bottom:{MARGIN:.3f}pt;left:{MARGIN:.3f}pt;right:{MARGIN:.3f}pt;font-size:8pt;line-height:10pt;color:{accent}}}.footer span{{float:right}}
@page{{size:{args.width_mm}mm {args.height_mm}mm;margin:0}}@media print{{body{{background:#fff}}.card{{margin:0;box-shadow:none}}.card:last-child{{break-after:auto;page-break-after:auto}}}}
</style></head><body>{''.join(sheets)}</body></html>'''
    path.write_text(doc, encoding="utf-8")


def render_pdf(path, pages, data, args, accent, font_name):
    from reportlab.lib.colors import HexColor
    from reportlab.pdfgen.canvas import Canvas
    width, height = args.width_mm * MM, args.height_mm * MM
    canvas = Canvas(str(path), pagesize=(width, height), pageCompression=1)
    canvas.setTitle(data["deck_title"])
    canvas.setAuthor("Synbio Skills")
    canvas.setCreator(f"synbio-cue-cards {VERSION}")
    def draw(text, x, y_top, size, color="#172A32"):
        canvas.setFillColor(HexColor(color))
        canvas.setFont(font_name, size)
        canvas.drawString(x, height - y_top - size, text)
    for number, page in enumerate(pages, 1):
        draw(page["code"], MARGIN, 7, 8, accent)
        y = MARGIN + 12
        for title in page["titles"]:
            draw(title, MARGIN, y, 16)
            y += 21
        y += 6
        for speaker in page["speakers"]:
            draw(speaker, MARGIN, y, 10, accent)
            y += 14
        y = page["content_top"]
        for line in page["lines"]:
            draw(line["text"], MARGIN, y, line["size"], "#56616C" if line["kind"] == "notes" else "#172A32")
            y += line["leading"]
        y = height - MARGIN - 15 - len(page["source_lines"]) * 11
        for source in page["source_lines"]:
            draw(source, MARGIN, y, 8, "#56616C")
            y += 11
        end = "续卡" if page["part"] < page["parts"] else "结束"
        draw(f"{page['card']['id']} · {end}", MARGIN, height - MARGIN - 10, 8, accent)
        canvas.setFont(font_name, 8)
        canvas.drawRightString(width - MARGIN, MARGIN + 2, f"{number} / {len(pages)}")
        canvas.showPage()
    canvas.save()


def write_index(stage, data, decks, pages, args):
    manifest = {"generator": "synbio-cue-cards", "generator_version": VERSION,
                "deck_title": data["deck_title"], "page_size_mm": [args.width_mm, args.height_mm],
                "format": args.format, "cards": data["cards"], "decks": decks,
                "pages": [{"code": p["code"], "card_id": p["card"]["id"], "speaker": p["card"]["speaker"]} for p in pages]}
    (stage / "index.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    items = []
    for deck in decks:
        links = " · ".join(f'<a href="{escape(name)}">{escape(name)}</a>' for name in deck["files"])
        items.append(f'<li>{escape(deck["label"])}：{deck["pages"]} 页 · {links}</li>')
    records = []
    for card in data["cards"]:
        records.append(f'<tr id="{card["id"]}"><td>{card["id"]}</td><td>{escape(card["title"])}</td><td>{escape(" / ".join(card["speaker"]))}</td><td>{escape(card["source"])}</td></tr>')
    (stage / "index.html").write_text(f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>卡片索引</title>
<style>body{{max-width:1100px;margin:40px auto;padding:0 20px;font:16px/1.7 "Microsoft YaHei",sans-serif;color:#172a32}}h1{{font-size:26px}}a{{color:#176b70}}table{{border-collapse:collapse;width:100%}}th,td{{text-align:left;vertical-align:top;border:1px solid #cfd8da;padding:10px;white-space:pre-wrap;overflow-wrap:anywhere}}th{{background:#edf4f4}}p{{color:#56616c}}</style>
</head><body><h1>{escape(data['deck_title'])}</h1><p>{len(data['cards'])} 条原始卡 · 总套 {len(pages)} 页 · {args.width_mm:g} × {args.height_mm:g} mm</p>
<ul>{''.join(items)}</ul><p>提示会随正文打印。长来源请通过此索引核对；请将索引与卡片一起保留。JSON 索引保存全部原始正文与提示。</p>
<table><thead><tr><th>卡号</th><th>主题</th><th>发言人</th><th>完整来源</th></tr></thead><tbody>{''.join(records)}</tbody></table></body></html>''', encoding="utf-8")


def run(args):
    for name, minimum, maximum in (("width_mm", 100, 250), ("height_mm", 70, 210), ("body_pt", 10, 24)):
        value = getattr(args, name)
        if not math.isfinite(value) or not minimum <= value <= maximum:
            raise ValueError(f"{name} must be between {minimum} and {maximum}")
    if args.font_index < 0:
        raise ValueError("font-index must be nonnegative")
    source_path = Path(args.input).resolve()
    out = Path(args.out).resolve()
    if out.exists():
        raise ValueError(f"Output already exists: {out}; choose a new directory")
    data = load_input(source_path)
    measure, font_name = make_metrics(args, data)
    pages = layout_deck(data, args, measure)
    speakers = list(dict.fromkeys(s for card in data["cards"] for s in card["speaker"]))
    groups = [("all", "总套", pages)] + [(f"speaker-{i:02d}", speaker, [p for p in pages if speaker in p["card"]["speaker"]]) for i, speaker in enumerate(speakers, 1)]
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{out.name}-", dir=out.parent) as temp_name:
        stage = Path(temp_name)
        decks = []
        for i, (stem, label, group) in enumerate(groups):
            files = []
            if args.format in ("html", "both"):
                render_html(stage / f"{stem}.html", group, data, args, PALETTE[i % len(PALETTE)])
                files.append(f"{stem}.html")
            if args.format in ("pdf", "both"):
                render_pdf(stage / f"{stem}.pdf", group, data, args, PALETTE[i % len(PALETTE)], font_name)
                files.append(f"{stem}.pdf")
            decks.append({"label": label, "pages": len(group), "files": files})
        write_index(stage, data, decks, pages, args)
        if out.exists():
            raise ValueError(f"Output appeared during generation: {out}; refusing to overwrite")
        # Move the fully generated directory; TemporaryDirectory tolerates its absence.
        os.rename(stage, out)
    return {"output": str(out), "original_cards": len(data["cards"]), "total_pages": len(pages), "speaker_decks": len(speakers), "format": args.format}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="UTF-8 card JSON")
    parser.add_argument("--out", required=True, help="New output directory; existing paths are not overwritten")
    parser.add_argument("--format", choices=("html", "pdf", "both"), default="html")
    parser.add_argument("--font", help="Local TrueType font (TTF or compatible TTC), needed for PDF")
    parser.add_argument("--font-index", type=int, default=0)
    parser.add_argument("--width-mm", type=float, default=150)
    parser.add_argument("--height-mm", type=float, default=100)
    parser.add_argument("--body-pt", type=float, default=13)
    parser.add_argument("--version", action="version", version=VERSION)
    args = parser.parse_args(argv)
    try:
        result = run(args)
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
