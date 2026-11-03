"""Content-addressed cache for station outputs.

Key = sha256(input image sha, station kind, provider, model, params, seed, prompt).
The same image through the same configured station always hits the cache, so re-running
an experiment or browsing the site never spends money. Cache entries hold the station
record (JSON) and, for image-producing stations, the output image bytes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import StationRecord, stable_hash


class StationCache:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.hits = 0
        self.misses = 0

    @staticmethod
    def key(
        input_sha: str | None,
        kind: str,
        provider: str | None,
        model: str | None,
        params: dict[str, Any],
        seed: int | None,
        prompt: str | None = None,
    ) -> str:
        return stable_hash(
            {
                "input_sha": input_sha,
                "kind": kind,
                "provider": provider,
                "model": model,
                "params": params,
                "seed": seed,
                "prompt": prompt,
            }
        )

    def _paths(self, key: str) -> tuple[Path, Path]:
        d = self.root / key[:2]
        return d / f"{key}.json", d / f"{key}.bin"

    def get(self, key: str) -> tuple[StationRecord, bytes | None] | None:
        meta, blob = self._paths(key)
        if not meta.exists():
            self.misses += 1
            return None
        record = StationRecord.model_validate_json(meta.read_text())
        record.cached = True
        data = blob.read_bytes() if blob.exists() else None
        self.hits += 1
        return record, data

    def put(self, key: str, record: StationRecord, data: bytes | None) -> None:
        meta, blob = self._paths(key)
        meta.parent.mkdir(parents=True, exist_ok=True)
        meta.write_text(record.model_dump_json(indent=None))
        if data is not None:
            blob.write_bytes(data)

    def stats(self) -> dict[str, int]:
        return {"hits": self.hits, "misses": self.misses}


class NullCache(StationCache):
    """Always misses. For tests of the uncached path."""

    def __init__(self) -> None:  # noqa: D107
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> None:  # type: ignore[override]
        self.misses += 1
        return None

    def put(self, key: str, record: StationRecord, data: bytes | None) -> None:
        return None


def json_dumps(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, default=str)
