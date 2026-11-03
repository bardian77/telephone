"""Build the Research and Experimentation Log as a .pptx (and PDF when LibreOffice is present).

Usage: python log/build_deck.py [--figures data/figures] [--out log/build/telephone_log.pptx]

Slides come from log/outline.md: every '## N. Title' heading is a slide, its bullets are the
body, and any backtick path that points at an existing figure under --figures is placed as a
picture. [RESULTS] slides whose figures are missing get a visible placeholder, so the deck can be
built before the experiments have run and rebuilt after.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Emu, Inches, Pt

W, H = Inches(13.333), Inches(7.5)
INK = RGBColor(0x0B, 0x0B, 0x0B)
MUTED = RGBColor(0x52, 0x51, 0x4E)
ACCENT = RGBColor(0x2A, 0x78, 0xD6)


def parse_outline(path: Path) -> list[dict]:
    slides: list[dict] = []
    cur: dict | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^## (\d+)\. (.+)$", line)
        if m:
            cur = {"n": int(m.group(1)), "title": m.group(2).strip(), "bullets": [], "figures": []}
            slides.append(cur)
            continue
        if cur is None or not line.strip():
            continue
        if line.startswith("- "):
            text = line[2:].strip()
            for fig in re.findall(r"`([^`]+\.png)`", text):
                cur["figures"].append(fig)
            text = re.sub(r"\s*Figures?: .*$", "", text)
            text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
            text = re.sub(r"\*(.+?)\*", r"\1", text)
            text = text.replace("`", "")
            if text:
                cur["bullets"].append(text)
    return slides


def find_figure(spec: str, figures: Path) -> Path | None:
    spec = spec.replace("<best chain>", "*").replace("*", "*")
    for p in sorted(figures.glob(spec)):
        if p.exists():
            return p
    return None


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


def build(outline: Path, figures: Path, out: Path) -> Path:
    prs = Presentation()
    prs.slide_width, prs.slide_height = W, H
    blank = prs.slide_layouts[6]
    for s in parse_outline(outline):
        slide = prs.slides.add_slide(blank)
        title = s["title"].replace("[RESULTS] ", "")
        add_text(
            slide, Inches(0.6), Inches(0.4), Inches(12), Inches(0.9), title, size=28, bold=True
        )
        add_text(
            slide,
            Inches(0.6),
            Inches(7.0),
            Inches(12),
            Inches(0.4),
            f"{s['n']} / 16 · Telephone · 5IMAG022W",
            size=10,
            color=MUTED,
        )
        found = [p for p in (find_figure(f, figures) for f in s["figures"]) if p]
        if found:
            add_bullets(
                slide, Inches(0.6), Inches(1.4), Inches(5.6), Inches(5.4), s["bullets"], size=13
            )
            top = Inches(1.4)
            per = Emu(int(Inches(5.4) / min(len(found), 2)))
            for p in found[:2]:
                slide.shapes.add_picture(str(p), Inches(6.5), top, width=Inches(6.3))
                top = Emu(top + per)
        else:
            add_bullets(
                slide, Inches(0.6), Inches(1.4), Inches(12), Inches(5.4), s["bullets"], size=15
            )
            if "[RESULTS]" in s["title"]:
                add_text(
                    slide,
                    Inches(0.6),
                    Inches(6.3),
                    Inches(12),
                    Inches(0.6),
                    "PLACEHOLDER: figures appear here after the experiment has run (python analysis/figures.py, then rebuild the deck).",
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
    ap.add_argument("--outline", default="log/outline.md")
    ap.add_argument("--figures", default="data/figures")
    ap.add_argument("--out", default="log/build/telephone_log.pptx")
    a = ap.parse_args()
    out = build(Path(a.outline), Path(a.figures), Path(a.out))
    print(f"wrote {out}")
    pdf = to_pdf(out)
    print(
        f"wrote {pdf}"
        if pdf
        else "LibreOffice not found; export the PDF from PowerPoint/Keynote/Google Slides"
    )
