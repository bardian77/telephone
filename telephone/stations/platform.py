"""Platform station: what an upload does to a photograph.

Resize to a maximum edge, re-encode as JPEG at a given quality with chroma subsampling, and
strip all metadata. Presets approximate what popular platforms do (public write-ups and
measurements vary; these are documented defaults, not claims about any platform's code).
"""

from __future__ import annotations

from typing import Any

from ..imageio import fit_within, from_bytes, to_jpeg_bytes, to_png_bytes
from ..models import StationRecord, Usage
from .base import Station, StationContext, StationResult

PRESETS: dict[str, dict[str, Any]] = {
    # name: max_side, quality, subsampling
    "instagram": {"max_side": 1080, "quality": 72, "subsampling": "4:2:0"},
    "whatsapp": {"max_side": 1600, "quality": 60, "subsampling": "4:2:0"},
    "twitter": {"max_side": 2048, "quality": 85, "subsampling": "4:2:0"},
    "facebook": {"max_side": 2048, "quality": 71, "subsampling": "4:2:0"},
    "messenger": {"max_side": 1280, "quality": 55, "subsampling": "4:2:0"},
    "harsh": {"max_side": 512, "quality": 30, "subsampling": "4:2:0"},
    "gentle": {"max_side": 4096, "quality": 95, "subsampling": "4:4:4"},
    "screenshot": {
        "max_side": 1170,
        "quality": 80,
        "subsampling": "4:2:0",
    },  # phone screenshot then re-upload
}


def resolve_params(params: dict[str, Any]) -> dict[str, Any]:
    out = dict(PRESETS.get(params.get("preset", ""), PRESETS["instagram"]))
    for k in ("max_side", "quality", "subsampling", "output"):
        if k in params:
            out[k] = params[k]
    out["output"] = out.get("output", "jpeg")
    return out


class PlatformStation(Station):
    kind = "platform"

    def _run(self, image: bytes, ctx: StationContext) -> StationResult:
        p = resolve_params(self.cfg.params)
        img = from_bytes(image)  # from_bytes already drops EXIF by converting to RGB
        img = fit_within(img, int(p["max_side"]))
        if p["output"] == "png":
            data = to_png_bytes(img)
        else:
            data = to_jpeg_bytes(img, quality=int(p["quality"]), subsampling=p["subsampling"])
        record = StationRecord(
            kind="platform",
            provider="local",
            model="pillow",
            params={**p, "preset": self.cfg.params.get("preset")},
            seed=None,
            usage=Usage(),
            raw={"width": img.width, "height": img.height, "bytes": len(data)},
        )
        return StationResult(image=data, record=record, caption=ctx.caption)
