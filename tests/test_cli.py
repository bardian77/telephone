from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from telephone.cli import app
from telephone.config import get_settings
from telephone.fixtures import make_fixture
from telephone.ledger import Ledger
from telephone.models import GenerationRecord, Metrics, stable_hash

REPO = Path(__file__).resolve().parents[1]
runner = CliRunner()


def _boom(*_a, **_k):
    raise AssertionError("a provider was requested; --no-extract must make no provider calls")


def test_run_experiment_no_extract_makes_no_provider_calls(tmp_path, monkeypatch):
    img = make_fixture(tmp_path / "street_a.png", "street")
    import telephone.stations.caption as caption
    import telephone.stations.extract as extract
    import telephone.stations.regenerate as regenerate

    monkeypatch.setattr(extract, "get_vision_provider", _boom)
    monkeypatch.setattr(caption, "get_vision_provider", _boom)
    monkeypatch.setattr(regenerate, "get_image_provider", _boom)
    monkeypatch.chdir(REPO)  # experiments/ is still found relative to the repo root
    result = runner.invoke(
        app,
        [
            "run-experiment",
            "exp01",
            "--image",
            str(img),
            "--variant",
            "harsh",
            "--generations",
            "2",
            "--no-extract",
            "--no-clip",
        ],
    )
    assert result.exit_code == 0, result.output
    led = Ledger(get_settings().ledger_path)
    recs = led.experiment("exp01_compression")
    assert [r.generation for r in recs] == [0, 1, 2]
    assert all(r.attributes is None and r.survival is None for r in recs)
    assert all(r.metrics.ssim_to_g0 is not None for r in recs)
    assert led.total_cost() == (0.0, 0.0)


def _rec(chain: str, gen: int, exp: str = "exp01_compression") -> GenerationRecord:
    return GenerationRecord(
        run_id="r1",
        experiment_id=exp,
        chain_id=chain,
        generation=gen,
        station_sequence="platform",
        output_path=f"data/runs/{exp}/{chain}/r0/{gen:03d}.jpg",
        output_sha=stable_hash([chain, gen]),
        metrics=Metrics(ssim_to_g0=1.0 - 0.1 * gen, hist_dist_to_g0=0.05 * gen),
    )


def test_save_and_load_results_round_trip(tmp_path, monkeypatch):
    s = get_settings()
    led = Ledger(s.ledger_path)
    for chain in ("exp01_compression__harsh__b", "exp01_compression__harsh__a"):
        for g in range(3):
            led.append(_rec(chain, g))
    led.append(_rec("exp00_smoke__compression__x", 0, exp="exp00_smoke"))
    led.close()

    result = runner.invoke(app, ["save-results", "exp01_compression"])
    assert result.exit_code == 0, result.output
    out = s.telephone_data_dir / "results" / "exp01_compression.jsonl"
    assert out.exists()
    lines = out.read_text().splitlines()
    assert len(lines) == 6  # only this experiment, one line per generation
    keys = [(json.loads(ln)["chain_id"], json.loads(ln)["generation"]) for ln in lines]
    assert keys == sorted(keys)  # deterministic order: chain, then generation

    # load into a fresh data dir
    fresh = tmp_path / "fresh"
    monkeypatch.setenv("TELEPHONE_DATA_DIR", str(fresh))
    get_settings.cache_clear()
    result = runner.invoke(app, ["load-results", str(out)])
    assert result.exit_code == 0, result.output
    led2 = Ledger(get_settings().ledger_path)
    recs = led2.experiment("exp01_compression")
    assert len(recs) == 6
    assert {r.chain_id for r in recs} == {
        "exp01_compression__harsh__a",
        "exp01_compression__harsh__b",
    }
    assert led2.experiment("exp00_smoke") == []


# -- batch B: usability -------------------------------------------------------------------------


def test_list_works_from_any_folder(tmp_path):
    assert Path.cwd() == tmp_path  # conftest moved us away from the repo
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0, result.output
    assert "exp01_compression" in result.output
    assert not (tmp_path / "experiments").exists()


def test_mock_flag_namespaces_the_experiment(tmp_path):
    img = make_fixture(tmp_path / "street_a.png", "street")
    result = runner.invoke(
        app,
        [
            "run-experiment",
            "exp02",
            "--mock",
            "--image",
            str(img),
            "--variant",
            "short",
            "--generations",
            "1",
            "--no-clip",
        ],
    )
    assert result.exit_code == 0, result.output
    led = Ledger(get_settings().ledger_path)
    assert [row["experiment_id"] for row in led.experiments()] == ["exp02_caption_length-mock"]
    recs = led.experiment("exp02_caption_length-mock")
    assert recs[0].chain_id.startswith("exp02_caption_length-mock__short__street_a")
    assert recs[1].caption and recs[1].attributes is not None
    assert {s.provider for s in recs[1].stations} == {"local", "mock"}


def test_missing_key_is_one_clean_line_and_stops(tmp_path):
    img = make_fixture(tmp_path / "street_a.png", "street")
    result = runner.invoke(
        app,
        ["run-experiment", "exp02", "--image", str(img), "--generations", "1", "--no-clip"],
    )
    assert result.exit_code == 2
    assert "ANTHROPIC_API_KEY" in result.output
    assert "--mock" in result.output
    assert "Traceback" not in result.output
    assert result.output.count("chain failed") == 0


def test_unknown_experiment_is_one_clean_line():
    result = runner.invoke(app, ["run-experiment", "nope"])
    assert result.exit_code == 2
    assert "nope" in result.output and "exp01_compression" in result.output
    assert "Traceback" not in result.output


def test_no_images_message_names_the_right_folder(tmp_path):
    s = get_settings()
    result = runner.invoke(app, ["run-experiment", "exp01", "--no-extract", "--no-clip"])
    assert result.exit_code == 1
    assert str(s.originals_dir) in result.output
    assert "make-fixtures" not in result.output
    result = runner.invoke(app, ["run-experiment", "exp00", "--no-clip"])
    assert result.exit_code == 1
    assert "make-fixtures" in result.output
    result = runner.invoke(
        app, ["run-experiment", "exp01", "--image", str(tmp_path / "x.png"), "--variant", "nope"]
    )
    assert result.exit_code == 1
    assert "variant" in result.output.lower() and "harsh" in result.output


def test_doctor_reports_what_can_run(tmp_path):
    result = runner.invoke(app, ["doctor", "--json"])
    assert result.exit_code == 0, result.output
    d = json.loads(result.output)
    assert d["root"] == str(REPO)
    assert d["keys"]["ANTHROPIC_API_KEY"] is False and d["keys"]["GEMINI_API_KEY"] is False
    assert d["gemini_billing"] == "list price"
    assert d["spend"]["cap_usd"] == 5.0 and d["spend"]["remaining_usd"] == 5.0
    assert "skimage" in d["packages"] and "torch" in d["packages"]
    assert d["photos"]["originals"] == 0 and d["photos"]["private"] == 0
    e1 = d["experiments"]["exp01_compression"]
    assert e1["missing_keys"] == ["ANTHROPIC_API_KEY"] and "--no-extract" in e1["status"]
    e2 = d["experiments"]["exp02_caption_length"]
    assert e2["missing_keys"] == ["ANTHROPIC_API_KEY", "GEMINI_API_KEY"]
    assert d["experiments"]["exp00_smoke"]["missing_keys"] == []
    # the human version mentions the same things
    text = runner.invoke(app, ["doctor"]).output
    assert "ANTHROPIC_API_KEY" in text and "exp01_compression" in text
