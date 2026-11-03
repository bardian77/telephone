from __future__ import annotations

from ..models import StationConfig
from .base import Station, StationContext, StationResult
from .caption import CaptionStation
from .extract import ExtractStation
from .physical import MissingFrame, PhysicalStation
from .platform import PRESETS, PlatformStation
from .regenerate import RegenerateStation

REGISTRY: dict[str, type[Station]] = {
    "platform": PlatformStation,
    "caption": CaptionStation,
    "regenerate": RegenerateStation,
    "extract": ExtractStation,
    "physical": PhysicalStation,
}


def build_station(cfg: StationConfig) -> Station:
    try:
        return REGISTRY[cfg.kind](cfg)
    except KeyError as e:
        raise ValueError(f"Unknown station kind {cfg.kind!r}; known: {sorted(REGISTRY)}") from e


__all__ = [
    "PRESETS",
    "REGISTRY",
    "MissingFrame",
    "Station",
    "StationContext",
    "StationResult",
    "build_station",
]
