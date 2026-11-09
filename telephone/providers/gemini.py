"""Gemini: vision (second captioner) and Gemini 2.5 Flash Image (default generator).

Calls are costed at list price unless GEMINI_FREE_TIER=1 is set, in which case cost_usd is 0 and
only list_price_usd is recorded. The default assumes you are billed; that is the honest default.
"""

from __future__ import annotations

import contextlib
from typing import Any

from ..cost import get_tracker, image_list_price, text_list_price
from ..imageio import media_type_of
from ..models import Attributes, Usage
from ..ratelimit import wait_for
from .base import (
    CAPTION_PROMPTS,
    EXTRACT_PROMPT,
    CaptionMode,
    ProviderRefusal,
    ProviderUnavailable,
    Timer,
)
from .defaults import IMAGE_DEFAULT_MODELS, VISION_DEFAULT_MODELS


def _client(api_key: str | None):
    try:
        from google import genai
    except ImportError as e:  # pragma: no cover
        raise ProviderUnavailable("pip install google-genai") from e
    from ..config import get_settings

    key = api_key or get_settings().gemini_api_key
    if not key:
        raise ProviderUnavailable(
            "GEMINI_API_KEY is not set (free key at https://aistudio.google.com)"
        )
    return genai.Client(api_key=key)


def _free() -> bool:
    from ..config import get_settings

    return get_settings().gemini_free_tier


def _text_usage(response: Any, model: str, ms: int) -> Usage:
    um = getattr(response, "usage_metadata", None)
    inp = int(getattr(um, "prompt_token_count", 0) or 0)
    out = int(getattr(um, "candidates_token_count", 0) or 0)
    price = text_list_price(model, inp, out)
    return Usage(
        input_tokens=inp,
        output_tokens=out,
        cost_usd=0.0 if _free() else price,
        list_price_usd=price,
        latency_ms=ms,
    )


class GeminiVision:
    name = "gemini"
    supports_seed = False

    def __init__(self, model: str | None = None, api_key: str | None = None):
        self.client = _client(api_key)
        self.model = model or VISION_DEFAULT_MODELS["gemini"]

    def _parts(self, image: bytes, prompt: str) -> list[Any]:
        from google.genai import types

        return [types.Part.from_bytes(data=image, mime_type=media_type_of(image)), prompt]

    def caption(
        self, image: bytes, mode: CaptionMode, seed: int | None = None
    ) -> tuple[str, Usage, dict[str, Any]]:
        tracker = get_tracker()
        tracker.reserve(0.0 if _free() else text_list_price(self.model, 2000, 400))
        wait_for("gemini")
        with Timer() as t:
            response = self.client.models.generate_content(
                model=self.model, contents=self._parts(image, CAPTION_PROMPTS[mode])
            )
        usage = _text_usage(response, self.model, t.ms)
        tracker.commit(usage, provider=self.name, model=self.model)
        text = (response.text or "").strip()
        if not text:
            raise ProviderRefusal("Gemini returned no text (possibly blocked by safety filters)")
        return text, usage, {"model_version": getattr(response, "model_version", None)}

    def extract(self, image: bytes) -> tuple[Attributes, Usage, dict[str, Any]]:
        from google.genai import types

        tracker = get_tracker()
        tracker.reserve(0.0 if _free() else text_list_price(self.model, 2000, 400))
        wait_for("gemini")
        with Timer() as t:
            response = self.client.models.generate_content(
                model=self.model,
                contents=self._parts(image, EXTRACT_PROMPT),
                config=types.GenerateContentConfig(
                    response_mime_type="application/json", response_schema=Attributes
                ),
            )
        usage = _text_usage(response, self.model, t.ms)
        tracker.commit(usage, provider=self.name, model=self.model)
        parsed = getattr(response, "parsed", None)
        if parsed is None:
            if not response.text:
                raise ProviderRefusal("Gemini returned no structured output")
            parsed = Attributes.model_validate_json(response.text)
        if isinstance(parsed, dict):
            parsed = Attributes.model_validate(parsed)
        return parsed, usage, {"model_version": getattr(response, "model_version", None)}


class GeminiImageGen:
    name = "gemini"
    supports_seed = False  # the API accepts a seed but does not promise determinism

    def __init__(self, model: str | None = None, api_key: str | None = None):
        self.client = _client(api_key)
        self.model = model or IMAGE_DEFAULT_MODELS["gemini"]

    def generate(
        self, prompt: str, seed: int | None = None, width: int = 1024, height: int = 1024
    ) -> tuple[bytes, Usage, dict[str, Any]]:
        from google.genai import types

        tracker = get_tracker()
        price = image_list_price(self.model)
        tracker.reserve(0.0 if _free() else price)
        wait_for("gemini-image")
        aspect = _aspect(width, height)
        full_prompt = (
            "Create a realistic photograph, not an illustration, matching this description exactly. "
            f"Do not add text unless the description quotes it.\n\n{prompt}"
        )
        cfg = types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio=aspect),
        )
        with Timer() as t:
            response = self.client.models.generate_content(
                model=self.model, contents=[full_prompt], config=cfg
            )
        data: bytes | None = None
        for cand in getattr(response, "candidates", None) or []:
            for part in getattr(cand.content, "parts", None) or []:
                blob = getattr(part, "inline_data", None)
                if blob is not None and blob.data:
                    data = blob.data
                    break
            if data:
                break
        usage = Usage(
            images=1, cost_usd=0.0 if _free() else price, list_price_usd=price, latency_ms=t.ms
        )
        um = getattr(response, "usage_metadata", None)
        if um is not None:
            usage.input_tokens = int(getattr(um, "prompt_token_count", 0) or 0)
            usage.output_tokens = int(getattr(um, "candidates_token_count", 0) or 0)
        tracker.commit(usage, provider=self.name, model=self.model)
        if data is None:
            fr = None
            with contextlib.suppress(Exception):
                fr = response.candidates[0].finish_reason if response.candidates else None
            raise ProviderRefusal(f"Gemini returned no image (finish_reason={fr})")
        return (
            data,
            usage,
            {"model_version": getattr(response, "model_version", None), "aspect_ratio": aspect},
        )


def _aspect(width: int, height: int) -> str:
    r = width / height
    options = {
        "1:1": 1.0,
        "3:4": 0.75,
        "4:3": 4 / 3,
        "9:16": 9 / 16,
        "16:9": 16 / 9,
        "2:3": 2 / 3,
        "3:2": 1.5,
    }
    return min(options, key=lambda k: abs(options[k] - r))
