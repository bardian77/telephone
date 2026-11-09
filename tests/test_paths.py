"""Commands must work from any folder: everything anchors on the project root."""

from __future__ import annotations

from pathlib import Path

from telephone import paths
from telephone.config import get_settings

REPO = Path(__file__).resolve().parents[1]


def test_project_root_is_found_from_another_folder(tmp_path, monkeypatch):
    # conftest already chdir'd into tmp_path, which has no pyproject.toml
    monkeypatch.delenv("TELEPHONE_ROOT", raising=False)
    paths.project_root.cache_clear()
    assert Path.cwd() == tmp_path
    assert paths.project_root() == REPO


def test_project_root_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEPHONE_ROOT", str(tmp_path))
    paths.project_root.cache_clear()
    assert paths.project_root() == tmp_path.resolve()
    paths.project_root.cache_clear()


def test_resolve_relative_paths_against_root(monkeypatch):
    monkeypatch.delenv("TELEPHONE_ROOT", raising=False)
    paths.project_root.cache_clear()
    assert paths.resolve("data/runs/x/000.png") == REPO / "data/runs/x/000.png"
    assert paths.resolve("/abs/file.png") == Path("/abs/file.png")


def test_default_data_dir_and_experiments_anchor_on_root(monkeypatch):
    monkeypatch.delenv("TELEPHONE_DATA_DIR", raising=False)
    monkeypatch.delenv("TELEPHONE_ROOT", raising=False)
    paths.project_root.cache_clear()
    get_settings.cache_clear()
    try:
        assert get_settings().telephone_data_dir == REPO / "data"
        from telephone.experiments import load_all

        assert "exp01_compression" in load_all()
    finally:
        get_settings.cache_clear()


def test_experiment_image_globs_follow_the_data_dir(tmp_path):
    """'data/...' patterns in experiment YAML mean the configured data dir, not the cwd."""
    from telephone.experiments import load_all
    from telephone.fixtures import make_fixture

    s = get_settings()  # TELEPHONE_DATA_DIR is tmp_path/data in tests
    make_fixture(s.originals_dir / "street_a.jpg", "street")
    exp = load_all()["exp01_compression"]
    assert [p.name for p in exp.resolve_images()] == ["street_a.jpg"]
    make_fixture(s.telephone_data_dir / "fixtures" / "street_fixture_01.png", "street")
    assert [p.name for p in load_all()["exp00_smoke"].resolve_images()] == ["street_fixture_01.png"]
