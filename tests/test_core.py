from __future__ import annotations

import json

import pytest

from telephone.cache import StationCache
from telephone.cost import SpendCapExceeded, SpendTracker, image_list_price, text_list_price
from telephone.imageio import from_bytes, load_image, sha256_bytes, to_jpeg_bytes, to_png_bytes
from telephone.ledger import Ledger
from telephone.models import GenerationRecord, Metrics, StationRecord, Usage, stable_hash
from telephone.ratelimit import TokenBucket


def test_stable_hash_is_order_independent():
    assert stable_hash({"a": 1, "b": [1, 2]}) == stable_hash({"b": [1, 2], "a": 1})
    assert stable_hash({"a": 1}) != stable_hash({"a": 2})


def test_image_roundtrip(test_image):
    img = load_image(test_image)
    png = to_png_bytes(img)
    assert from_bytes(png).size == img.size
    jpg_hi = to_jpeg_bytes(img, quality=95)
    jpg_lo = to_jpeg_bytes(img, quality=20)
    assert len(jpg_lo) < len(jpg_hi)
    assert sha256_bytes(png) == sha256_bytes(to_png_bytes(img))


def test_prices():
    assert text_list_price("claude-sonnet-5-5", 1_000_000, 0) == pytest.approx(2.0)
    assert text_list_price("claude-haiku-5-5", 0, 1_000_000) == pytest.approx(0.5)
    assert image_list_price("gemini-2.5-flash-image") == pytest.approx(0.039)
    assert image_list_price("mock") == 0


def test_spend_cap_blocks_before_call():
    t = SpendTracker(cap_usd=0.01)
    t.reserve(0.005)
    t.commit(Usage(cost_usd=0.005, list_price_usd=0.005))
    with pytest.raises(SpendCapExceeded):
        t.reserve(0.006)
    assert t.remaining() == pytest.approx(0.005)


def test_cache_roundtrip(tmp_path):
    c = StationCache(tmp_path / "cache")
    key = StationCache.key("abc", "platform", None, None, {"q": 50}, None)
    assert c.get(key) is None
    rec = StationRecord(kind="platform", params={"q": 50})
    c.put(key, rec, b"bytes")
    got = c.get(key)
    assert got is not None
    rec2, data = got
    assert rec2.cached is True and data == b"bytes"
    assert c.stats() == {"hits": 1, "misses": 1}
    assert StationCache.key("abc", "platform", None, None, {"q": 51}, None) != key


def _rec(chain="c1", gen=0, exp="exp01", cost=0.01, **kw) -> GenerationRecord:
    return GenerationRecord(
        run_id="r1",
        experiment_id=exp,
        chain_id=chain,
        generation=gen,
        station_sequence="platform",
        output_path=f"{chain}/{gen:03d}.png",
        output_sha=stable_hash([chain, gen]),
        metrics=Metrics(clip_dist_to_g0=0.1 * gen),
        cost_usd=cost,
        list_price_usd=cost,
        **kw,
    )


def test_ledger_append_query(tmp_path):
    led = Ledger(tmp_path / "l.sqlite")
    for g in range(3):
        led.append(_rec(gen=g))
    led.append(_rec(chain="c2", gen=0, exp="exp02"))
    assert led.has("c1", 2) and not led.has("c1", 3)
    assert [r.generation for r in led.chain("c1")] == [0, 1, 2]
    assert len(led.experiment("exp01")) == 3
    chains = led.chains()
    assert {c["chain_id"] for c in chains} == {"c1", "c2"}
    assert led.total_cost()[0] == pytest.approx(0.04)
    # replace on same key, not duplicate
    led.append(_rec(gen=2, cost=0.5))
    assert len(led.chain("c1")) == 3
    assert led.chain("c1")[2].cost_usd == pytest.approx(0.5)
    # errored rows do not count as done
    led.append(_rec(chain="c3", gen=0, error="boom"))
    assert not led.has("c3", 0)


def test_results_snapshot_matches_sqlite_after_replacements(tmp_path):
    """The saved JSONL is a snapshot of SQLite, so re-appending a key never duplicates a line."""
    led = Ledger(tmp_path / "l.sqlite")
    for g in range(3):
        led.append(_rec(gen=g))
    led.append(_rec(gen=2, cost=0.5))  # replaced, not duplicated
    led.append(_rec(chain="c0", gen=0))  # sorts before c1
    out = tmp_path / "results" / "exp01.jsonl"
    assert led.save_results("exp01", out) == 4
    lines = [json.loads(ln) for ln in out.read_text().splitlines()]
    assert [(r["chain_id"], r["generation"]) for r in lines] == [
        ("c0", 0),
        ("c1", 0),
        ("c1", 1),
        ("c1", 2),
    ]
    assert lines[3]["cost_usd"] == pytest.approx(0.5)
    # saving again rewrites the file whole instead of appending
    assert led.save_results("exp01", out) == 4
    assert out.read_text().count("\n") == 4
    led.close()
    led2 = Ledger(tmp_path / "l2.sqlite")
    assert led2.import_jsonl(out) == 4
    assert [r.to_row() for r in led2.experiment("exp01")] == lines


def test_token_bucket_waits():
    b = TokenBucket(rate_per_minute=6000, burst=1)  # 100/s
    assert b.acquire() == 0
    waited = b.acquire()
    assert 0 < waited < 0.5
