from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from telephone.cache import StationCache
from telephone.config import get_settings
from telephone.imageio import from_bytes, load_image, sha256_bytes, to_png_bytes
from telephone.models import ChainConfig, StationConfig
from telephone.stations import MissingFrame, build_station
from telephone.stations.base import StationContext


def ctx_for(tmp_path: Path, stations, caption=None, generation=1) -> StationContext:
    chain = ChainConfig(
        chain_id="t", experiment_id="test", image="x.jpg", stations=stations, generations=3, seed=1
    )
    return StationContext(
        settings=get_settings(),
        cache=StationCache(tmp_path / "cache"),
        chain=chain,
        generation=generation,
        seed=1,
        caption=caption,
    )


def test_platform_station_shrinks_and_strips(tmp_path, test_image):
    img = load_image(test_image)
    png = to_png_bytes(img)
    cfg = StationConfig(kind="platform", params={"preset": "harsh"})
    st = build_station(cfg)
    res = st.run(png, sha256_bytes(png), ctx_for(tmp_path, [cfg]))
    assert res.image is not None
    out = from_bytes(res.image)
    assert max(out.size) == 512
    assert len(res.image) < len(png)
    assert Image.open(__import__("io").BytesIO(res.image)).info.get("exif") is None
    assert res.record.params["quality"] == 30
    # second run is a cache hit
    res2 = st.run(png, sha256_bytes(png), ctx_for(tmp_path, [cfg]))
    assert res2.record.cached is True and res2.image == res.image


def test_caption_regenerate_extract_with_mocks(tmp_path, test_image):
    png = to_png_bytes(load_image(test_image))
    cap_cfg = StationConfig(kind="caption", provider="mock", params={"mode": "detailed"})
    gen_cfg = StationConfig(kind="regenerate", provider="mock", params={"size": 256})
    ext_cfg = StationConfig(kind="extract", provider="mock")
    ctx = ctx_for(tmp_path, [cap_cfg, gen_cfg])
    cap = build_station(cap_cfg).run(png, sha256_bytes(png), ctx)
    assert cap.caption and "photograph" in cap.caption
    assert cap.image == png  # passthrough
    ctx.caption = cap.caption
    gen = build_station(gen_cfg).run(png, sha256_bytes(png), ctx)
    assert gen.image is not None and gen.record.seed == 1 * 1000 + 1
    assert gen.record.prompt_or_caption == cap.caption
    assert max(from_bytes(gen.image).size) == 256
    ext = build_station(ext_cfg).run(gen.image, sha256_bytes(gen.image), ctx)
    assert ext.attributes is not None and ext.attributes.dominant_colors
    # extract cached, attributes come back from the cache
    ext2 = build_station(ext_cfg).run(gen.image, sha256_bytes(gen.image), ctx)
    assert ext2.record.cached and ext2.attributes == ext.attributes
    # same caption + same seed => same image (deterministic mock)
    gen2 = build_station(gen_cfg).run(png, sha256_bytes(png), ctx)
    assert gen2.record.cached and gen2.image == gen.image


def test_regenerate_without_caption_errors(tmp_path, test_image):
    png = to_png_bytes(load_image(test_image))
    gen_cfg = StationConfig(kind="regenerate", provider="mock")
    res = build_station(gen_cfg).run(
        png, sha256_bytes(png), ctx_for(tmp_path, [gen_cfg], caption=None)
    )
    assert res.image is None and "no caption" in (res.record.error or "")


def test_physical_station_missing_frame(tmp_path, test_image):
    png = to_png_bytes(load_image(test_image))
    folder = tmp_path / "frames"
    folder.mkdir()
    cfg = StationConfig(kind="physical", params={"folder": str(folder)})
    with pytest.raises(MissingFrame):
        build_station(cfg).run(png, sha256_bytes(png), ctx_for(tmp_path, [cfg], generation=1))
    load_image(test_image).save(folder / "IMG_0001.jpg")
    res = build_station(cfg).run(png, sha256_bytes(png), ctx_for(tmp_path, [cfg], generation=1))
    assert res.image is not None and res.record.params["frame"] == "IMG_0001.jpg"


def test_unknown_provider():
    from telephone.providers import ProviderUnavailable, get_vision_provider

    with pytest.raises(ProviderUnavailable):
        get_vision_provider("nope")
    with pytest.raises(ProviderUnavailable):
        get_vision_provider("anthropic")  # no key in tests
