"""The dashboard: plain-language readings of results, and the local API behind the browser UI.

Everything here runs on mock providers or on compression only. Nothing is paid.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from telephone.models import (
    Attributes,
    GenerationRecord,
    Metrics,
    StationRecord,
)

REPO = Path(__file__).resolve().parents[1]


# -- reading: numbers into plain words ------------------------------------------------------


def _rec(
    gen, clip, ssim=None, size=1000, exp="exp01_compression", stations=None, seq="platform", **kw
):
    return GenerationRecord(
        run_id="t",
        experiment_id=exp,
        chain_id=f"{exp}__harsh__street_a_01",
        generation=gen,
        station_sequence=seq,
        stations=stations or [],
        output_path=f"data/runs/x/{gen:03d}.jpg",
        output_sha="s",
        metrics=Metrics(
            clip_dist_to_g0=clip, ssim_to_g0=ssim, file_bytes=size, width=100, height=80
        ),
        **kw,
    )


def test_drift_position_is_a_fraction_of_the_way_to_a_different_photograph():
    from telephone.dashboard.reading import DIFFERENT_PHOTO_CLIP, drift_position

    assert drift_position(0.0) == 0.0
    assert drift_position(DIFFERENT_PHOTO_CLIP / 2) == pytest.approx(0.5)
    assert drift_position(5.0) == 1.0  # capped: the scale ends at "a different photograph"
    assert drift_position(None) is None


def test_drift_band_names_follow_the_scale():
    from telephone.dashboard.reading import drift_band

    assert drift_band(0.01)["key"] == "same"
    assert drift_band(0.09)["key"] == "worn"
    assert drift_band(0.2)["key"] == "drifting"
    assert drift_band(0.4)["key"] == "different"
    assert drift_band(None)["key"] == "unknown"
    assert all(drift_band(v)["label"] for v in (0.01, 0.09, 0.2, 0.4, None))


def test_settled_generation_is_where_the_numbers_stop_moving():
    from telephone.dashboard.reading import settled_generation

    assert settled_generation([0.0, 0.089, 0.089, 0.088, 0.089]) == 1
    assert settled_generation([0.0, 0.1, 0.2, 0.3, 0.4]) is None  # still moving at the end
    assert settled_generation([0.0, 0.1, 0.2, 0.3, 0.3, 0.3]) == 3
    assert settled_generation([0.0]) is None


def test_reading_of_a_compression_chain_says_the_first_upload_did_the_damage():
    from telephone.dashboard.reading import chain_reading

    recs = [_rec(0, 0.0, 1.0, size=400_000)] + [
        _rec(g, 0.02, 0.975, size=100_000) for g in range(1, 6)
    ]
    r = chain_reading(recs)
    assert r["kind"] == "compression"
    assert r["simulation"] is False
    assert r["settled_at"] == 1
    assert "first" in r["headline"].lower()
    labels = {f["label"] for f in r["facts"]}
    assert {"Drift", "File size"} <= labels
    size = next(f for f in r["facts"] if f["label"] == "File size")
    assert "25%" in size["meaning"]


def test_reading_marks_mock_runs_as_simulations_and_reports_lost_facts():
    from telephone.dashboard.reading import chain_reading
    from telephone.metrics.survival import compare_attributes

    def attrs(text, people):
        return Attributes(
            objects=["arch", "bicycle"],
            people_count=people,
            visible_text=text,
            setting="arcade street in Bologna",
            lighting="golden hour",
            mood="calm",
            dominant_colors=["orange"],
            camera_angle="eye level",
            is_photograph=True,
        )

    a0 = attrs(["Seddon House"], 3)
    mock = [StationRecord(kind="caption", provider="mock"), StationRecord(kind="regenerate")]
    seq = "platform > caption > regenerate"
    recs = [_rec(0, 0.0, exp="exp02_caption_length-mock", attributes=a0, seq=seq)]
    recs[0].survival = compare_attributes(a0, a0)
    for g, a in ((1, attrs(["Seddon House"], 3)), (2, attrs([], 3)), (3, attrs([], 0))):
        r = _rec(g, 0.1 * g, exp="exp02_caption_length-mock", stations=mock, attributes=a, seq=seq)
        r.survival = compare_attributes(a0, a)
        r.caption = "an arcade"
        recs.append(r)
    out = chain_reading(recs)
    assert out["simulation"] is True
    assert out["kind"] == "ai"
    surv = out["survival"]
    assert surv["alive"] == 7 and surv["total"] == 9
    assert [f["field"] for f in surv["lost"]] == ["visible_text", "people_count"]
    assert surv["lost"][0]["generation"] == 2
    assert surv["lost"][0]["label"] == "Readable text"


def test_photo_and_variant_names_are_made_readable():
    from telephone.dashboard.reading import photo_label, variant_label

    assert photo_label("street_bologna_portici_01") == {
        "name": "Bologna portici 01",
        "type": "street",
    }
    assert photo_label("IMG1234")["name"] == "IMG1234"
    assert variant_label("screenshot_whatsapp") == "Screenshot WhatsApp"


# -- the API --------------------------------------------------------------------------------


@pytest.fixture
def client(monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from telephone.dashboard.server import create_app

    monkeypatch.chdir(REPO)  # experiments/ is found from the repo root; data stays in tmp_path
    from telephone import paths

    paths.project_root.cache_clear()
    app = create_app()
    with TestClient(app) as c:
        yield c


def _wait(client, timeout=60.0):
    end = time.time() + timeout
    while time.time() < end:
        job = client.get("/api/runs/current").json()["job"]
        if job and job["status"] in ("done", "failed", "stopped"):
            return job
        time.sleep(0.05)
    raise AssertionError("the run did not finish in time")


def test_overview_reports_keys_budget_and_what_can_run(client):
    d = client.get("/api/overview").json()
    assert d["keys"]["ANTHROPIC_API_KEY"] is False
    assert d["spend"]["cap_usd"] == 5 and d["spend"]["paid_usd"] == 0
    exps = {e["id"]: e for e in d["experiments"]}
    assert "simulation" in exps["exp00_smoke"]["modes"]
    assert "real" not in exps["exp02_caption_length"]["modes"]
    assert exps["exp02_caption_length"]["missing_keys"]
    assert "free" in exps["exp01_compression"]["modes"]
    assert d["job"] is None


def test_static_page_is_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "Telephone" in r.text
    assert client.get("/static/app.css").status_code == 200
    assert client.get("/static/app.js").status_code == 200


def test_a_simulation_runs_and_its_results_can_be_read(client):
    r = client.post(
        "/api/runs",
        json={"experiment": "exp00_smoke", "mode": "simulation", "generations": 2, "clip": False},
    )
    assert r.status_code == 200, r.text
    job = _wait(client)
    assert job["status"] == "done", job
    assert job["chains_total"] == 10 and job["chains_done"] == 10
    assert job["result_experiment"] == "exp00_smoke"

    results = client.get("/api/results").json()["experiments"]
    row = next(e for e in results if e["id"] == "exp00_smoke")
    assert row["simulation"] is True and row["chains"] == 10

    exp = client.get("/api/results/exp00_smoke").json()
    assert len(exp["chains"]) == 10
    chain = next(c for c in exp["chains"] if c["variant"] == "telephone")
    assert chain["reading"]["simulation"] is True

    detail = client.get(f"/api/chains/{chain['key']}").json()
    assert [g["generation"] for g in detail["generations"]] == [0, 1, 2]
    assert detail["generations"][1]["caption"]
    assert detail["generations"][1]["survival"]["fields"]
    assert detail["stations"][0]["kind"] == "platform"

    img = client.get(f"/api/image/chain/{chain['key']}/1?w=200")
    assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg"
    assert client.get(f"/api/image/chain/{chain['key']}/99").status_code == 404
    assert client.get("/api/chains/nope__r0").status_code == 404


def test_a_real_run_without_keys_is_refused_with_the_missing_key_named(client):
    r = client.post("/api/runs", json={"experiment": "exp02_caption_length", "mode": "real"})
    assert r.status_code == 409
    assert "ANTHROPIC_API_KEY" in r.json()["detail"]


def test_estimate_says_what_a_run_would_cost_before_it_starts(client):
    from telephone.config import get_settings
    from telephone.fixtures import make_fixture

    none = client.post(
        "/api/estimate", json={"experiment": "exp02_caption_length", "mode": "simulation"}
    )
    assert none.status_code == 409 and "photographs" in none.json()["detail"]
    make_fixture(get_settings().originals_dir / "street_public_01.png", "street")
    r = client.post(
        "/api/estimate", json={"experiment": "exp02_caption_length", "mode": "simulation"}
    )
    assert r.status_code == 200
    d = r.json()
    assert d["estimate_usd"] == 0 and d["needs_confirmation"] is False
    assert d["chains"] == 3 and d["result_experiment"] == "exp02_caption_length-mock"


def test_a_paid_run_needs_the_estimate_confirmed():
    from telephone.dashboard.service import RunRefused, check_budget

    check_budget(0.0, confirm_usd=None, remaining=5.0)  # free: nothing to confirm
    with pytest.raises(RunRefused, match="confirm"):
        check_budget(0.42, confirm_usd=None, remaining=5.0)
    check_budget(0.42, confirm_usd=0.42, remaining=5.0)
    with pytest.raises(RunRefused, match="budget"):
        check_budget(6.0, confirm_usd=6.0, remaining=5.0)


def test_requests_from_another_site_cannot_start_a_run(client):
    r = client.post(
        "/api/runs",
        json={"experiment": "exp00_smoke", "mode": "simulation", "clip": False},
        headers={"Origin": "http://evil.example"},
    )
    assert r.status_code == 403


def test_private_photographs_are_never_listed_or_served(client):
    from telephone.config import get_settings
    from telephone.fixtures import make_fixture

    s = get_settings()
    make_fixture(s.originals_dir / "street_public_01.png", "street")
    make_fixture(s.private_dir / "portrait_secret_01.png", "portrait")
    stems = [p["stem"] for p in client.get("/api/overview").json()["photos"]]
    assert stems == ["street_public_01"]
    assert client.get("/api/image/photo/street_public_01?w=120").status_code == 200
    assert client.get("/api/image/photo/portrait_secret_01").status_code == 404


def test_saved_results_can_be_loaded_from_the_dashboard(client):
    from telephone.config import get_settings

    s = get_settings()
    s.results_dir.mkdir(parents=True, exist_ok=True)
    rec = _rec(0, 0.0, 1.0)
    (s.results_dir / "exp01_compression.jsonl").write_text(rec.model_dump_json() + "\n")
    saved = client.get("/api/overview").json()["saved_results"]
    assert saved == [{"experiment": "exp01_compression", "rows": 1, "loaded": False}]
    r = client.post("/api/actions/load-saved", json={"experiment": "exp01_compression"})
    assert r.status_code == 200 and r.json()["rows"] == 1
    assert client.get("/api/overview").json()["saved_results"][0]["loaded"] is True
    exp = client.get("/api/results/exp01_compression").json()
    assert exp["chains"][0]["images_available"] is False


def test_cli_has_a_dashboard_command():
    from typer.testing import CliRunner

    from telephone.cli import app

    out = CliRunner().invoke(app, ["dashboard", "--help"])
    assert out.exit_code == 0 and "browser" in out.output.lower()


def test_file_size_is_compared_with_the_photograph_not_the_lossless_copy():
    from telephone.dashboard.reading import chain_reading

    # generation 0 is stored as a large PNG copy; the photograph itself was a 200 kB JPEG
    recs = [_rec(0, 0.0, 1.0, size=2_000_000)] + [_rec(g, 0.02, 0.97, size=50_000) for g in (1, 2)]
    size = next(f for f in chain_reading(recs, 200_000)["facts"] if f["label"] == "File size")
    assert size["value"] == "200 kB to 50 kB" and "25%" in size["meaning"]
    tiny = [_rec(0, 0.0, 1.0, size=2_000_000)] + [_rec(g, 0.1, 0.8, size=9_000) for g in (1, 2)]
    size = next(f for f in chain_reading(tiny)["facts"] if f["label"] == "File size")
    assert size["meaning"].startswith("Less than 1%")


def test_the_dashboard_works_behind_a_proxy_but_still_refuses_other_sites(client):
    body = {"experiment": "exp02_caption_length", "mode": "simulation"}
    # a preview pane or reverse proxy forwards the public host name
    ok = client.post(
        "/api/estimate",
        json=body,
        headers={"Origin": "https://preview.example", "X-Forwarded-Host": "preview.example"},
    )
    assert ok.status_code != 403
    # a form on another site can only send a simple content type: that is not accepted as JSON
    import json

    plain = client.post(
        "/api/estimate", content=json.dumps(body), headers={"Content-Type": "text/plain"}
    )
    assert plain.status_code == 422


def test_band_wording_describes_the_models_score_not_what_a_person_sees():
    from telephone.dashboard.reading import BANDS, chain_reading

    assert all("comparison model" in meaning for _, _, _, meaning in BANDS)
    recs = [_rec(0, 0.0, 1.0)] + [_rec(g, 0.17, 0.75) for g in (1, 2, 3)]
    assert "comparison model scores" in chain_reading(recs)["headline"]
