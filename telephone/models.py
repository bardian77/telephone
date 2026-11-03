"""Pydantic models shared by the pipeline, the ledger, the export and the API."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

StationKind = Literal["platform", "caption", "regenerate", "extract", "physical"]


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def stable_hash(obj: Any) -> str:
    """sha256 of a canonical JSON encoding. Used for cache keys and ids."""
    data = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(data).hexdigest()


class StationConfig(BaseModel):
    """One step in a chain. `params` is station specific (see telephone/stations)."""

    kind: StationKind
    provider: str | None = None
    model: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)

    def label(self) -> str:
        bits = [self.kind]
        if self.provider:
            bits.append(self.provider)
        if self.model:
            bits.append(self.model)
        for k, v in sorted(self.params.items()):
            bits.append(f"{k}={v}")
        return ":".join(bits)


class ChainConfig(BaseModel):
    """A chain = an original image + an ordered list of stations, repeated for N generations."""

    chain_id: str
    experiment_id: str
    image: str = Field(description="Path to the generation-0 image")
    stations: list[StationConfig]
    generations: int = 12
    seed: int = 7
    repeat: int = Field(0, description="Repeat index when a chain is run several times")
    extract_every_generation: bool = True
    notes: str | None = None

    def station_sequence(self) -> str:
        return " > ".join(s.kind for s in self.stations)


class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    images: int = 0
    cost_usd: float = 0.0
    list_price_usd: float = 0.0
    latency_ms: int = 0


class StationRecord(BaseModel):
    """What one station did to one image in one generation."""

    kind: StationKind
    provider: str | None = None
    model: str | None = None
    model_version: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    prompt_or_caption: str | None = None
    seed: int | None = None
    usage: Usage = Field(default_factory=Usage)
    cached: bool = False
    error: str | None = None
    raw: dict[str, Any] | None = Field(default=None, description="Provider response metadata")


class Attributes(BaseModel):
    """Structured reading of an image. Extracted at every generation and compared to generation 0."""

    objects: list[str] = Field(
        description="Up to 10 distinct physical things visible, lowercase nouns"
    )
    people_count: int = Field(description="Number of people visible, 0 if none")
    visible_text: list[str] = Field(description="Exact strings of any legible text, empty if none")
    setting: str = Field(
        description="Where this is, in 2 to 6 words, e.g. 'busy city street at night'"
    )
    lighting: str = Field(
        description="One of: daylight, overcast, golden hour, night, artificial, mixed, unknown"
    )
    mood: str = Field(description="One or two words for the emotional tone")
    dominant_colors: list[str] = Field(description="Up to 3 colour names, most dominant first")
    camera_angle: str = Field(
        description="One of: eye level, high angle, low angle, aerial, close-up, unknown"
    )
    is_photograph: bool = Field(
        description="True if it reads as a camera photograph rather than an illustration or render"
    )


class FieldSurvival(BaseModel):
    alive: bool
    score: float = Field(description="1.0 identical, 0.0 nothing in common")
    g0: Any = None
    now: Any = None


class Survival(BaseModel):
    fields: dict[str, FieldSurvival]
    alive_count: int
    total: int

    @property
    def fraction(self) -> float:
        return self.alive_count / self.total if self.total else 0.0


class Metrics(BaseModel):
    clip_dist_to_g0: float | None = None
    clip_dist_to_prev: float | None = None
    ssim_to_g0: float | None = None
    ssim_to_prev: float | None = None
    lpips_to_g0: float | None = None
    lpips_to_prev: float | None = None
    ocr_chars: int | None = None
    ocr_words: int | None = None
    face_count: int | None = None
    width: int | None = None
    height: int | None = None
    file_bytes: int | None = None


class GenerationRecord(BaseModel):
    """One ledger row: one generation of one chain."""

    run_id: str
    experiment_id: str
    chain_id: str
    repeat: int = 0
    generation: int
    station_sequence: str
    stations: list[StationRecord] = Field(default_factory=list)
    caption: str | None = Field(
        default=None, description="Caption that produced this generation, if any"
    )
    seed: int | None = None
    input_sha: str | None = None
    output_path: str
    output_sha: str
    attributes: Attributes | None = None
    survival: Survival | None = None
    metrics: Metrics = Field(default_factory=Metrics)
    cost_usd: float = 0.0
    list_price_usd: float = 0.0
    latency_ms: int = 0
    created_at: str = Field(default_factory=now_iso)
    error: str | None = None

    def to_row(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> GenerationRecord:
        return cls.model_validate(row)
