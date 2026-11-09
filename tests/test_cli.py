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
