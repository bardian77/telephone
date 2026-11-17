"""Build the Research and Experimentation Log as a .pptx (and PDF when LibreOffice is present).

Usage, from any folder:  python log/build_deck.py

Slides come from log/outline.md. Every '## N. Title' heading is a slide and its '- ' lines are
the bullets. A path in backticks that ends in .png or .jpg is a figure: it is looked for under
--figures (data/figures) and then from the project root, so `docs/tutorial-17nov/figures/x.png`
works as written.

Two marks can go in front of a title:

  [WIDE]     the figure fills the slide. The first bullet is the one-line claim above it and an
             optional second bullet is the small caption below it. More text than that is an
             error, so nothing is ever cut without warning.
  [RESULTS]  the slide waits for an experiment. Until its figure exists the slide says the
             experiment has not been run, so the deck can be built before and rebuilt after.

A picture is always scaled to fit its place and never stretched. If a file called figures.json
sits beside a figure and has an "alt" for it, that text is attached to the picture.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parent.parent
W, H = Inches(13.333), Inches(7.5)
INK = RGBColor(0x0B, 0x0B, 0x0B)
MUTED = RGBColor(0x52, 0x51, 0x4E)
ACCENT = RGBColor(0x24, 0x66, 0xB8)
MARKS = ("[WIDE]", "[RESULTS]")
FIGURE = re.compile(r"`([^`]+\.(?:png|jpe?g))`", re.IGNORECASE)


def parse_outline(path: Path) -> list[dict]:
    slides: list[dict] = []
    cur: dict | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^## (\d+)\. (.+)$", line)
        if m:
            title = m.group(2).strip()
            cur = {
                "n": int(m.group(1)),
                "wide": "[WIDE]" in title,
                "results": "[RESULTS]" in title,
                "bullets": [],
                "figures": [],
            }
            for mark in MARKS:
                title = title.replace(mark, "")
            cur["title"] = " ".join(title.split())
            slides.append(cur)
            continue
        if cur is None or not line.startswith("- "):
            continue
        text = line[2:].strip()
        cur["figures"].extend(FIGURE.findall(text))
        text = re.sub(r"\s*Figures?: .*$", "", text)
        text = FIGURE.sub("", text)
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
        text = re.sub(r"\*(.+?)\*", r"\1", text)
        text = " ".join(text.replace("`", "").split())
        if text:
            cur["bullets"].append(text)
    return slides


def find_figure(spec: str, figures: Path, root: Path = ROOT) -> Path | None:
    """The file a figure path points at: under the figures folder first, then from the root."""
    spec = spec.replace("<best chain>", "*")
    for base in (figures, root):
        for p in sorted(Path(base).glob(spec)):
            if p.is_file():
                return p
    return None


def alt_text(figure: Path) -> str | None:
    """The description written for a figure in the figures.json beside it, if there is one."""
    notes = figure.parent / "figures.json"
    if not notes.is_file():
        return None
    entry = json.loads(notes.read_text(encoding="utf-8")).get(figure.name) or {}
    return entry.get("alt")


def add_text(slide, left, top, width, height, text, size=18, bold=False, color=INK):
    tb = slide.shapes.add_textbox(left, top, width, height)
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(size)
    p.font.bold = bold
    p.font.color.rgb = color
    return tb


def add_bullets(slide, left, top, width, height, bullets, size=14):
    tb = slide.shapes.add_textbox(left, top, width, height)
    tf = tb.text_frame
    tf.word_wrap = True
    for i, b in enumerate(bullets):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = "• " + b
        p.font.size = Pt(size)
        p.font.color.rgb = INK
        p.space_after = Pt(6)
    return tb


def add_picture(slide, path: Path, left, top, width, height):
    """Place a picture inside the box (left, top, width, height): as large as fits, centred,
    never stretched."""
    with Image.open(path) as img:
        w_px, h_px = img.size
    scale = min(width / w_px, height / h_px)
    w, h = Emu(int(w_px * scale)), Emu(int(h_px * scale))
    pic = slide.shapes.add_picture(
        str(path), Emu(int(left + (width - w) / 2)), Emu(int(top + (height - h) / 2)), w, h
    )
    alt = alt_text(path)
    if alt:
        pic._element.xpath(".//p:cNvPr")[0].set("descr", alt)
    return pic


def build(outline: Path, figures: Path, out: Path, root: Path = ROOT) -> Path:
    prs = Presentation()
    prs.slide_width, prs.slide_height = W, H
    blank = prs.slide_layouts[6]
    slides = parse_outline(outline)
    for s in slides:
        slide = prs.slides.add_slide(blank)
        add_text(
            slide, Inches(0.6), Inches(0.35), Inches(12.1), Inches(0.9), s["title"], 28, bold=True
        )
        add_text(
            slide,
            Inches(0.6),
            Inches(7.0),
            Inches(12.1),
            Inches(0.4),
            f"{s['n']} / {len(slides)} · Telephone · 5IMAG022W · Bardia Nasab",
            size=10,
            color=MUTED,
        )
        found = [p for p in (find_figure(f, figures, root) for f in s["figures"]) if p]
        bullets = s["bullets"]
        if s["wide"] and found:
            if len(bullets) > 2 or len(found) > 1:
                raise ValueError(
                    f"slide {s['n']} ({s['title']}) is marked [WIDE]: it takes one figure, one "
                    f"claim and at most one caption, and has {len(found)} figures and "
                    f"{len(bullets)} bullets"
                )
            if bullets:
                add_text(slide, Inches(0.6), Inches(1.2), Inches(12.1), Inches(0.6), bullets[0], 16)
            add_picture(slide, found[0], Inches(0.6), Inches(1.85), Inches(12.1), Inches(4.55))
            if len(bullets) == 2:
                add_text(
                    slide,
                    Inches(0.6),
                    Inches(6.45),
                    Inches(12.1),
                    Inches(0.5),
                    bullets[1],
                    11,
                    color=MUTED,
                )
        elif found:
            add_bullets(slide, Inches(0.6), Inches(1.4), Inches(5.5), Inches(5.4), bullets, size=14)
            shown = found[:2]
            each = Inches(5.4) / len(shown)
            for i, p in enumerate(shown):
                top = Emu(int(Inches(1.4) + i * each))
                add_picture(slide, p, Inches(6.4), top, Inches(6.3), Emu(int(each - Inches(0.15))))
        else:
            add_bullets(slide, Inches(0.6), Inches(1.4), Inches(12.1), Inches(5.2), bullets, 19)
            if s["results"]:
                add_text(
                    slide,
                    Inches(0.6),
                    Inches(6.4),
                    Inches(12.1),
                    Inches(0.5),
                    "This experiment has not been run yet. Its figure goes here when it has.",
                    size=12,
                    color=ACCENT,
                )
    out.parent.mkdir(parents=True, exist_ok=True)
    prs.save(out)
    return out


def to_pdf(pptx: Path) -> Path | None:
    exe = shutil.which("soffice") or shutil.which("libreoffice")
    if not exe:
        return None
    subprocess.run(
        [exe, "--headless", "--convert-to", "pdf", "--outdir", str(pptx.parent), str(pptx)],
        check=False,
        capture_output=True,
        timeout=300,
    )
    pdf = pptx.with_suffix(".pdf")
    return pdf if pdf.exists() else None


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--outline", default=str(ROOT / "log" / "outline.md"))
    ap.add_argument("--figures", default=str(ROOT / "data" / "figures"))
    ap.add_argument("--out", default=str(ROOT / "log" / "build" / "telephone_log.pptx"))
    a = ap.parse_args()
    out = build(Path(a.outline), Path(a.figures), Path(a.out))
    print(f"wrote {out}")
    pdf = to_pdf(out)
    print(
        f"wrote {pdf}"
        if pdf
        else "LibreOffice not found; export the PDF from PowerPoint/Keynote/Google Slides"
    )
