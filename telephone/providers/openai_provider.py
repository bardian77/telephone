"""OpenAI: GPT vision (captioner for the swap experiment) and GPT Image (generator). Paid, optional."""

from __future__ import annotations

import base64
from typing import Any

from ..cost import get_tracker, image_list_price, text_list_price
from ..imageio import media_type_of, to_base64
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


def _client(api_key: str | None):
    try:
        import openai
    except ImportError as e:  # pragma: no cover
        raise ProviderUnavailable("pip install openai") from e
    from ..config import get_settings

    key = api_key or get_settings().openai_api_key
    if not key:
        raise ProviderUnavailable("OPENAI_API_KEY is not set")
    return openai.OpenAI(api_key=key, max_retries=3, timeout=120)


class OpenAIVision:
    name = "openai"
    supports_seed = False

    def __init__(self, model: str = "gpt-5-mini", api_key: str | None = None):
        self.client = _client(api_key)
        self.model = model

    def _messages(self, image: bytes, prompt: str) -> list[dict[str, Any]]:
        uri = f"data:{media_type_of(image)};base64,{to_base64(image)}"
        return [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": uri}},
                    {"type": "text", "text": prompt},
                ],
            }
        ]

    def _usage(self, response: Any, ms: int) -> Usage:
        u = response.usage
        inp, out = int(u.prompt_tokens or 0), int(u.completion_tokens or 0)
        price = text_list_price(self.model, inp, out)
        return Usage(
            input_tokens=inp, output_tokens=out, cost_usd=price, list_price_usd=price, latency_ms=ms
        )

    def caption(
        self, image: bytes, mode: CaptionMode, seed: int | None = None
    ) -> tuple[str, Usage, dict[str, Any]]:
        tracker = get_tracker()
        tracker.reserve(text_list_price(self.model, 2000, 400))
        wait_for("openai")
        with Timer() as t:
            response = self.client.chat.completions.create(
                model=self.model, messages=self._messages(image, CAPTION_PROMPTS[mode])
            )
        usage = self._usage(response, t.ms)
        tracker.commit(usage)
        text = (response.choices[0].message.content or "").strip()
        if not text:
            raise ProviderRefusal("OpenAI returned no text")
        return (
            text,
            usage,
            {"finish_reason": response.choices[0].finish_reason, "served_model": response.model},
        )

    def extract(self, image: bytes) -> tuple[Attributes, Usage, dict[str, Any]]:
        tracker = get_tracker()
        tracker.reserve(text_list_price(self.model, 2000, 400))
        wait_for("openai")
        with Timer() as t:
            response = self.client.chat.completions.parse(
                model=self.model,
                messages=self._messages(image, EXTRACT_PROMPT),
                response_format=Attributes,
            )
        usage = self._usage(response, t.ms)
        tracker.commit(usage)
        parsed = response.choices[0].message.parsed
        if parsed is None:
            raise ProviderRefusal("OpenAI returned no structured output")
        return parsed, usage, {"served_model": response.model}


class OpenAIImageGen:
    name = "openai"
    supports_seed = False

    def __init__(
        self, model: str = "gpt-image-1-mini", api_key: str | None = None, quality: str = "low"
    ):
        self.client = _client(api_key)
        self.model = model
        self.quality = quality

    def generate(
        self, prompt: str, seed: int | None = None, width: int = 1024, height: int = 1024
    ) -> tuple[bytes, Usage, dict[str, Any]]:
        tracker = get_tracker()
        price = image_list_price(self.model)
        tracker.reserve(price)
        wait_for("openai")
        size = (
            "1024x1024"
            if abs(width - height) < 8
            else ("1024x1536" if height > width else "1536x1024")
        )
        with Timer() as t:
            response = self.client.images.generate(
                model=self.model, prompt=prompt[:4000], size=size, quality=self.quality, n=1
            )
        b64 = response.data[0].b64_json if response.data else None
        if not b64:
            raise ProviderRefusal("OpenAI returned no image")
        usage = Usage(images=1, cost_usd=price, list_price_usd=price, latency_ms=t.ms)
        tracker.commit(usage)
        return base64.b64decode(b64), usage, {"size": size, "quality": self.quality}
