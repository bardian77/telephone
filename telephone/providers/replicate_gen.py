"""FLUX on Replicate. Paid, seeded, optional."""

from __future__ import annotations

from typing import Any

from ..cost import get_tracker, image_list_price
from ..models import Usage
from ..ratelimit import wait_for
from .base import ProviderRefusal, ProviderUnavailable, Timer
from .defaults import IMAGE_DEFAULT_MODELS


class ReplicateFluxGen:
    name = "replicate"
    supports_seed = True

    def __init__(self, model: str | None = None, api_token: str | None = None):
        try:
            import replicate
        except ImportError as e:  # pragma: no cover
            raise ProviderUnavailable("pip install replicate") from e
        from ..config import get_settings

        token = api_token or get_settings().replicate_api_token
        if not token:
            raise ProviderUnavailable("REPLICATE_API_TOKEN is not set")
        self.client = replicate.Client(api_token=token)
        self.model = model or IMAGE_DEFAULT_MODELS["replicate"]

    def generate(
        self, prompt: str, seed: int | None = None, width: int = 1024, height: int = 1024
    ) -> tuple[bytes, Usage, dict[str, Any]]:
        tracker = get_tracker()
        price = image_list_price(self.model)
        tracker.reserve(price)
        wait_for("replicate")
        inputs: dict[str, Any] = {
            "prompt": prompt,
            "aspect_ratio": "1:1"
            if abs(width - height) < 8
            else ("3:4" if height > width else "4:3"),
            "output_format": "png",
            "disable_safety_checker": False,
        }
        if seed is not None:
            inputs["seed"] = int(seed)
        with Timer() as t:
            out = self.client.run(self.model, input=inputs)
        files = out if isinstance(out, list) else [out]
        if not files:
            raise ProviderRefusal("Replicate returned no image (safety checker?)")
        f = files[0]
        data = (
            f.read() if hasattr(f, "read") else __import__("httpx").get(str(f), timeout=120).content
        )
        usage = Usage(images=1, cost_usd=price, list_price_usd=price, latency_ms=t.ms)
        tracker.commit(usage, provider=self.name, model=self.model)
        return data, usage, {"seed": inputs.get("seed")}
