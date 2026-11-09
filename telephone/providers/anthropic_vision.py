"""Claude as captioner and attribute extractor.

Captions: `client.beta.messages.create` with server-side refusal fallbacks (`fallbacks="default"`).
Extraction: `client.beta.messages.parse` with the Attributes pydantic model as `output_format`, so
the survival metric always gets schema-valid JSON. Thinking is left adaptive (the parameter is
omitted); effort is low because this is description, not reasoning.
"""

from __future__ import annotations

from typing import Any

from ..cost import get_tracker, text_list_price
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

FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicVision:
    name = "anthropic"
    supports_seed = False

    def __init__(
        self, model: str = "claude-sonnet-5-5", api_key: str | None = None, effort: str = "low"
    ):
        try:
            import anthropic
        except ImportError as e:  # pragma: no cover
            raise ProviderUnavailable("pip install anthropic") from e
        from ..config import get_settings

        key = api_key or get_settings().anthropic_api_key
        if not key:
            raise ProviderUnavailable("ANTHROPIC_API_KEY is not set")
        self.client = anthropic.Anthropic(api_key=key, max_retries=3, timeout=120)
        self.model = model
        self.effort = effort

    def _image_block(self, image: bytes) -> dict[str, Any]:
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type_of(image),
                "data": to_base64(image),
            },
        }

    def _usage(self, response: Any, ms: int) -> Usage:
        u = response.usage
        inp = int(getattr(u, "input_tokens", 0) or 0)
        out = int(getattr(u, "output_tokens", 0) or 0)
        served = getattr(response, "model", self.model) or self.model
        price = text_list_price(served, inp, out)
        return Usage(
            input_tokens=inp, output_tokens=out, cost_usd=price, list_price_usd=price, latency_ms=ms
        )

    def _estimate(self) -> float:
        # ~1600 image tokens + prompt, ~300 output tokens
        return text_list_price(self.model, 2000, 400)

    def caption(
        self, image: bytes, mode: CaptionMode, seed: int | None = None
    ) -> tuple[str, Usage, dict[str, Any]]:
        tracker = get_tracker()
        tracker.reserve(self._estimate())
        wait_for("anthropic")
        with Timer() as t:
            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=600,
                betas=[FALLBACK_BETA],
                fallbacks="default",
                output_config={"effort": self.effort},
                messages=[
                    {
                        "role": "user",
                        "content": [
                            self._image_block(image),
                            {"type": "text", "text": CAPTION_PROMPTS[mode]},
                        ],
                    }
                ],
            )
        usage = self._usage(response, t.ms)
        tracker.commit(usage, provider=self.name, model=self.model)
        meta = {
            "stop_reason": response.stop_reason,
            "served_model": response.model,
            "id": response.id,
        }
        if response.stop_reason == "refusal":
            sd = getattr(response, "stop_details", None)
            meta["refusal_category"] = getattr(sd, "category", None)
            raise ProviderRefusal(
                f"Claude declined to caption this image ({meta['refusal_category']})"
            )
        text = "".join(
            getattr(b, "text", "") for b in response.content if getattr(b, "type", "") == "text"
        ).strip()
        if not text:
            raise ProviderRefusal("Claude returned no text for this image")
        return text, usage, meta

    def extract(self, image: bytes) -> tuple[Attributes, Usage, dict[str, Any]]:
        tracker = get_tracker()
        tracker.reserve(self._estimate())
        wait_for("anthropic")
        with Timer() as t:
            response = self.client.beta.messages.parse(
                model=self.model,
                max_tokens=1200,
                betas=[FALLBACK_BETA],
                fallbacks="default",
                output_config={"effort": self.effort},
                output_format=Attributes,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            self._image_block(image),
                            {"type": "text", "text": EXTRACT_PROMPT},
                        ],
                    }
                ],
            )
        usage = self._usage(response, t.ms)
        tracker.commit(usage, provider=self.name, model=self.model)
        meta = {
            "stop_reason": response.stop_reason,
            "served_model": response.model,
            "id": response.id,
        }
        if response.stop_reason == "refusal":
            raise ProviderRefusal("Claude declined to read this image")
        parsed = response.parsed_output
        if parsed is None:
            raise ProviderRefusal("Claude returned no structured output")
        return parsed, usage, meta
