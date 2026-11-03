"""Station protocol and the shared context a chain passes along."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..cache import StationCache
from ..config import Settings
from ..models import Attributes, ChainConfig, StationConfig, StationRecord


@dataclass
class StationContext:
    settings: Settings
    cache: StationCache
    chain: ChainConfig
    generation: int
    seed: int
    caption: str | None = None  # the most recent caption produced in this generation
    input_sha: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass
class StationResult:
    image: bytes | None  # None for stations that do not produce an image (extract)
    record: StationRecord
    caption: str | None = None
    attributes: Attributes | None = None


class Station:
    """Base class. Subclasses implement `_run`; `run` adds caching around it."""

    kind: str = "base"
    produces_image: bool = True

    def __init__(self, cfg: StationConfig):
        self.cfg = cfg

    def cache_key(self, image_sha: str | None, ctx: StationContext) -> str:
        return StationCache.key(
            image_sha,
            self.cfg.kind,
            self.cfg.provider,
            self.cfg.model,
            self.cfg.params,
            self.seed_for(ctx),
            ctx.caption if self.uses_caption else None,
        )

    uses_caption: bool = False

    def seed_for(self, ctx: StationContext) -> int | None:
        if "seed" in self.cfg.params:
            return int(self.cfg.params["seed"])
        return ctx.seed

    def run(self, image: bytes, image_sha: str, ctx: StationContext) -> StationResult:
        key = self.cache_key(image_sha, ctx)
        hit = ctx.cache.get(key)
        if hit is not None:
            record, data = hit
            return StationResult(
                image=data if self.produces_image else None,
                record=record,
                caption=record.prompt_or_caption if self.kind == "caption" else ctx.caption,
                attributes=Attributes.model_validate(record.raw["attributes"])
                if record.raw and "attributes" in record.raw
                else None,
            )
        result = self._run(image, ctx)
        if result.record.error is None:
            ctx.cache.put(key, result.record, result.image)
        return result

    def _run(self, image: bytes, ctx: StationContext) -> StationResult:  # pragma: no cover
        raise NotImplementedError

    def estimated_cost_usd(self) -> float:
        return 0.0
