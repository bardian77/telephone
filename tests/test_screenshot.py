"""The screenshot station and experiment 7, the "screenshot and forward" loop.

Every picture here is synthetic (noise, thin lines and small text drawn with numpy and Pillow),
so the tests need no photograph, no network and no model weights.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml
from PIL import Image, ImageDraw
from typer.testing import CliRunner

from telephone import paths
from telephone.cache import StationCache
from telephone.chain import ChainRunner, RunnerOptions, config_fingerprint
from telephone.cli import app, parse_stations
from telephone.config import get_settings
from telephone.doctor import collect, render_text
from telephone.experiments import find, load_all
from telephone.export import export_all
from telephone.imageio import from_bytes, media_type_of, sha256_bytes, to_png_bytes
from telephone.ledger import Ledger
from telephone.models import ChainConfig, GenerationRecord, StationConfig
from telephone.render import render_all
from telephone.stations import build_station, screenshot
from telephone.stations.base import StationContext, StationResult
from telephone.stations.screenshot import crop_offsets, screen_size

# A phone screen a third of the default size (1170 x 2532), so the tests are quick.
SMALL_PHONE = {"screen_width": 390, "screen_height": 844}
EDGES = {"left", "top", "right", "bottom"}
# Instagram's settings at a third of the size, to go with the small phone: 390 / 360 is the same
# step up as the real 1170 / 1080.
SMALL_INSTAGRAM = {"preset": "instagram", "max_side": 360}
# Only the local measurements that need no model weights and no network.
OFFLINE = RunnerOptions(
    compute_clip=False, compute_lpips=False, compute_readability=False, extractor=None
)


def detailed_image(size: tuple[int, int] = (600, 400), seed: int = 0) -> Image.Image:
    """A synthetic picture with fine detail: grain over a soft gradient, thin lines, small text."""
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


def take_screenshot(
    tmp_path: Path,
    img: Image.Image,
    params: dict | None = None,
    generation: int = 1,
    seed: int = 7,
) -> StationResult:
    """Run the screenshot station once, as generation `generation` of a chain with seed `seed`."""
    cfg = StationConfig(kind="screenshot", params=params or {})
    chain = ChainConfig(
        chain_id="t", experiment_id="test", image="x.png", stations=[cfg], generations=3, seed=seed
    )
    ctx = StationContext(
        settings=get_settings(),
        cache=StationCache(tmp_path / "cache"),
        chain=chain,
        generation=generation,
        seed=seed,
    )
    png = to_png_bytes(img)
    return build_station(cfg).run(png, sha256_bytes(png), ctx)


def test_screenshot_station_builds_from_config_and_returns_a_png(tmp_path):
    res = take_screenshot(tmp_path, detailed_image())
    assert res.image is not None
    assert media_type_of(res.image) == "image/png"  # a screenshot is lossless
    assert res.record.kind == "screenshot" and res.record.error is None
    assert from_bytes(res.image).size[0] > 0


# -- the picture is shown as large as fits on the screen ------------------------------------------


def test_landscape_picture_comes_out_exactly_screen_width_wide(tmp_path):
    res = take_screenshot(tmp_path, detailed_image((1500, 1000)))
    assert from_bytes(res.image).size == (1170, 780)  # scaled down, same 3:2 shape


def test_very_tall_picture_is_limited_by_the_screen_height(tmp_path):
    res = take_screenshot(tmp_path, detailed_image((300, 1500)))
    # width alone would allow a 3.9x enlargement (5850 px tall); the screen is only 2532 px tall
    assert from_bytes(res.image).size == (506, 2532)


def test_the_displayed_size_is_rounded_to_the_nearest_pixel_not_cut_down():
    # The 16:9 photographs are 1080 x 608 after Instagram. On the 1170-wide screen the height
    # is 608 * 1170 / 1080 = 658.67 pixels, which is shown as 659, not 658.
    assert screen_size(1080, 608, 1170, 2532) == (1170, 659)
    # the same for a tall picture, where the height fills the screen: 300 * 2532 / 1500 = 506.4
    assert screen_size(300, 1500, 1170, 2532) == (506, 2532)
    assert screen_size(310, 1500, 1170, 2532) == (523, 2532)  # 523.28
    assert screen_size(311, 1500, 1170, 2532) == (525, 2532)  # 524.97


def test_small_picture_is_scaled_up_to_the_screen(tmp_path):
    res = take_screenshot(tmp_path, detailed_image((460, 460)))
    assert from_bytes(res.image).size == (1170, 1170)


def test_screen_size_and_resample_can_be_set(tmp_path):
    params = {**SMALL_PHONE, "resample": "bilinear"}
    res = take_screenshot(tmp_path, detailed_image((360, 240)), params)
    assert from_bytes(res.image).size == (390, 260)
    bicubic = take_screenshot(
        tmp_path, detailed_image((360, 240)), {**params, "resample": "bicubic"}
    )
    assert bicubic.image != res.image  # the two ways of resampling give different pixels


# -- the loose crop: a few pixels lost from each edge, a different few every generation ----------


def test_no_jitter_crops_nothing(tmp_path):
    assert crop_offsets(seed=7, generation=3, jitter=0) == dict.fromkeys(EDGES, 0)
    for generation in range(1, 6):
        res = take_screenshot(
            tmp_path, detailed_image((360, 240)), {**SMALL_PHONE, "crop_jitter_px": 0}, generation
        )
        assert from_bytes(res.image).size == (390, 260)


def test_jitter_removes_between_0_and_2n_pixels_per_axis(tmp_path):
    n = 6
    sizes = set()
    for generation in range(1, 21):
        res = take_screenshot(
            tmp_path, detailed_image((360, 240)), {**SMALL_PHONE, "crop_jitter_px": n}, generation
        )
        w, h = from_bytes(res.image).size
        assert 390 - 2 * n <= w <= 390 and 260 - 2 * n <= h <= 260
        sizes.add((w, h))
    assert len(sizes) >= 10  # the crop really moves from one generation to the next


def test_the_crop_takes_the_offsets_off_the_matching_edges(tmp_path):
    img = detailed_image((360, 240))
    uncropped = from_bytes(take_screenshot(tmp_path, img, SMALL_PHONE).image)
    for generation in (1, 2, 3):
        crop = crop_offsets(seed=7, generation=generation, jitter=6)
        box = (crop["left"], crop["top"], 390 - crop["right"], 260 - crop["bottom"])
        res = take_screenshot(tmp_path, img, {**SMALL_PHONE, "crop_jitter_px": 6}, generation)
        assert from_bytes(res.image).tobytes() == uncropped.crop(box).tobytes()


def test_crop_offsets_are_whole_numbers_from_0_to_n_and_use_the_whole_range():
    n = 6
    crops = [crop_offsets(seed=7, generation=g, jitter=n) for g in range(1, 41)]
    for crop in crops:
        assert set(crop) == EDGES
        assert all(isinstance(v, int) and 0 <= v <= n for v in crop.values())
    assert {v for crop in crops for v in crop.values()} == set(range(n + 1))


def test_crop_offsets_repeat_for_the_same_seed_and_generation():
    first = [crop_offsets(seed=7, generation=g, jitter=6) for g in range(1, 41)]
    again = [crop_offsets(seed=7, generation=g, jitter=6) for g in range(1, 41)]
    assert first == again


def test_crop_offsets_differ_between_generations_and_between_seeds():
    # 40 generations, so this cannot pass or fail by coincidence: with 7 values on each of four
    # edges there are 2401 possible crops, and two generations rarely draw the same one
    seed7 = [tuple(crop_offsets(seed=7, generation=g, jitter=6).values()) for g in range(1, 41)]
    seed8 = [tuple(crop_offsets(seed=8, generation=g, jitter=6).values()) for g in range(1, 41)]
    assert len(set(seed7)) >= 35
    assert sum(a == b for a, b in zip(seed7, seed8, strict=True)) <= 2


def test_crop_offsets_are_the_same_in_another_python_process():
    """Python's own hash() is salted per process; the offsets must not depend on it."""
    code = (
        "from telephone.stations.screenshot import crop_offsets; "
        "print([crop_offsets(seed=7, generation=g, jitter=6) for g in range(1, 6)])"
    )
    here = str([crop_offsets(seed=7, generation=g, jitter=6) for g in range(1, 6)])
    for salt in ("1", "2"):
        out = subprocess.run(
            [sys.executable, "-c", code],
            env={**os.environ, "PYTHONHASHSEED": salt},
            capture_output=True,
            text=True,
            check=True,
        )
        assert out.stdout.strip() == here


def test_a_tiny_picture_is_never_cropped_to_nothing(tmp_path):
    # shown at 8 x 2 pixels, with up to 6 pixels asked for from every edge
    params = {"screen_width": 8, "screen_height": 8, "crop_jitter_px": 6}
    for generation in range(1, 41):
        res = take_screenshot(tmp_path, detailed_image((40, 10)), params, generation)
        w, h = from_bytes(res.image).size
        assert 1 <= w <= 8 and 1 <= h <= 2


# -- the station cache ---------------------------------------------------------------------------


def test_loose_crop_generations_fed_identical_bytes_do_not_share_a_cache_entry(tmp_path):
    """The cache key is built from the input picture and the settings. A loose crop also depends
    on the generation, so generation 2 must not be handed generation 1's output."""
    img = detailed_image((360, 240))
    params = {**SMALL_PHONE, "crop_jitter_px": 6}
    assert crop_offsets(seed=7, generation=1, jitter=6) != crop_offsets(
        seed=7, generation=2, jitter=6
    )
    g1 = take_screenshot(tmp_path, img, params, generation=1)
    g2 = take_screenshot(tmp_path, img, params, generation=2)  # same bytes in, same cache folder
    assert g1.record.cached is False and g2.record.cached is False
    assert g2.image != g1.image
    # the same generation asked for again is a cache hit and gives back the same picture
    again = take_screenshot(tmp_path, img, params, generation=2)
    assert again.record.cached is True and again.image == g2.image
    # another chain seed crops differently, so it does not share the entry either
    other_seed = take_screenshot(tmp_path, img, params, generation=2, seed=8)
    assert other_seed.record.cached is False and other_seed.image != g2.image


def test_without_jitter_generations_fed_identical_bytes_share_the_cache(tmp_path):
    """With an exact crop nothing depends on the generation: same bytes in, same bytes out."""
    img = detailed_image((360, 240))
    g1 = take_screenshot(tmp_path, img, SMALL_PHONE, generation=1)
    g2 = take_screenshot(tmp_path, img, SMALL_PHONE, generation=2)
    assert g1.record.cached is False
    assert g2.record.cached is True and g2.image == g1.image


# -- what the station writes down ----------------------------------------------------------------


def test_the_record_says_what_the_screenshot_did(tmp_path):
    params = {**SMALL_PHONE, "crop_jitter_px": 6}
    res = take_screenshot(tmp_path, detailed_image((360, 240)), params, generation=2)
    rec = res.record
    assert (rec.kind, rec.provider, rec.model) == ("screenshot", "local", "pillow")
    assert rec.params == {  # the settings actually used, defaults included
        "screen_width": 390,
        "screen_height": 844,
        "crop_jitter_px": 6,
        "resample": "bicubic",
    }
    assert rec.seed == 7  # the seed the crop was worked out from
    crop = crop_offsets(seed=7, generation=2, jitter=6)
    assert rec.raw == {
        "scale": pytest.approx(390 / 360),
        "displayed_width": 390,
        "displayed_height": 260,
        "crop": crop,
        "width": 390 - crop["left"] - crop["right"],
        "height": 260 - crop["top"] - crop["bottom"],
        "bytes": len(res.image),
    }
    assert from_bytes(res.image).size == (rec.raw["width"], rec.raw["height"])


def test_the_record_of_an_exact_crop_has_no_seed_and_a_zero_crop(tmp_path):
    res = take_screenshot(tmp_path, detailed_image((1500, 1000)))
    assert res.record.params == {
        "screen_width": 1170,
        "screen_height": 2532,
        "crop_jitter_px": 0,
        "resample": "bicubic",
    }
    assert res.record.seed is None  # nothing random happened
    assert res.record.raw["scale"] == pytest.approx(0.78)
    assert res.record.raw["crop"] == dict.fromkeys(EDGES, 0)
    assert (res.record.raw["width"], res.record.raw["height"]) == (1170, 780)


def test_the_record_shows_the_crop_that_was_really_made_on_a_tiny_picture(tmp_path):
    params = {"screen_width": 8, "screen_height": 8, "crop_jitter_px": 6}
    for generation in range(1, 11):
        raw = take_screenshot(tmp_path, detailed_image((40, 10)), params, generation).record.raw
        assert (raw["displayed_width"], raw["displayed_height"]) == (8, 2)
        assert raw["width"] == 8 - raw["crop"]["left"] - raw["crop"]["right"]
        assert raw["height"] == 2 - raw["crop"]["top"] - raw["crop"]["bottom"] == 2


# -- settings ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("params", "named_in_message"),
    [
        ({"crop_jiter_px": 6}, "crop_jiter_px"),  # misspelt name
        ({"resample": "nearest"}, "nearest"),  # not one of the two ways offered
        ({"screen_width": 0}, "screen_width"),
        ({"crop_jitter_px": -1}, "crop_jitter_px"),
    ],
)
def test_a_wrong_setting_is_an_error_not_a_silent_default(params, named_in_message):
    with pytest.raises(ValueError, match=named_in_message):
        build_station(StationConfig(kind="screenshot", params=params))


@pytest.mark.parametrize(
    ("params", "named_in_message"),
    [
        ({"crop_jitter_px": 0.6}, "crop_jitter_px"),  # would have been cut down to 0, an exact crop
        ({"crop_jitter_px": None}, "crop_jitter_px"),  # an empty value in the experiment file
        ({"crop_jitter_px": "six"}, "crop_jitter_px"),
        ({"screen_width": 1170.5}, "screen_width"),
        ({"screen_height": True}, "screen_height"),
    ],
)
def test_a_setting_that_is_not_a_whole_number_is_refused_not_rounded(params, named_in_message):
    with pytest.raises(ValueError, match=f"{named_in_message} must be a whole number"):
        build_station(StationConfig(kind="screenshot", params=params))


def test_a_whole_number_written_as_a_float_is_accepted(tmp_path):
    res = take_screenshot(
        tmp_path, detailed_image((360, 240)), {**SMALL_PHONE, "crop_jitter_px": 6.0}
    )
    assert res.record.params["crop_jitter_px"] == 6
    assert isinstance(res.record.params["crop_jitter_px"], int)


def test_a_seed_in_the_params_replaces_the_chain_seed(tmp_path):
    """Every station accepts a `seed` param; here it decides the loose crop."""
    params = {**SMALL_PHONE, "crop_jitter_px": 6, "seed": 3}
    res = take_screenshot(tmp_path, detailed_image((360, 240)), params, generation=2, seed=7)
    assert res.record.seed == 3
    assert res.record.raw["crop"] == crop_offsets(seed=3, generation=2, jitter=6)


# -- chains ----------------------------------------------------------------------------------------


def small_chain(
    name: str, stations: list[StationConfig], image: str = "x.png", generations: int = 8
) -> ChainConfig:
    return ChainConfig(
        chain_id=f"t__{name}__detail",
        experiment_id="t",
        image=image,
        stations=stations,
        generations=generations,
        seed=7,
    )


def run_small_chain(
    tmp_path: Path, name: str, stations: list[StationConfig], generations: int = 8
) -> list[GenerationRecord]:
    """A short chain on the synthetic picture, with the ledger and cache in a temp folder."""
    path = tmp_path / "detail.png"
    if not path.exists():
        # 600 x 400 becomes 360 x 240 after the small platform: a whole number of 8-pixel JPEG
        # blocks each way, like the 1080 x 608 that the 16:9 photographs become on Instagram.
        # (Sizes that leave a part-block at the edge take two to three times longer to settle.)
        detailed_image((600, 400)).save(path)
    return ChainRunner(options=OFFLINE).run(small_chain(name, stations, str(path), generations))


def first_repeat(recs: list[GenerationRecord]) -> int | None:
    """The first generation whose file is byte for byte the one before it, or None."""
    files = [r.output_sha for r in recs]
    return next((g for g in range(1, len(files)) if files[g] == files[g - 1]), None)


def test_config_fingerprint_differs_between_exact_and_loose_crop():
    upload = StationConfig(kind="platform", params={"preset": "instagram"})

    def fingerprint(jitter: int) -> str:
        shot = StationConfig(kind="screenshot", params={"crop_jitter_px": jitter})
        return config_fingerprint(small_chain("x", [shot, upload]), None, get_settings())

    assert fingerprint(0) != fingerprint(6)
    assert fingerprint(6) == fingerprint(6)
    reupload_only = config_fingerprint(small_chain("x", [upload]), None, get_settings())
    assert reupload_only not in (fingerprint(0), fingerprint(6))


def test_config_fingerprint_covers_the_screenshot_settings_that_come_from_the_code(monkeypatch):
    """Experiment 7 only writes crop_jitter_px; the phone's screen size and the way of
    resampling come from DEFAULTS in the station. A chain is resumed only from rows with the
    same fingerprint, so the fingerprint must change when one of those defaults changes.
    Otherwise one chain could be made on two different phones with nothing to show it."""
    upload = StationConfig(kind="platform", params={"preset": "instagram"})

    def fingerprint(params: dict) -> str:
        shot = StationConfig(kind="screenshot", params=params)
        return config_fingerprint(small_chain("x", [shot, upload]), None, get_settings())

    # leaving a default out and writing it down build the same station: one fingerprint
    assert fingerprint({}) == fingerprint({"crop_jitter_px": 0})
    assert fingerprint({}) == fingerprint({"screen_width": 1170, "resample": "bicubic"})
    assert fingerprint({}) != fingerprint({"resample": "bilinear"})
    assert fingerprint({}) != fingerprint({"seed": 3})  # a seed in the params still counts

    before = fingerprint({"crop_jitter_px": 0})
    monkeypatch.setitem(screenshot.DEFAULTS, "screen_width", 900)  # a different phone
    assert fingerprint({"crop_jitter_px": 0}) != before


def test_in_8_generations_reupload_settles_and_screenshot_and_forward_does_not(tmp_path):
    """The premise of experiment 7, at small scale, with no AI, over 8 generations.

    Re-uploading at a fixed size and quality reaches a file that no longer changes (here by
    generation 4 or 5). With a screenshot before each upload the picture is resampled every
    pass: every one of the 8 generations is a new file, and the picture ends further from the
    original than the re-uploaded one.

    This is a statement about 8 generations only. Run for longer, this exact-crop chain settles
    as well (around generation 14 to 17 on pictures like this one), because an exact crop
    resamples in the same way every pass. The experiment itself shows what happens over 40.
    """
    upload = StationConfig(kind="platform", params=SMALL_INSTAGRAM)
    screenshot = StationConfig(kind="screenshot", params=SMALL_PHONE)

    reupload = run_small_chain(tmp_path, "reupload", [upload])
    assert first_repeat(reupload) is not None

    forwarded = run_small_chain(tmp_path, "screenshot", [screenshot, upload])
    assert [r.generation for r in forwarded] == list(range(9))
    assert all(r.error is None for r in forwarded)
    assert len({r.output_sha for r in forwarded}) == 9  # no generation repeats an earlier one
    assert all(r.metrics.ssim_to_prev < 1.0 for r in forwarded[1:])
    # the framing is unchanged: every generation is the same 360 x 240 picture, resampled
    assert {(r.metrics.width, r.metrics.height) for r in forwarded[1:]} == {(360, 240)}
    # the damage added up over these passes, and went past what re-uploading alone does
    assert forwarded[8].metrics.ssim_to_g0 < forwarded[1].metrics.ssim_to_g0
    assert forwarded[8].metrics.ssim_to_g0 < reupload[8].metrics.ssim_to_g0


def test_a_screenshot_that_does_not_resample_settles_like_a_reupload(tmp_path):
    """The control for the test above. On a screen exactly as wide as the upload the phone shows
    the picture pixel for pixel, so the loop is a plain re-save again and it settles. It is the
    resampling, not the screenshot's PNG, that keeps the picture changing."""
    upload = StationConfig(kind="platform", params=SMALL_INSTAGRAM)
    same_size_screen = StationConfig(
        kind="screenshot", params={"screen_width": 360, "screen_height": 844}
    )
    recs = run_small_chain(tmp_path, "screenshot_1to1", [same_size_screen, upload])
    assert first_repeat(recs) is not None


def test_a_loose_crop_chain_gives_every_generation_its_own_crop(tmp_path):
    upload = StationConfig(kind="platform", params=SMALL_INSTAGRAM)
    loose = StationConfig(kind="screenshot", params={**SMALL_PHONE, "crop_jitter_px": 6})
    recs = run_small_chain(tmp_path, "screenshot_loose_crop", [loose, upload], generations=4)
    assert all(r.error is None for r in recs)
    for rec in recs[1:]:
        shot = rec.stations[0]
        assert shot.kind == "screenshot" and shot.cached is False
        assert shot.raw["crop"] == crop_offsets(seed=7, generation=rec.generation, jitter=6)
    assert first_repeat(recs) is None
    assert all(r.metrics.ssim_to_prev < 1.0 for r in recs[1:])


# -- experiment 7: the screenshot-and-forward loop -----------------------------------------------

EXP07 = "exp07_screenshot_loop"
UPLOAD = {"kind": "platform", "params": {"preset": "instagram"}}


def test_exp07_has_four_variants_that_differ_only_in_the_screenshot_step():
    exp = load_all()[EXP07]
    assert (exp.generations, exp.seed, exp.repeats) == (40, 7, 1)
    exact = {"kind": "screenshot", "params": {"crop_jitter_px": 0}}
    bilinear = {"kind": "screenshot", "params": {"crop_jitter_px": 0, "resample": "bilinear"}}
    loose = {"kind": "screenshot", "params": {"crop_jitter_px": 6}}
    assert {v["name"]: v["stations"] for v in exp.variants} == {
        "reupload": [UPLOAD],
        "screenshot": [exact, UPLOAD],
        # the same step with the station's other way of resampling: how much an exact-crop
        # screenshot costs depends on it, and a real phone's way is not known
        "screenshot_bilinear": [bilinear, UPLOAD],
        "screenshot_loose_crop": [loose, UPLOAD],
    }
    assert "resampled" in exp.question
    assert any("Ashton" in ref for ref in exp.references)
    assert any("Steyerl" in ref for ref in exp.references)


def test_exp07_says_what_its_numbers_can_and_cannot_show():
    """The experiment page and the export show the description and the notes, so the caveats
    have to be written there, next to the numbers they qualify."""
    exp = load_all()[EXP07]
    description = " ".join(exp.description.split())
    notes = {v["name"]: " ".join((v.get("notes") or "").split()) for v in exp.variants}
    # SSIM is computed on copies 512 px wide, so it cannot see finer detail being lost
    assert "512 px" in description and "finer" in description
    # the phone enlarges the 460 px abstract crop; the reupload control never does. So that
    # photograph is not like for like, and it stays out of the per-variant averages
    assert "460 px" in description and "enlarge" in description
    assert "like for like" in description and "average" in description
    for name in ("screenshot", "screenshot_bilinear", "screenshot_loose_crop"):
        assert "enlarge" in notes[name], name
    # the size of the effect belongs to the way of resampling, and a real phone's is not known
    assert "bicubic" in description and "bilinear" in description
    assert "not known" in description
    # settling is read from SSIM to the previous generation, not from identical files
    assert "1.000000" in description and "byte for byte" in description
    # the control settling is an expectation that is checked, not a fact
    assert "expect" in notes["reupload"].lower() and "checked" in notes["reupload"]
    assert "should sit still" not in notes["reupload"]
    # The loose crop's distance-to-original columns measure the reframing. The note names the
    # columns, so it stays true when a comparison that follows the crop is added beside them.
    loose = notes["screenshot_loose_crop"]
    assert "reframing" in loose and "if nothing had decayed" in loose
    assert "ssim_to_g0" in loose and "ssim_to_prev" in loose
    assert "not measured" not in loose  # would stop being true once that comparison exists
    assert "same crops" in loose  # one seed, one repeat


def test_exp07_runs_keyless_the_same_way_exp01_does():
    exps = load_all()
    exp07, exp01 = exps[EXP07], exps["exp01_compression"]
    assert (exp07.images, exp07.extractor, exp07.metrics) == (
        exp01.images,
        exp01.extractor,
        exp01.metrics,
    )


def test_exp01_and_exp07_prefixes_each_find_exactly_one_experiment():
    ids = sorted(load_all())
    assert [i for i in ids if i.startswith("exp01")] == ["exp01_compression"]
    assert [i for i in ids if i.startswith("exp07")] == [EXP07]
    assert find("exp01").id == "exp01_compression"
    assert find("exp07").id == EXP07


def test_exp07_chains_build_and_cost_nothing(tmp_path):
    img = tmp_path / "street_detail_01.png"
    detailed_image().save(img)
    chains = load_all()[EXP07].chains(images=[img])
    assert [c.chain_id for c in chains] == [
        f"{EXP07}__reupload__street_detail_01",
        f"{EXP07}__screenshot__street_detail_01",
        f"{EXP07}__screenshot_bilinear__street_detail_01",
        f"{EXP07}__screenshot_loose_crop__street_detail_01",
    ]
    assert all(c.generations == 40 and c.seed == 7 for c in chains)
    runner = ChainRunner(options=OFFLINE)  # no extractor, as with --no-extract
    for chain in chains:
        assert runner.estimate(chain) == (0, 0.0)  # no paid calls, no dollars
        assert [build_station(s).kind for s in chain.stations] == [s.kind for s in chain.stations]


def test_doctor_lists_exp07_and_says_it_runs_with_no_extract():
    report = collect()
    exp07 = report["experiments"][EXP07]
    assert exp07["missing_keys"] == ["ANTHROPIC_API_KEY"]  # only the survival form wants a key
    assert "--no-extract" in exp07["status"]
    assert EXP07 in render_text(report)


def test_exp07_dry_run_from_the_command_line_runs_nothing(tmp_path):
    img = tmp_path / "street_detail_01.png"
    detailed_image().save(img)
    result = CliRunner().invoke(
        app, ["run-experiment", "exp07", "--no-extract", "--dry-run", "--image", str(img)]
    )
    assert result.exit_code == 0, result.output
    assert f"{EXP07}: 4 chains" in result.output
    assert "0.000" in result.output  # the estimated cost
    assert not (get_settings().runs_dir / EXP07).exists()


def test_exp07_runs_from_the_command_line_without_a_key(tmp_path):
    img = tmp_path / "street_detail_01.png"
    detailed_image().save(img)
    # exp07 asks for CLIP and LPIPS; a test must not need their weights, so both are off
    args = ["run-experiment", "exp07", "--no-extract", "--no-clip", "--no-lpips"]
    args += ["--image", str(img), "--variant", "screenshot_loose_crop", "--generations", "2"]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    recs = Ledger(get_settings().ledger_path).experiment(EXP07)
    assert [r.generation for r in recs] == [0, 1, 2]
    assert all(r.error is None and r.cost_usd == 0.0 for r in recs)
    assert [s.kind for s in recs[2].stations] == ["screenshot", "platform"]
    assert recs[2].stations[0].raw["displayed_width"] == 1170  # the default phone
    assert recs[2].stations[0].raw["crop"] == crop_offsets(seed=7, generation=2, jitter=6)
    assert recs[2].metrics.width == 1080  # Instagram's size


def test_exp07_rows_export_and_render(tmp_path):
    """The website export and the figures do not depend on a list of station kinds, and the
    loose crop's changing picture size does not upset the contact sheet."""
    img = tmp_path / "street_detail_01.png"
    detailed_image().save(img)
    loose = load_all()[EXP07].chains(images=[img], generations=1)[3]
    assert loose.chain_id == f"{EXP07}__screenshot_loose_crop__street_detail_01"
    ChainRunner(options=OFFLINE).run(loose)

    export_all(tmp_path / "site")
    index = json.loads((tmp_path / "site" / "index.json").read_text())
    assert [e["id"] for e in index["experiments"]] == [EXP07]
    kinds = [[s["kind"] for s in v["stations"]] for v in index["experiments"][0]["variants"]]
    assert kinds == [["platform"]] + [["screenshot", "platform"]] * 3
    chain = json.loads((tmp_path / "site" / "chains" / f"{loose.chain_id}__r0.json").read_text())
    shot = chain["generations"][1]["stations"][0]
    assert shot["kind"] == "screenshot" and shot["params"]["crop_jitter_px"] == 6

    figures = render_all(EXP07, tmp_path / "figures")
    assert all(path.exists() for path in figures)
    assert "ssim_to_g0_by_variant.png" in {path.name for path in figures}
    assert any(path.parent.name == "contact_sheets" for path in figures)


# -- run-chain ------------------------------------------------------------------------------------


def test_run_chain_station_list_understands_screenshot():
    stations = parse_stations("screenshot,platform:instagram", None, None)
    assert [(s.kind, s.params) for s in stations] == [
        ("screenshot", {}),
        ("platform", {"preset": "instagram"}),
    ]
    loose = parse_stations("screenshot:6", None, None)[0]  # the number is crop_jitter_px
    assert (loose.kind, loose.params) == ("screenshot", {"crop_jitter_px": 6})


# -- a wrong setting at the command line: one line, no traceback ----------------------------------


def clean_failure(result) -> str:
    """The command stopped itself with a message. An error that escaped would show up here as
    the exception itself (at a real terminal: a traceback)."""
    assert result.exit_code != 0
    assert isinstance(result.exception, SystemExit), repr(result.exception)
    assert "Traceback" not in result.output
    return result.output


def scratch_experiment(tmp_path: Path, monkeypatch, screenshot_params: dict) -> Path:
    """A scratch project with one experiment, exp90_typo, whose screenshot station has these
    params. Returns a picture to run it on."""
    root = tmp_path / "project"
    (root / "experiments").mkdir(parents=True)
    doc = {
        "id": "exp90_typo",
        "title": "A screenshot loop with a wrong setting",
        "generations": 2,
        "variants": [
            {
                "name": "screenshot",
                "stations": [{"kind": "screenshot", "params": screenshot_params}, UPLOAD],
            }
        ],
    }
    (root / "experiments" / "exp90_typo.yaml").write_text(yaml.safe_dump(doc), encoding="utf-8")
    monkeypatch.setenv("TELEPHONE_ROOT", str(root))
    paths.project_root.cache_clear()
    img = tmp_path / "street_detail_01.png"
    detailed_image().save(img)
    return img


@pytest.mark.parametrize("dry_run", [["--dry-run"], []])
def test_a_misspelt_screenshot_setting_in_an_experiment_is_one_line(tmp_path, monkeypatch, dry_run):
    img = scratch_experiment(tmp_path, monkeypatch, {"crop_jiter_px": 6})
    args = ["run-experiment", "exp90", "--no-extract", "--no-clip", "--image", str(img), *dry_run]
    output = clean_failure(CliRunner().invoke(app, args))
    assert "crop_jiter_px" in output  # the misspelt name, so it can be found and fixed
    assert not (get_settings().runs_dir / "exp90_typo").exists()  # nothing ran


@pytest.mark.parametrize(
    ("stations", "named_in_message"),
    [
        ("screenshot:-2,platform:instagram", "crop_jitter_px"),  # the station's own message
        ("screenshot:abc,platform:instagram", "screenshot:abc"),  # not a number at all
        ("platform:instagram,regenerate:big", "regenerate:big"),
    ],
)
def test_a_wrong_station_setting_in_run_chain_is_one_line(tmp_path, stations, named_in_message):
    img = tmp_path / "street_detail_01.png"
    detailed_image().save(img)
    args = ["run-chain", "--image", str(img), "--stations", stations]
    args += ["--extractor", "none", "--no-clip", "--generations", "1"]
    output = clean_failure(CliRunner().invoke(app, args))
    assert named_in_message in output
    assert not get_settings().ledger_path.exists() or not Ledger(get_settings().ledger_path).all()
