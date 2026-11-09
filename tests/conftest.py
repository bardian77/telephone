from __future__ import annotations

import os
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from telephone import cost


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch, tmp_path):
    """Tests never read the developer's .env or spend money."""
    for k in [
        "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
        "CLOUDFLARE_API_TOKEN",
        "CLOUDFLARE_ACCOUNT_ID",
        "REPLICATE_API_TOKEN",
        "OPENAI_API_KEY",
    ]:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.delenv("TELEPHONE_ROOT", raising=False)
    monkeypatch.setenv("TELEPHONE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TELEPHONE_SPEND_CAP_USD", "5")
    monkeypatch.chdir(tmp_path)
    from telephone import paths
    from telephone.config import get_settings

    paths.project_root.cache_clear()
    get_settings.cache_clear()
    cost.reset_tracker(5.0)
    yield
    get_settings.cache_clear()
    paths.project_root.cache_clear()


def make_test_image(
    path: Path, kind: str = "street", size: tuple[int, int] = (640, 480), seed: int = 0
) -> Path:
    """Deterministic synthetic 'photograph' with shapes and text, for tests only."""
    import random

    rng = random.Random(seed)
    img = Image.new(
        "RGB", size, (rng.randint(100, 200), rng.randint(100, 200), rng.randint(100, 200))
    )
    d = ImageDraw.Draw(img)
    for _ in range(12):
        x0, y0 = rng.randint(0, size[0] - 50), rng.randint(0, size[1] - 50)
        x1, y1 = x0 + rng.randint(20, 200), y0 + rng.randint(20, 200)
        color = (rng.randint(0, 255), rng.randint(0, 255), rng.randint(0, 255))
        if rng.random() < 0.5:
            d.rectangle([x0, y0, x1, y1], fill=color)
        else:
            d.ellipse([x0, y0, x1, y1], fill=color)
    d.text((20, 20), f"TELEPHONE {kind.upper()} {seed}", fill=(255, 255, 255))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="JPEG", quality=95)
    return path


@pytest.fixture
def test_image(tmp_path) -> Path:
    return make_test_image(tmp_path / "originals" / "street_test_01.jpg")


def pytest_collection_modifyitems(config, items):
    if os.environ.get("TELEPHONE_RUN_SLOW") == "1" or config.getoption("-m", default=""):
        return
    skip = pytest.mark.skip(reason="slow: set TELEPHONE_RUN_SLOW=1")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip)
