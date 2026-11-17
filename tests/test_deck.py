"""The deck builder: log/outline.md -> the research log as slides."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from PIL import Image
from pptx import Presentation
from pptx.util import Inches

ROOT = Path(__file__).resolve().parent.parent


def load_builder():
    spec = importlib.util.spec_from_file_location("build_deck", ROOT / "log" / "build_deck.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


deck = load_builder()


def picture(path: Path, size: tuple[int, int]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, (120, 140, 160)).save(path)
    return path


def outline(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "outline.md"
    path.write_text(text, encoding="utf-8")
    return path


def test_the_outline_gives_each_slide_its_bullets_figures_and_layout(tmp_path):
    slides = deck.parse_outline(
        outline(
            tmp_path,
            "# Log\n\n## 1. Title\n- **Telephone.** One line.\n\n"
            "## 2. [WIDE] A result\n- The claim. Figure: `a/b.png`\n- A note. Figure: `c/d.jpg`\n",
        )
    )
    assert [(s["n"], s["title"], s["wide"]) for s in slides] == [
        (1, "Title", False),
        (2, "A result", True),
    ]
    assert slides[0]["bullets"] == ["Telephone. One line."]
    assert slides[1]["figures"] == ["a/b.png", "c/d.jpg"]  # jpg as well as png
    assert slides[1]["bullets"] == ["The claim.", "A note."]


def test_a_figure_is_found_under_the_figures_folder_or_from_the_project_root(tmp_path):
    figures = tmp_path / "figures"
    inside = picture(figures / "exp" / "one.png", (40, 30))
    assert deck.find_figure("exp/one.png", figures, root=tmp_path) == inside
    elsewhere = picture(tmp_path / "docs" / "day" / "two.jpg", (40, 30))
    assert deck.find_figure("docs/day/two.jpg", figures, root=tmp_path) == elsewhere
    assert deck.find_figure("docs/day/missing.png", figures, root=tmp_path) is None


def test_slides_are_numbered_out_of_the_real_total(tmp_path):
    text = "## 1. One\n- a\n\n## 2. Two\n- b\n\n## 3. Three\n- c\n"
    out = deck.build(outline(tmp_path, text), tmp_path / "figures", tmp_path / "log.pptx")
    prs = Presentation(str(out))
    assert len(prs.slides) == 3
    footers = [
        shape.text_frame.text
        for slide in prs.slides
        for shape in slide.shapes
        if shape.has_text_frame and " / " in shape.text_frame.text
    ]
    assert [f.split(" · ")[0] for f in footers] == ["1 / 3", "2 / 3", "3 / 3"]


@pytest.mark.parametrize("size", [(1600, 500), (500, 1600), (1500, 840)])
@pytest.mark.parametrize("wide", ["", "[WIDE] "])
def test_a_picture_always_fits_on_the_slide_whatever_its_shape(tmp_path, size, wide):
    picture(tmp_path / "docs" / "fig.png", size)
    text = f"## 1. {wide}A result\n- The claim. Figure: `docs/fig.png`\n"
    out = deck.build(
        outline(tmp_path, text), tmp_path / "figures", tmp_path / "log.pptx", root=tmp_path
    )
    slide = Presentation(str(out)).slides[0]
    pics = [s for s in slide.shapes if s.shape_type == 13]
    assert len(pics) == 1
    pic = pics[0]
    assert pic.left >= 0 and pic.top >= Inches(1.2)
    assert pic.left + pic.width <= Inches(13.333) + 1
    assert pic.top + pic.height <= Inches(6.95)
    assert pic.width / pic.height == pytest.approx(size[0] / size[1], rel=0.01)  # not stretched


def test_a_wide_slide_with_too_much_text_is_an_error_not_a_silent_cut(tmp_path):
    picture(tmp_path / "docs" / "fig.png", (800, 400))
    text = "## 4. [WIDE] Crowded\n- one `docs/fig.png`\n- two\n- three\n"
    with pytest.raises(ValueError, match="slide 4"):
        deck.build(
            outline(tmp_path, text), tmp_path / "figures", tmp_path / "log.pptx", root=tmp_path
        )


def test_a_picture_carries_the_description_written_beside_it(tmp_path):
    picture(tmp_path / "docs" / "fig.png", (800, 400))
    (tmp_path / "docs" / "figures.json").write_text(
        json.dumps({"fig.png": {"alt": "A line that falls and then levels off."}}),
        encoding="utf-8",
    )
    text = "## 1. A result\n- The claim. Figure: `docs/fig.png`\n"
    out = deck.build(
        outline(tmp_path, text), tmp_path / "figures", tmp_path / "log.pptx", root=tmp_path
    )
    pic = next(s for s in Presentation(str(out)).slides[0].shapes if s.shape_type == 13)
    assert pic._element.xpath(".//p:cNvPr")[0].get("descr") == (
        "A line that falls and then levels off."
    )


def test_a_results_slide_without_its_figure_says_so(tmp_path):
    text = "## 1. [RESULTS] Not run yet\n- The claim. Figure: `docs/nothing.png`\n"
    out = deck.build(
        outline(tmp_path, text), tmp_path / "figures", tmp_path / "log.pptx", root=tmp_path
    )
    slide = Presentation(str(out)).slides[0]
    words = " ".join(s.text_frame.text for s in slide.shapes if s.has_text_frame)
    assert "Not run yet" in words and "[RESULTS]" not in words
    assert "not been run" in words.lower()
