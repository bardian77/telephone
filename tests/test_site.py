"""The export the one-page website reads: site.json and the pictures it shows."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from test_detail import SMALL_PHONE, UPLOAD, detailed_image, run_chain
from typer.testing import CliRunner

from telephone.cli import app
from telephone.config import get_settings
from telephone.imageio import media_type_of
from telephone.models import StationConfig
from telephone.site import export_site

LOOSE = StationConfig(kind="screenshot", params={**SMALL_PHONE, "crop_jitter_px": 3})


def two_chains(tmp_path: Path, generations: int = 4) -> None:
    """A re-upload chain and a loose-crop chain on one synthetic picture, with their detail
    results saved the way `telephone detail-test` saves them."""
    run_chain(tmp_path, "reupload", [UPLOAD], generations=generations)
    run_chain(tmp_path, "loose", [LOOSE, UPLOAD], generations=generations)
    assert CliRunner().invoke(app, ["detail-test", "t"]).exit_code == 0


def read(out: Path) -> dict:
    return json.loads((out / "site.json").read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_site_json_has_each_photograph_with_its_journeys_in_the_order_asked(tmp_path):
    two_chains(tmp_path)
    out = tmp_path / "site"
    export_site(out, experiment="t", variants=["reupload", "loose"], passes=[0, 1, 3])
    site = read(out)

    assert site["experiment"] == "t" and site["passes"] == [0, 1, 3]
    assert [p["stem"] for p in site["photos"]] == ["street_test_01"]
    photo = site["photos"][0]
    assert list(photo["journeys"]) == ["reupload", "loose"]
    assert (photo["width"], photo["height"]) == (600, 400)
    for journey in photo["journeys"].values():
        assert [p["pass"] for p in journey["passes"]] == [0, 1, 3]
        # one number per generation, published or not, for the line on the page
        assert all(len(values) == 5 for values in journey["series"].values())
        for p in journey["passes"]:
            assert (out / p["img"]).is_file()


def test_a_published_pass_is_the_file_the_pipeline_wrote_byte_for_byte(tmp_path):
    two_chains(tmp_path)
    out = tmp_path / "site"
    export_site(out, experiment="t", passes=[0, 1, 3])
    from telephone.ledger import Ledger

    rows = {
        (r.chain_id, r.generation): r for r in Ledger(get_settings().ledger_path).experiment("t")
    }
    journey = read(out)["photos"][0]["journeys"]["reupload"]
    for p in journey["passes"][1:]:
        row = rows[("t__reupload__street_test_01", p["pass"])]
        assert sha(out / p["img"]) == row.output_sha  # not re-compressed for the web
        assert p["bytes"] == (out / p["img"]).stat().st_size == row.metrics.file_bytes
        assert media_type_of((out / p["img"]).read_bytes()) == "image/jpeg"
        assert p["reencoded"] is False


def test_pass_0_is_the_authors_own_file_when_it_is_in_the_originals_folder(tmp_path):
    two_chains(tmp_path)
    originals = get_settings().originals_dir
    originals.mkdir(parents=True, exist_ok=True)
    mine = originals / "street_test_01.jpg"
    detailed_image((600, 400)).save(mine, format="JPEG", quality=90)

    out = tmp_path / "site"
    export_site(out, experiment="t", passes=[0, 1])
    first = read(out)["photos"][0]["journeys"]["reupload"]["passes"][0]
    assert sha(out / first["img"]) == sha(mine) and first["reencoded"] is False
    assert first["bytes"] == mine.stat().st_size

    # without it, generation 0 (stored as a PNG) is saved as a JPEG, and the page is told so
    mine.unlink()
    out2 = tmp_path / "site2"
    export_site(out2, experiment="t", passes=[0, 1])
    first = read(out2)["photos"][0]["journeys"]["reupload"]["passes"][0]
    assert first["reencoded"] is True and first["bytes"] is None
    assert media_type_of((out2 / first["img"]).read_bytes()) == "image/jpeg"


def test_the_same_bytes_are_stored_once(tmp_path):
    two_chains(tmp_path)
    out = tmp_path / "site"
    export_site(out, experiment="t", passes=[0, 1, 2, 3, 4])
    journeys = read(out)["photos"][0]["journeys"]
    # both journeys start from the same original
    assert journeys["reupload"]["passes"][0]["img"] == journeys["loose"]["passes"][0]["img"]
    pictures = {p["img"] for j in journeys.values() for p in j["passes"]}
    on_disk = {f"img/{f.name}" for f in (out / "img").iterdir() if "thumb" not in f.name}
    assert on_disk == pictures


def test_detail_numbers_are_attached_and_a_stale_results_file_is_not_trusted(tmp_path):
    two_chains(tmp_path)
    out = tmp_path / "site"
    export_site(out, experiment="t", passes=[0, 1, 3])
    loose = read(out)["photos"][0]["journeys"]["loose"]
    assert loose["passes"][0]["detail"] == {
        "ssim_native": 1.0,
        "detail_kept": 1.0,
        "frame_kept": 1.0,
    }
    assert loose["passes"][2]["detail"]["frame_kept"] < 1.0
    assert loose["series"]["frame_kept"][0] == 1.0 and loose["series"]["frame_kept"][4] < 1.0
    assert loose["passes"][1]["place"] is None  # no place results were saved in this test

    # a results row that was measured on other bytes than the ledger now holds is left out
    results = get_settings().results_dir / "t_detail.jsonl"
    rows = [json.loads(line) for line in results.read_text(encoding="utf-8").splitlines()]
    for row in rows:
        row["output_sha"] = "0" * 64
    results.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    out2 = tmp_path / "site2"
    export_site(out2, experiment="t", passes=[0, 1, 3])
    assert read(out2)["photos"][0]["journeys"]["loose"]["passes"][2]["detail"] is None


def test_place_numbers_are_attached_when_they_were_saved(tmp_path):
    two_chains(tmp_path)
    from telephone.ledger import Ledger

    rec = Ledger(get_settings().ledger_path).get("t__reupload__street_test_01", 1, 0)
    place = {
        "chain_id": rec.chain_id,
        "repeat": 0,
        "generation": 1,
        "output_sha": rec.output_sha,
        "rank": 1,
        "prob": 0.72,
        "top": "Ayton, Testland",
        "place": "Ayton, Testland",
        "lineup_size": 12,
        "clip_model": "fake/build",
    }
    results = get_settings().results_dir / "t_place.jsonl"
    results.write_text(json.dumps(place) + "\n", encoding="utf-8")
    out = tmp_path / "site"
    export_site(out, experiment="t", passes=[0, 1])
    site = read(out)
    journey = site["photos"][0]["journeys"]["reupload"]
    assert journey["passes"][1]["place"] == {
        "rank": 1,
        "prob": 0.72,
        "top": "Ayton, Testland",
        "place": "Ayton, Testland",
        "lineup_size": 12,
    }
    assert journey["series"]["place_prob"] == [None, 0.72, None, None, None]
    assert site["made_with"]["clip_model"] == "fake/build"


def test_settled_at_is_the_first_pass_that_changes_nothing(tmp_path):
    run_chain(tmp_path, "reupload", [UPLOAD], generations=8)
    run_chain(tmp_path, "loose", [LOOSE, UPLOAD], generations=8)
    out = tmp_path / "site"
    export_site(out, experiment="t", passes=[0, 1])
    journeys = read(out)["photos"][0]["journeys"]
    settled = journeys["reupload"]["settled_at"]
    assert settled is not None and 1 < settled <= 8
    assert journeys["reupload"]["series"]["ssim_to_prev"][settled] == 1.0
    assert journeys["loose"]["settled_at"] is None  # a new crop every pass


def test_each_photograph_gets_a_small_thumbnail_for_the_picker(tmp_path):
    two_chains(tmp_path)
    out = tmp_path / "site"
    export_site(out, experiment="t", passes=[0, 1])
    photo = read(out)["photos"][0]
    thumb = out / photo["thumb"]
    assert thumb.is_file() and thumb.stat().st_size < 40_000


def test_a_private_photograph_is_never_exported(tmp_path):
    two_chains(tmp_path)
    s = get_settings()
    s.private_dir.mkdir(parents=True, exist_ok=True)
    (s.private_dir / "street_test_01.jpg").write_bytes(b"x")
    with pytest.raises(ValueError, match="Nothing to export"):
        export_site(tmp_path / "site", experiment="t", passes=[0, 1])
    assert not (tmp_path / "site" / "site.json").exists()


def test_mock_runs_and_unknown_experiments_are_refused(tmp_path):
    two_chains(tmp_path)
    with pytest.raises(ValueError, match="mock"):
        export_site(tmp_path / "site", experiment="t-mock")
    with pytest.raises(ValueError, match="No experiment"):
        export_site(tmp_path / "site", experiment="nothing_like_this")


def test_the_export_refuses_to_grow_past_its_size_limit(tmp_path):
    two_chains(tmp_path)
    with pytest.raises(ValueError, match="MB"):
        export_site(tmp_path / "site", experiment="t", passes=[0, 1, 3], max_mb=0.001)


def test_the_export_replaces_what_was_there_before(tmp_path):
    two_chains(tmp_path)
    out = tmp_path / "site"
    export_site(out, experiment="t", passes=[0, 1, 2, 3])
    before = {f.name for f in (out / "img").iterdir()}
    export_site(out, experiment="t", passes=[0, 1])
    after = {f.name for f in (out / "img").iterdir()}
    assert after < before  # pictures no longer on the page are not left lying around


def test_export_site_from_the_command_line(tmp_path):
    two_chains(tmp_path)
    out = tmp_path / "site"
    result = CliRunner().invoke(
        app, ["export-site", "t", "--out", str(out), "--passes", "0,1,3", "--variants", "loose"]
    )
    assert result.exit_code == 0, result.output
    site = read(out)
    assert list(site["photos"][0]["journeys"]) == ["loose"]
    assert "site.json" in result.output and "MB" in result.output

    result = CliRunner().invoke(app, ["export-site", "nothing_like_this", "--out", str(out)])
    assert result.exit_code == 1 and "Traceback" not in result.output
