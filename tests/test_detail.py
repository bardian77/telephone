"""The registered comparison: fine detail at a picture's own size, against the same part of the
original.

Every picture here is synthetic, so the tests need no photograph, no network and no weights.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFilter
from typer.testing import CliRunner

from telephone.chain import ChainRunner, RunnerOptions
from telephone.cli import app
from telephone.config import get_settings
from telephone.imageio import from_bytes, to_jpeg_bytes, to_png_bytes
from telephone.ledger import Ledger
from telephone.metrics.detail import (
    CropBox,
    after_screenshot,
    box_after,
    detail_scores,
    reference_for,
    registration_shift,
    whole,
)
from telephone.models import ChainConfig, GenerationRecord, StationConfig, StationRecord

SMALL_PHONE = {"screen_width": 390, "screen_height": 844}
SMALL_INSTAGRAM = {"preset": "instagram", "max_side": 360}
UPLOAD = StationConfig(kind="platform", params=SMALL_INSTAGRAM)
OFFLINE = RunnerOptions(
    compute_clip=False, compute_lpips=False, compute_readability=False, extractor=None
)


def detailed_image(size: tuple[int, int] = (600, 400), seed: int = 0) -> Image.Image:
    """Grain, thin lines and small text: nothing in it repeats, so a picture that is one pixel
    out of place cannot match by accident."""
    w, h = size
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w]
    gradient = np.stack([90 + 80 * xx / w, 110 + 60 * yy / h, 150 - 50 * xx / w], axis=-1)
    grain = rng.normal(0, 25, (h, w, 3))
    img = Image.fromarray(np.clip(gradient + grain, 0, 255).astype(np.uint8), "RGB")
    d = ImageDraw.Draw(img)
    for x in range(8, w, 37):
        d.line([(x, 0), (x + 60, h)], fill=(0, 0, 0), width=1)
    for y in range(5, h, 29):
        d.line([(0, y), (w, y + 11)], fill=(255, 255, 255), width=1)
    d.text((20, 20), "NO CYCLING  NO SKATEBOARDING", fill=(255, 255, 0))
    return img


def shot(displayed: tuple[int, int], crop: tuple[int, int, int, int]) -> dict:
    """What the screenshot station writes into a record's `raw` for one pass."""
    left, top, right, bottom = crop
    return {
        "displayed_width": displayed[0],
        "displayed_height": displayed[1],
        "crop": {"left": left, "top": top, "right": right, "bottom": bottom},
    }


# -- the crop box ---------------------------------------------------------------------------------


def test_the_box_starts_as_the_whole_original():
    box = whole(600, 400)
    assert (box.x0, box.y0, box.x1, box.y1) == (0.0, 0.0, 600.0, 400.0)
    assert (box.width, box.height, box.area) == (600.0, 400.0, 240000.0)


def test_one_screenshot_pass_moves_the_box_by_the_crop_in_original_pixels():
    # 600 x 400 shown at twice the size: one displayed pixel is half an original pixel
    box = after_screenshot(whole(600, 400), shot((1200, 800), (4, 2, 6, 8)))
    assert (box.x0, box.y0, box.x1, box.y1) == (2.0, 1.0, 597.0, 396.0)


def test_a_second_pass_is_measured_in_what_the_first_one_left():
    first = after_screenshot(whole(600, 400), shot((1200, 800), (4, 2, 6, 8)))  # 595 x 395 left
    # the 595 x 395 that is left is now shown 1190 x 790, so again 2 displayed px = 1 original px
    second = after_screenshot(first, shot((1190, 790), (2, 4, 0, 6)))
    assert (second.x0, second.y0, second.x1, second.y1) == (3.0, 3.0, 597.0, 393.0)


def test_each_side_is_scaled_on_its_own_because_the_displayed_size_is_rounded():
    # 100 x 30 shown at 333 x 100: the two sides are not scaled by quite the same amount
    box = after_screenshot(whole(100, 30), shot((333, 100), (3, 0, 0, 10)))
    assert box.x0 == pytest.approx(3 * 100 / 333)
    assert box.y1 == pytest.approx(30 - 10 * 30 / 100)


def test_an_upload_only_scales_so_it_leaves_the_box_alone():
    upload = StationRecord(kind="platform", raw={"width": 360, "height": 240, "bytes": 1})
    screenshot = StationRecord(kind="screenshot", raw=shot((1200, 800), (4, 2, 6, 8)))
    start = whole(600, 400)
    assert box_after(start, [upload]) == start
    assert box_after(start, [screenshot, upload]) == CropBox(2.0, 1.0, 597.0, 396.0)


# -- the reference and the three numbers -----------------------------------------------------------


def test_the_reference_for_an_uncropped_picture_is_the_original_resized_once():
    original = detailed_image((600, 400))
    ref = reference_for(to_png_bytes(original), whole(600, 400), (360, 240))
    plain = original.convert("L").resize((360, 240), Image.Resampling.LANCZOS)
    assert ref.size == (360, 240)
    assert np.array_equal(np.asarray(ref), np.asarray(plain))


def test_the_reference_for_a_cropped_picture_is_that_part_of_the_original():
    original = detailed_image((600, 400))
    ref = reference_for(to_png_bytes(original), CropBox(100.0, 50.0, 400.0, 250.0), (300, 200))
    part = original.convert("L").crop((100, 50, 400, 250))  # same size: nothing to resample
    assert np.abs(np.asarray(ref, dtype=float) - np.asarray(part, dtype=float)).max() <= 1


def test_a_clean_resize_keeps_its_detail_and_a_blurred_copy_does_not():
    original = detailed_image((600, 400))
    png = to_png_bytes(original)
    clean = original.resize((360, 240), Image.Resampling.LANCZOS)
    blurred = clean.filter(ImageFilter.GaussianBlur(1.5))

    a = detail_scores(to_png_bytes(clean), png, whole(600, 400))
    assert a["ssim_native"] == pytest.approx(1.0, abs=0.02)
    assert a["detail_kept"] == pytest.approx(1.0, abs=0.05)
    assert a["frame_kept"] == 1.0
    assert (a["width"], a["height"]) == (360, 240)

    b = detail_scores(to_png_bytes(blurred), png, whole(600, 400))
    assert b["detail_kept"] < 0.3  # the fine detail is what a blur removes
    assert b["ssim_native"] < a["ssim_native"] - 0.2


def test_marks_that_saving_adds_do_not_count_as_detail_kept():
    """Saving a JPEG twice adds speckle that was never in the photograph. It raises the amount
    of pixel-to-pixel variation (detail_energy) and must not raise the share of the ORIGINAL's
    detail that is still there (detail_kept)."""
    original = detailed_image((600, 400))
    png = to_png_bytes(original)
    clean = original.resize((360, 240), Image.Resampling.LANCZOS)
    rng = np.random.default_rng(1)
    speckle = rng.normal(0, 12, (240, 360, 1))
    noisy = Image.fromarray(
        np.clip(np.asarray(clean, dtype=float) + speckle, 0, 255).astype(np.uint8)
    )

    a = detail_scores(to_png_bytes(clean), png, whole(600, 400))
    b = detail_scores(to_png_bytes(noisy), png, whole(600, 400))
    assert b["detail_energy"] > a["detail_energy"] + 0.15  # more variation in the picture...
    assert b["detail_kept"] == pytest.approx(
        a["detail_kept"], abs=0.05
    )  # ...none of it kept detail
    assert b["ssim_native"] < a["ssim_native"]


def test_a_picture_with_its_fine_detail_halved_keeps_about_half():
    original = detailed_image((600, 400))
    clean = original.resize((360, 240), Image.Resampling.LANCZOS)
    soft = clean.filter(ImageFilter.GaussianBlur(4))
    # half way between the clean picture and a heavily blurred one: about half the fine detail
    half = Image.blend(clean, soft, 0.5)
    scores = detail_scores(to_png_bytes(half), to_png_bytes(original), whole(600, 400))
    assert scores["detail_kept"] == pytest.approx(0.5, abs=0.08)


def test_frame_kept_is_the_share_of_the_original_still_in_the_picture():
    original = detailed_image((600, 400))
    box = CropBox(60.0, 40.0, 540.0, 360.0)  # 480 x 320 of 600 x 400
    part = original.crop((60, 40, 540, 360))
    scores = detail_scores(to_png_bytes(part), to_png_bytes(original), box)
    assert scores["frame_kept"] == pytest.approx(0.64)
    assert scores["box"] == [60.0, 40.0, 540.0, 360.0]
    assert scores["ssim_native"] == pytest.approx(1.0, abs=0.01)


def test_a_picture_that_is_out_of_place_shows_up_as_a_shift():
    original = detailed_image((600, 400)).convert("L")
    ref = original.crop((10, 10, 370, 250))
    assert registration_shift(ref, ref) == (0, 0)
    moved = original.crop((12, 9, 372, 249))  # the same view, 2 px right and 1 px up
    assert registration_shift(moved, ref) == (2, -1)


# -- on a real chain --------------------------------------------------------------------------------


def run_chain(tmp_path: Path, name: str, stations: list[StationConfig], generations: int = 8):
    path = tmp_path / "detail.png"
    if not path.exists():
        detailed_image((600, 400)).save(path)
    cfg = ChainConfig(
        chain_id=f"t__{name}__street_test_01",
        experiment_id="t",
        image=str(path),
        stations=stations,
        generations=generations,
        seed=7,
    )
    return ChainRunner(options=OFFLINE).run(cfg)


def scores_along(recs: list[GenerationRecord]) -> list[dict]:
    """detail_scores for every generation of a chain, following the box as the chain did."""
    from telephone import paths

    original = paths.resolve(recs[0].output_path).read_bytes()
    w, h = from_bytes(original).size
    box, out = whole(w, h), []
    for rec in recs:
        box = box_after(box, rec.stations)
        out.append(detail_scores(paths.resolve(rec.output_path).read_bytes(), original, box))
    return out


def test_the_tracked_box_lines_up_with_a_loose_crop_chain(tmp_path):
    loose = StationConfig(kind="screenshot", params={**SMALL_PHONE, "crop_jitter_px": 3})
    recs = run_chain(tmp_path, "loose", [loose, UPLOAD])
    scores = scores_along(recs)

    assert scores[0]["ssim_native"] == pytest.approx(1.0) and scores[0]["frame_kept"] == 1.0
    for g in (2, 5, 8):
        assert scores[g]["shift"] == [0, 0], f"the box is out of place at generation {g}"
    assert scores[8]["frame_kept"] < scores[2]["frame_kept"] < 1.0  # the frame keeps shrinking
    assert scores[8]["ssim_native"] < scores[1]["ssim_native"]  # and the damage keeps adding up

    # the box matters: against the WHOLE original, generation 8 looks far worse than it is
    from telephone import paths

    original = paths.resolve(recs[0].output_path).read_bytes()
    last = paths.resolve(recs[8].output_path).read_bytes()
    untracked = detail_scores(last, original, whole(600, 400))
    assert untracked["ssim_native"] < scores[8]["ssim_native"] - 0.1


def test_a_reupload_chain_holds_steady_after_the_first_pass(tmp_path):
    scores = scores_along(run_chain(tmp_path, "reupload", [UPLOAD]))
    assert scores[1]["ssim_native"] < 1.0  # the first upload costs something
    assert scores[8]["ssim_native"] == pytest.approx(scores[2]["ssim_native"], abs=0.005)
    assert scores[8]["detail_kept"] == pytest.approx(scores[2]["detail_kept"], abs=0.02)
    assert all(s["frame_kept"] == 1.0 and s["shift"] == [0, 0] for s in scores)


# -- the command -----------------------------------------------------------------------------------


def test_detail_test_writes_one_sorted_row_per_generation(tmp_path):
    loose = StationConfig(kind="screenshot", params={**SMALL_PHONE, "crop_jitter_px": 3})
    run_chain(tmp_path, "reupload", [UPLOAD], generations=3)
    run_chain(tmp_path, "loose", [loose, UPLOAD], generations=3)

    result = CliRunner().invoke(app, ["detail-test", "t"])
    assert result.exit_code == 0, result.output
    out = get_settings().results_dir / "t_detail.jsonl"
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]

    assert [(r["variant"], r["generation"]) for r in rows] == [
        (v, g) for v in ("loose", "reupload") for g in range(4)
    ]
    first = rows[0]
    assert first["image"] == "street_test_01" and first["experiment_id"] == "t"
    assert (first["ssim_native"], first["detail_kept"], first["frame_kept"]) == (1.0, 1.0, 1.0)
    assert rows[3]["frame_kept"] < 1.0 and rows[7]["frame_kept"] == 1.0
    assert first["detail_energy"] == 1.0
    for key in ("output_sha", "config_sha", "box", "shift", "width", "height", "method"):
        assert key in first
    assert "wrote 8 rows" in result.output


def test_detail_test_leaves_out_chains_a_registered_comparison_means_nothing_for(tmp_path):
    run_chain(tmp_path, "reupload", [UPLOAD], generations=2)
    # a describe-and-redraw chain: the picture is drawn afresh, so there is no "same region"
    led = Ledger(get_settings().ledger_path)
    led.append(
        GenerationRecord(
            run_id="r",
            experiment_id="t",
            chain_id="t__redraw__street_test_01",
            generation=0,
            station_sequence="caption > regenerate",
            output_path="nowhere.png",
            output_sha="0",
        )
    )
    result = CliRunner().invoke(app, ["detail-test", "t"])
    assert result.exit_code == 0, result.output
    text = (get_settings().results_dir / "t_detail.jsonl").read_text(encoding="utf-8")
    assert "redraw" not in text
    assert "1 chain" in result.output and "redraw" in result.output.replace("\n", " ")


def test_detail_test_never_writes_a_private_photograph(tmp_path):
    s = get_settings()
    s.private_dir.mkdir(parents=True, exist_ok=True)
    (s.private_dir / "street_test_01.jpg").write_bytes(to_jpeg_bytes(detailed_image((64, 64))))
    run_chain(tmp_path, "reupload", [UPLOAD], generations=2)
    result = CliRunner().invoke(app, ["detail-test", "t"])
    assert result.exit_code == 1
    assert not (s.results_dir / "t_detail.jsonl").exists()
    assert "private" in result.output


def test_detail_test_on_an_unknown_experiment_is_one_line(tmp_path):
    run_chain(tmp_path, "reupload", [UPLOAD], generations=1)
    result = CliRunner().invoke(app, ["detail-test", "nothing_like_this"])
    assert result.exit_code == 1
    assert "Traceback" not in result.output
    assert "nothing_like_this" in result.output
