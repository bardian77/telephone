from __future__ import annotations

from pathlib import Path

from telephone.chain import ChainRunner, RunnerOptions
from telephone.config import get_settings
from telephone.experiments import Experiment, load_all
from telephone.fixtures import make_fixture
from telephone.models import ChainConfig, StationConfig


def _chain(img: Path, gens: int = 3) -> ChainConfig:
    return ChainConfig(
        chain_id="t__telephone__x",
        experiment_id="t",
        image=str(img),
        generations=gens,
        seed=3,
        stations=[
            StationConfig(kind="platform", params={"preset": "instagram"}),
            StationConfig(kind="caption", provider="mock", params={"mode": "detailed"}),
            StationConfig(kind="regenerate", provider="mock", params={"size": 256}),
        ],
    )


def test_chain_runs_resumes_and_caches(tmp_path):
    img = make_fixture(tmp_path / "street.png", "street", seed=1)
    opts = RunnerOptions(
        compute_clip=False, extractor=StationConfig(kind="extract", provider="mock")
    )
    events: list[str] = []
    runner = ChainRunner(options=opts, on_event=lambda k, d: events.append(k))
    recs = runner.run(_chain(img))
    assert [r.generation for r in recs] == [0, 1, 2, 3]
    assert all(Path(r.output_path).exists() for r in recs)
    assert recs[0].attributes is not None and recs[0].survival.fraction == 1.0
    g3 = recs[3]
    assert g3.caption and g3.survival is not None and g3.metrics.hist_dist_to_g0 is not None
    assert g3.metrics.ssim_to_g0 is not None and g3.metrics.width == 256 or g3.metrics.height == 256
    assert {s.kind for s in g3.stations} == {"platform", "caption", "regenerate", "extract"}
    assert runner.ledger.has("t__telephone__x", 3)
    # resume: nothing recomputed
    events.clear()
    runner2 = ChainRunner(options=opts, on_event=lambda k, d: events.append(k))
    recs2 = runner2.run(_chain(img))
    assert events.count("resume") == 4 and len(recs2) == 4
    # extend: generations 4 and 5 run from cache misses, earlier ones resume
    recs3 = runner2.run(_chain(img, gens=5))
    assert [r.generation for r in recs3][-2:] == [4, 5]
    assert runner.ledger.total_cost() == (0.0, 0.0)


def test_estimate_counts_paid_calls(tmp_path):
    img = make_fixture(tmp_path / "s.png", "street")
    cfg = _chain(img, gens=4)
    cfg.stations[1].provider = "anthropic"
    cfg.stations[2].provider = "gemini"
    runner = ChainRunner(
        options=RunnerOptions(
            compute_clip=False, extractor=StationConfig(kind="extract", provider="anthropic")
        )
    )
    calls, cost = runner.estimate(cfg)
    assert calls == 4 * 3 + 1  # caption+regen+extract per gen, extract at g0
    # Sonnet caption + extract per generation plus 4 Gemini images at list price (0.039 each)
    assert 0.15 < cost < 0.5


def test_experiments_load_and_expand(tmp_path):
    exps = load_all()  # found from the package location, whatever the cwd
    assert {
        "exp00_smoke",
        "exp01_compression",
        "exp02_caption_length",
        "exp03_system_swap",
        "exp04_photo_types",
        "exp05_mixed_chains",
        "exp06_physical",
    } <= set(exps)
    e: Experiment = exps["exp02_caption_length"]
    imgs = [make_fixture(tmp_path / f"{k}_a.png", k) for k in ("street", "portrait")]
    chains = e.chains(images=imgs)
    assert len(chains) == 3 * 2
    assert chains[0].chain_id.startswith("exp02_caption_length__short__")
    assert e.extractor_config().provider == "anthropic"
    e4 = exps["exp04_photo_types"]
    c4 = e4.chains(images=imgs)
    assert (
        len(c4) == 1 * 2 * 3
        and {c.repeat for c in c4} == {0, 1, 2}
        and len({c.seed for c in c4}) == 3
    )


def test_clip_unavailable_is_graceful(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEPHONE_CLIP_MODEL", "not-a-real-model")
    from telephone.metrics import embed

    embed.ClipEmbedder._instance = None
    img = make_fixture(tmp_path / "p.png", "portrait")
    warnings: list[str] = []
    runner = ChainRunner(
        options=RunnerOptions(compute_clip=True, extractor=None),
        on_event=lambda k, d: warnings.append(d.get("message", "")) if k == "warning" else None,
    )
    recs = runner.run(_chain(img, gens=1))
    assert recs[1].metrics.clip_dist_to_g0 is None and recs[1].metrics.hist_dist_to_g0 is not None
    assert any("CLIP" in w for w in warnings)
    assert get_settings().runs_dir in Path(recs[1].output_path).parents
