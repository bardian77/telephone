"""Extract station: structured attributes for the survival metric. Does not change the image."""

from __future__ import annotations

from ..imageio import from_bytes, prepare_for_vision_api
from ..models import StationRecord, Usage
from ..providers import ProviderRefusal, get_vision_provider
from .base import Station, StationContext, StationResult, estimate_vision_call


class ExtractStation(Station):
    kind = "extract"
    produces_image = False

    def _run(self, image: bytes, ctx: StationContext) -> StationResult:
        provider_name = self.cfg.provider or ctx.settings.default_captioner
        provider = get_vision_provider(provider_name, self.cfg.model)
        payload = prepare_for_vision_api(from_bytes(image))
        record = StationRecord(
            kind="extract", provider=provider.name, model=provider.model, params={}, seed=None
        )
        try:
            attrs, usage, meta = provider.extract(payload)
        except ProviderRefusal as e:
            record.error = str(e)
            record.usage = Usage()
            return StationResult(image=None, record=record, caption=ctx.caption)
        record.usage = usage
        record.raw = {**meta, "attributes": attrs.model_dump()}
        record.model_version = meta.get("served_model") or meta.get("model_version")
        return StationResult(image=None, record=record, caption=ctx.caption, attributes=attrs)

    def run(self, image: bytes, image_sha: str, ctx: StationContext) -> StationResult:
        res = super().run(image, image_sha, ctx)
        res.image = image
        return res

    def estimated_cost_usd(self) -> float:
        return estimate_vision_call(self.cfg, output_tokens=300)
