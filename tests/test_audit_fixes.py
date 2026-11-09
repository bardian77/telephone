"""Tests for the bugs found in the November 2026 audit of the core loop.

1. chain identity ignores providers and models (a real run could resume mock rows)
2. the spend cap resets every process instead of counting lifetime spend
3. Gemini is costed at $0 by default
6. exp06's '{image_stem}' placeholder is never substituted and station configs are shared

Bugs 4 and 5 (committed ledger, JSONL drift) are structural and are covered by test_core.py.
Everything here runs on mock providers or stubbed clients; nothing calls a paid API.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from telephone import cost
from telephone.chain import ChainRunner, RunnerOptions
from telephone.config import Settings, get_settings
from telephone.experiments import load_all, mockify
from telephone.fixtures import make_fixture
from telephone.ledger import Ledger
from telephone.models import ChainConfig, StationConfig, Usage

EXPERIMENTS = Path(__file__).resolve().parents[1] / "experiments"


# -- bug 1: chain identity -------------------------------------------------------------------


def _chain(img: Path, caption_model: str | None = None, gens: int = 2) -> ChainConfig:
    return ChainConfig(
        chain_id="t__telephone__x",
        experiment_id="t",
        image=str(img),
        generations=gens,
        seed=3,
        stations=[
            StationConfig(kind="platform", params={"preset": "instagram"}),
            StationConfig(
                kind="caption", provider="mock", model=caption_model, params={"mode": "short"}
            ),
            StationConfig(kind="regenerate", provider="mock", params={"size": 256}),
        ],
    )


def test_changed_provider_config_is_not_resumed(tmp_path):
    img = make_fixture(tmp_path / "street.png", "street", seed=1)
    opts = RunnerOptions(compute_clip=False, extractor=None)
    events: list[str] = []
    runner = ChainRunner(options=opts, on_event=lambda k, d: events.append(k))
    first = runner.run(_chain(img))
    assert first[1].stations[1].model == "mock-vision"
    assert all(r.config_sha for r in first)

    # same chain id, same image, but the captioner's model changed: nothing may be resumed
    events.clear()
    second = ChainRunner(options=opts, on_event=lambda k, d: events.append(k)).run(
        _chain(img, caption_model="mock-vision-b")
    )
    assert events.count("resume") == 0
    assert second[1].stations[1].model == "mock-vision-b"
    assert second[1].config_sha != first[1].config_sha

    # unchanged config resumes everything again
    events.clear()
    ChainRunner(options=opts, on_event=lambda k, d: events.append(k)).run(
        _chain(img, caption_model="mock-vision-b")
    )
    assert events.count("resume") == 3


def test_fingerprint_treats_default_and_explicit_provider_alike(tmp_path):
    img = make_fixture(tmp_path / "s.png", "street")
    opts = RunnerOptions(compute_clip=False, extractor=None)
    a = ChainConfig(
        chain_id="t__c__x",
        experiment_id="t",
        image=str(img),
        generations=1,
        stations=[StationConfig(kind="platform")],
    )
    b = ChainConfig(
        chain_id="t__c__x",
        experiment_id="t",
        image=str(img),
        generations=1,
        stations=[StationConfig(kind="platform", params={})],
    )
    r1 = ChainRunner(options=opts).run(a)
    events: list[str] = []
    ChainRunner(options=opts, on_event=lambda k, d: events.append(k)).run(b)
    assert events.count("resume") == 2 and r1[0].config_sha


def test_errored_generation_zero_is_not_resumed(tmp_path):
    img = make_fixture(tmp_path / "s.png", "street")
    led = Ledger(get_settings().ledger_path)
    opts = RunnerOptions(compute_clip=False, extractor=None)
    runner = ChainRunner(ledger=led, options=opts)
    cfg = ChainConfig(
        chain_id="t__c__x",
        experiment_id="t",
        image=str(img),
        generations=1,
        stations=[StationConfig(kind="platform")],
    )
    recs = runner.run(cfg)
    g0 = recs[0].model_copy(update={"error": "extract: declined"})
    led.append(g0)
    events: list[str] = []
    out = ChainRunner(ledger=led, options=opts, on_event=lambda k, d: events.append(k)).run(cfg)
    assert out[0].error is None
    assert events.count("resume") <= 1  # g1 may resume; the errored g0 must be redone


def test_mockify_namespaces_the_experiment_and_forces_mock_providers():
    exp = load_all(EXPERIMENTS)["exp02_caption_length"]
    chain = exp.chains(images=[Path("data/originals/street_a.jpg")])[0]
    m = mockify(chain)
    assert m.experiment_id == "exp02_caption_length-mock"
    assert m.chain_id.startswith("exp02_caption_length-mock__short__street_a")
    assert all(s.provider == "mock" and s.model is None for s in m.stations if s.kind != "platform")
    # the original is untouched and the namespace survives the id parser
    assert chain.experiment_id == "exp02_caption_length"
    from telephone.render import image_of, variant_of

    assert variant_of(m.chain_id) == "short" and image_of(m.chain_id) == "street_a"
    # an experiment that already runs on mock providers keeps its id
    smoke = load_all(EXPERIMENTS)["exp00_smoke"].chains(images=[Path("x/street_f.png")])[1]
    assert mockify(smoke).experiment_id == "exp00_smoke"


# -- bug 2: lifetime spend -------------------------------------------------------------------


def test_spend_log_seeds_the_tracker_across_processes():
    s = get_settings()
    led = Ledger(s.ledger_path)
    led.log_spend("anthropic", "claude-sonnet-5-5", cost_usd=3.0, list_price_usd=3.0)
    led.log_spend("gemini", "gemini-2.5-flash-image", cost_usd=1.99, list_price_usd=1.99)
    assert led.total_spend() == (pytest.approx(4.99), pytest.approx(4.99))
    led.close()

    cost._tracker = None  # a new process
    t = cost.get_tracker()
    assert t.total_usd == pytest.approx(4.99)
    with pytest.raises(cost.SpendCapExceeded):
        t.reserve(0.02)  # cap in tests is 5.0 (conftest)
    assert t.remaining() == pytest.approx(0.01)


def test_commit_appends_to_the_spend_log():
    cost._tracker = None
    t = cost.get_tracker()
    t.commit(Usage(cost_usd=0.25, list_price_usd=0.5), provider="openai", model="gpt-5-mini")
    paid, listp = Ledger(get_settings().ledger_path).total_spend()
    assert paid == pytest.approx(0.25) and listp == pytest.approx(0.5)
    cost._tracker = None
    assert cost.get_tracker().total_usd == pytest.approx(0.25)


# -- bug 3: Gemini billing -------------------------------------------------------------------


def _fake_gemini_client(png: bytes):
    def generate_content(model, contents, config=None):
        part = SimpleNamespace(inline_data=SimpleNamespace(data=png), text=None)
        cand = SimpleNamespace(content=SimpleNamespace(parts=[part]), finish_reason="STOP")
        return SimpleNamespace(
            candidates=[cand],
            text="a quiet harbour at dusk",
            parsed=None,
            usage_metadata=SimpleNamespace(prompt_token_count=1000, candidates_token_count=100),
            model_version="gemini-test",
        )

    return SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))


def test_gemini_is_billed_unless_free_tier_is_declared(monkeypatch, test_image):
    assert Settings(_env_file=None).gemini_free_tier is False

    from telephone.imageio import load_image, to_png_bytes
    from telephone.providers import gemini

    png = to_png_bytes(load_image(test_image))
    monkeypatch.setattr(gemini, "_client", lambda api_key=None: _fake_gemini_client(png))
    monkeypatch.setattr(gemini, "wait_for", lambda name: 0.0)
    cost._tracker = None

    gen = gemini.GeminiImageGen(api_key="x")
    data, usage, meta = gen.generate("a cat")
    assert data == png
    assert usage.cost_usd == pytest.approx(0.039) == usage.list_price_usd
    assert cost.get_tracker().total_usd == pytest.approx(0.039)

    text, usage2, _ = gemini.GeminiVision(api_key="x").caption(png, "short")
    assert usage2.cost_usd > 0 and usage2.cost_usd == pytest.approx(usage2.list_price_usd)

    # opting in to the free tier is explicit
    monkeypatch.setenv("GEMINI_FREE_TIER", "1")
    get_settings.cache_clear()
    cost._tracker = None
    _, usage3, _ = gemini.GeminiImageGen(api_key="x").generate("a cat")
    assert usage3.cost_usd == 0.0 and usage3.list_price_usd == pytest.approx(0.039)


def test_estimates_price_gemini_when_not_free():
    from telephone.stations import build_station

    cap = build_station(StationConfig(kind="caption", provider="gemini"))
    ext = build_station(StationConfig(kind="extract", provider="gemini"))
    gen = build_station(StationConfig(kind="regenerate", provider="gemini"))
    assert cap.estimated_cost_usd() > 0 and ext.estimated_cost_usd() > 0
    assert gen.estimated_cost_usd() == pytest.approx(0.039)


# -- bug 6: exp06 placeholder ----------------------------------------------------------------


def test_exp06_placeholder_is_filled_per_image(tmp_path):
    exp = load_all(EXPERIMENTS)["exp06_physical"]
    chains = exp.chains(images=[tmp_path / "a.png", tmp_path / "b.png"])
    folders = [c.stations[0].params["folder"] for c in chains]
    assert folders == ["data/physical/a", "data/physical/b"]
    assert chains[0].stations[0] is not chains[1].stations[0]
    assert chains[0].stations[0].params is not chains[1].stations[0].params


def test_physical_station_refuses_an_unfilled_placeholder(tmp_path, test_image):
    from telephone.cache import StationCache
    from telephone.imageio import load_image, sha256_bytes, to_png_bytes
    from telephone.stations import build_station
    from telephone.stations.base import StationContext

    cfg = StationConfig(kind="physical", params={"folder": "data/physical/{image_stem}"})
    chain = ChainConfig(
        chain_id="t", experiment_id="t", image="x.jpg", stations=[cfg], generations=1, seed=1
    )
    ctx = StationContext(
        settings=get_settings(),
        cache=StationCache(tmp_path / "c"),
        chain=chain,
        generation=1,
        seed=1,
    )
    png = to_png_bytes(load_image(test_image))
    with pytest.raises(ValueError, match="image_stem"):
        build_station(cfg).run(png, sha256_bytes(png), ctx)
