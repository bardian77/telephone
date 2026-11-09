"""Where the project lives, so every command works from any folder.

The project root is, in order: `TELEPHONE_ROOT` if set; the nearest folder at or above the
current directory that holds both `pyproject.toml` and `experiments/`; the checkout this package
was installed from (an editable install); else the current directory. Relative paths in the
ledger (`data/runs/...`) and in experiment files are resolved against it, so a ledger saved on
one machine still points at the right files on another.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


def _looks_like_root(d: Path) -> bool:
    return (d / "pyproject.toml").is_file() and (d / "experiments").is_dir()


@lru_cache
def project_root() -> Path:
    env = os.environ.get("TELEPHONE_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    for start in (Path.cwd(), Path(__file__).resolve().parent):
        for d in (start, *start.parents):
            if _looks_like_root(d):
                return d
    return Path.cwd()


def resolve(p: str | Path) -> Path:
    """Absolute path for a stored or configured path; relative ones hang off the project root."""
    p = Path(p)
    return p if p.is_absolute() else project_root() / p


def to_stored(p: str | Path) -> str:
    """The form a path takes in the ledger: relative to the root when it is inside it."""
    p = Path(p).resolve()
    try:
        return p.relative_to(project_root()).as_posix()
    except ValueError:
        return str(p)
