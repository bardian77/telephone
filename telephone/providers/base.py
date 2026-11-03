"""Provider protocols. A VisionProvider reads images; an ImageGenProvider makes them.

Every call returns (payload, Usage, raw_metadata). Providers never touch the cache or the
ledger; stations do that. Providers do call the rate limiter and the spend tracker, because
those must run immediately before money moves.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Literal, Protocol, runtime_checkable

from ..models import Attributes, Usage

CaptionMode = Literal["short", "detailed", "literal"]


class ProviderUnavailable(RuntimeError):
    """Raised when a provider is requested but its key or package is missing."""


class ProviderRefusal(RuntimeError):
    """The model declined to process the image. Recorded as a station error, never retried blindly."""


@runtime_checkable
class VisionProvider(Protocol):
    name: str
    model: str

    def caption(
        self, image: bytes, mode: CaptionMode, seed: int | None = None
    ) -> tuple[str, Usage, dict[str, Any]]: ...

    def extract(self, image: bytes) -> tuple[Attributes, Usage, dict[str, Any]]: ...


@runtime_checkable
class ImageGenProvider(Protocol):
    name: str
    model: str
    supports_seed: bool

    def generate(
        self, prompt: str, seed: int | None = None, width: int = 1024, height: int = 1024
    ) -> tuple[bytes, Usage, dict[str, Any]]: ...


@dataclass
class Timer:
    start: float = 0.0

    def __enter__(self) -> Timer:
        self.start = time.perf_counter()
        return self

    def __exit__(self, *exc: object) -> None:
        self.ms = int((time.perf_counter() - self.start) * 1000)


CAPTION_PROMPTS: dict[str, str] = {
    "short": (
        "Describe this photograph in one plain sentence of at most 20 words, as a caption someone "
        "might type when posting it. Mention only what is clearly visible. Output the sentence only."
    ),
    "detailed": (
        "Describe this photograph in about 150 words so that an artist who cannot see it could "
        "repaint it as faithfully as possible. Cover: the main subject(s) and their exact placement "
        "in the frame; number of people and what they are doing; any legible text, quoted exactly; "
        "the setting; lighting and time of day; colours; camera angle and focal length feel; "
        "photographic qualities (grain, blur, depth of field). State only what is visible; do not "
        "guess names or places unless written in the image. Output the description only."
    ),
    "literal": (
        "List what is visible in this photograph as a comma-separated inventory of nouns with brief "
        "modifiers, most prominent first, maximum 40 items. No sentences. Output the list only."
    ),
}

EXTRACT_PROMPT = (
    "Read this image and fill the schema. Be literal: only what is visible. Use lowercase for objects "
    "and colours. If there is no legible text, visible_text is an empty list. If you cannot tell, use 'unknown'."
)
