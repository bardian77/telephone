"""Regenerate station: a text-to-image model recreates the picture from the current caption."""

from __future__ import annotations

from ..cost import image_list_price
from ..imageio import from_bytes
from ..models import StationRecord, Usage
from ..providers import ProviderRefusal, get_image_provider
from .base import Station, StationContext, StationResult


class RegenerateStation(Station):
    kind = "regenerate"
    uses_caption = True

    def seed_for(self, ctx: StationContext) -> int | None:
        if "seed" in self.cfg.params:
            return int(self.cfg.params["seed"])
        # one seed per chain, offset per generation so repeated prompts still vary like real reposts
        return ctx.seed * 1000 + ctx.generation

    def _run(self, image: bytes, ctx: StationContext) -> StationResult:
        provider_name = self.cfg.provider or ctx.settings.default_generator
        provider = get_image_provider(provider_name, self.cfg.model)
        seed = self.seed_for(ctx)
        record = StationRecord(
            kind="regenerate",
            provider=provider.name,
            model=provider.model,
            params=dict(self.cfg.params),
            seed=seed,
        )
        if not ctx.caption:
            record.error = "no caption available for regeneration"
            return StationResult(image=None, record=record)
        src = from_bytes(image)
        size = int(self.cfg.params.get("size", 1024))
        if self.cfg.params.get("keep_aspect", True):
            w, h = src.size
            if w >= h:
                width, height = size, max(256, round(size * h / w))
            else:
                width, height = max(256, round(size * w / h)), size
        else:
            width = height = size
        record.prompt_or_caption = ctx.caption
        try:
            data, usage, meta = provider.generate(
                ctx.caption,
                seed=seed if provider.supports_seed else None,
                width=width,
                height=height,
            )
        except ProviderRefusal as e:
            record.error = str(e)
            record.usage = Usage()
            return StationResult(image=None, record=record, caption=ctx.caption)
        record.usage = usage
        record.raw = meta
        record.model_version = meta.get("model_version")
        return StationResult(image=data, record=record, caption=ctx.caption)

    def estimated_cost_usd(self) -> float:
        prov = self.cfg.provider or "gemini"
        if prov in ("mock", "cloudflare"):
            return 0.0
        if prov == "gemini":
            from ..config import get_settings

            return (
                0.0
                if get_settings().gemini_free_tier
                else image_list_price(self.cfg.model or "gemini-2.5-flash-image")
            )
        return image_list_price(self.cfg.model or prov)
