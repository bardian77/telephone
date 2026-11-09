"""The web export never publishes mock runs by accident, and never publishes private photos."""

from __future__ import annotations

import json
from pathlib import Path

from telephone.chain import ChainRunner, RunnerOptions
from telephone.config import get_settings
from telephone.export import export_all
from telephone.fixtures import make_fixture
from telephone.models import ChainConfig, StationConfig


def _run(img: Path, experiment_id: str, chain_id: str) -> None:
    cfg = ChainConfig(
        chain_id=chain_id,
        experiment_id=experiment_id,
        image=str(img),
        generations=1,
        stations=[
            StationConfig(kind="platform", params={"preset": "harsh"}),
            StationConfig(kind="caption", provider="mock", params={"mode": "short"}),
            StationConfig(kind="regenerate", provider="mock", params={"size": 128}),
        ],
    )
    ChainRunner(options=RunnerOptions(compute_clip=False, extractor=None)).run(cfg)


def _ids(out: Path) -> list[str]:
    return [e["id"] for e in json.loads((out / "index.json").read_text())["experiments"]]


def test_export_skips_mock_experiments_unless_asked(tmp_path):
    img = make_fixture(tmp_path / "street_a.png", "street")
    _run(img, "exp02_caption_length-mock", "exp02_caption_length-mock__short__street_a")
    _run(img, "exp00_smoke", "exp00_smoke__telephone__street_a")
    export_all(tmp_path / "out1")
    assert _ids(tmp_path / "out1") == ["exp00_smoke"]
    export_all(tmp_path / "out2", include_mock=True)
    assert _ids(tmp_path / "out2") == ["exp00_smoke", "exp02_caption_length-mock"]


def test_export_excludes_photos_in_the_private_folder(tmp_path):
    s = get_settings()
    private = s.originals_dir / "private"
    secret = make_fixture(private / "portrait_secret_01.jpg", "portrait")
    public = make_fixture(s.originals_dir / "street_a.jpg", "street")
    _run(secret, "exp00_smoke", "exp00_smoke__telephone__portrait_secret_01")
    _run(public, "exp00_smoke", "exp00_smoke__telephone__street_a")
    export_all(tmp_path / "out1")
    index = json.loads((tmp_path / "out1" / "index.json").read_text())
    assert index["images"] == ["street_a"]
    assert not list((tmp_path / "out1" / "img").glob("*portrait_secret*"))
    export_all(tmp_path / "out2", include_private=True)
    index2 = json.loads((tmp_path / "out2" / "index.json").read_text())
    assert index2["images"] == ["portrait_secret_01", "street_a"]
