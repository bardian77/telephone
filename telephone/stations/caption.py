"""Caption station: a vision-language model describes the image."""

from __future__ import annotations

from ..cost import text_list_price
from ..imageio import from_bytes, prepare_for_vision_api
from ..models import StationRecord, Usage
from ..providers import ProviderRefusal, get_vision_provider
from .base import Station, StationContext, StationResult


class CaptionStation(Station):
    kind = "caption"
    produces_image = False

    def _run(self, image: bytes, ctx: StationContext) -> StationResult:
        provider_name = self.cfg.provider or ctx.settings.default_captioner
        provider = get_vision_provider(provider_name, self.cfg.model)
        mode = self.cfg.params.get("mode", "detailed")
        payload = prepare_for_vision_api(
            from_bytes(image), max_side=int(self.cfg.params.get("max_side", 1024))
        )
        record = StationRecord(
            kind="caption",
            provider=provider.name,
            model=provider.model,
            params={"mode": mode},
            seed=None,
        )
        try:
            text, usage, meta = provider.caption(payload, mode)
        except ProviderRefusal as e:
            record.error = str(e)
            record.usage = Usage()
            return StationResult(image=None, record=record, caption=None)
        record.prompt_or_caption = text
        record.usage = usage
        record.raw = meta
        record.model_version = meta.get("served_model") or meta.get("model_version")
        return StationResult(image=None, record=record, caption=text)

    def run(self, image: bytes, image_sha: str, ctx: StationContext) -> StationResult:
        res = super().run(image, image_sha, ctx)
        # the captioned image passes through unchanged
        res.image = image
        return res

    def estimated_cost_usd(self) -> float:
        model = self.cfg.model or "claude-sonnet-5-5"
        return (
            text_list_price(model, 2000, 400)
            if (self.cfg.provider or "anthropic") in ("anthropic", "openai")
            else 0.0
        )
