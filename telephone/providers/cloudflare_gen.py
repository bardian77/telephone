"""FLUX.1 schnell on Cloudflare Workers AI. Free daily allowance, and it takes a seed."""

from __future__ import annotations

import base64
from typing import Any

import httpx

from ..cost import get_tracker, image_list_price
from ..models import Usage
from ..ratelimit import wait_for
from .base import ProviderRefusal, ProviderUnavailable, Timer


class CloudflareFluxGen:
    name = "cloudflare"
    supports_seed = True

    def __init__(
        self,
        model: str = "@cf/black-forest-labs/flux-1-schnell",
        account_id: str | None = None,
        token: str | None = None,
        steps: int = 4,
    ):
        from ..config import get_settings

        s = get_settings()
        self.account_id = account_id or s.cloudflare_account_id
        self.token = token or s.cloudflare_api_token
        if not (self.account_id and self.token):
            raise ProviderUnavailable("CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN are not set")
        self.model = model
        self.steps = min(max(steps, 1), 8)
        self.client = httpx.Client(timeout=120)

    def generate(
        self, prompt: str, seed: int | None = None, width: int = 1024, height: int = 1024
    ) -> tuple[bytes, Usage, dict[str, Any]]:
        tracker = get_tracker()
        price = image_list_price(self.model)
        tracker.reserve(0.0)  # free allowance; list price recorded below
        wait_for("cloudflare")
        url = f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}/ai/run/{self.model}"
        body: dict[str, Any] = {"prompt": prompt[:2048], "steps": self.steps}
        if seed is not None:
            body["seed"] = int(seed) % (2**31)
        with Timer() as t:
            r = self.client.post(url, headers={"Authorization": f"Bearer {self.token}"}, json=body)
        if r.status_code == 429:
            raise ProviderRefusal("Cloudflare rate limit or daily allowance exhausted (429)")
        r.raise_for_status()
        payload = r.json()
        if not payload.get("success", False):
            raise ProviderRefusal(f"Cloudflare error: {payload.get('errors')}")
        b64 = payload["result"].get("image")
        if not b64:
            raise ProviderRefusal("Cloudflare returned no image")
        data = base64.b64decode(b64)
        usage = Usage(images=1, cost_usd=0.0, list_price_usd=price, latency_ms=t.ms)
        tracker.commit(usage)
        return data, usage, {"steps": self.steps, "seed": body.get("seed")}
