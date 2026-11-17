"""Screenshot station: a phone shows the picture and the user takes a screenshot of it.

The phone shows the picture as large as fits on its screen, so the picture is redrawn on the
screen's pixel grid: scaled up or down, keeping its shape. The user then crops the screenshot
back to the picture. The result is saved as a PNG, which loses nothing, as a phone does. The
platform station that follows does the JPEG.

This is the step Pete Ashton repeated in "I Am Sitting in Stagram": every repost was a
screenshot, so the picture was resampled before each upload.

With an exact crop (`crop_jitter_px` 0) every pass resamples the picture in the same way,
between the same two pixel grids. With a loose crop (`crop_jitter_px` N) up to N pixels are
lost from each edge, a different few every generation, so the grid lands somewhere slightly
different every pass and the picture is slowly reframed.
"""

from __future__ import annotations

from typing import Any

from PIL import Image

from ..cache import StationCache
from ..imageio import from_bytes, to_png_bytes
from ..models import StationConfig, StationRecord, Usage, stable_hash
from .base import Station, StationContext, StationResult

DEFAULTS: dict[str, Any] = {
    "screen_width": 1170,  # an iPhone 12, 13 or 14 screen, in pixels
    "screen_height": 2532,
    "crop_jitter_px": 0,  # 0: the crop is exact. N: up to N pixels are lost from each edge
    "resample": "bicubic",
}
RESAMPLE = {"bicubic": Image.Resampling.BICUBIC, "bilinear": Image.Resampling.BILINEAR}
EDGES = ("left", "top", "right", "bottom")


def _whole_number(name: str, value: Any) -> int:
    """`value` as an int. 6 and 6.0 are whole numbers; 0.6, "six" and an empty value are not.

    Cutting 0.6 down to 0 would quietly turn a loose crop into an exact one, so anything that
    is not a whole number is an error that names the setting.
    """
    is_number = isinstance(value, int | float) and not isinstance(value, bool)
    if not is_number or not float(value).is_integer():
        raise ValueError(f"screenshot station: {name} must be a whole number, not {value!r}")
    return int(value)


def resolve_params(params: dict[str, Any]) -> dict[str, Any]:
    """The station's settings, with the defaults filled in.

    A misspelt name or a value that makes no sense is an error, so a typo in an experiment file
    can never quietly run the default instead. (`seed` is allowed: every station accepts it.)
    """
    unknown = sorted(set(params) - set(DEFAULTS) - {"seed"})
    if unknown:
        raise ValueError(f"screenshot station: unknown params {unknown}; known: {sorted(DEFAULTS)}")
    p = {**DEFAULTS, **{k: v for k, v in params.items() if k in DEFAULTS}}
    if p["resample"] not in RESAMPLE:
        raise ValueError(
            f"screenshot station: resample must be one of {sorted(RESAMPLE)}, not {p['resample']!r}"
        )
    for name in ("screen_width", "screen_height", "crop_jitter_px"):
        p[name] = _whole_number(name, p[name])
    if p["screen_width"] < 1 or p["screen_height"] < 1:
        raise ValueError("screenshot station: screen_width and screen_height must be at least 1")
    if p["crop_jitter_px"] < 0:
        raise ValueError("screenshot station: crop_jitter_px cannot be negative")
    return p


def screen_size(width: int, height: int, screen_width: int, screen_height: int) -> tuple[int, int]:
    """The size at which the phone shows a picture: as large as fits, same shape.

    Whichever side reaches the edge of the screen first lands on it exactly; the other side
    follows in proportion.
    """
    if screen_width * height <= screen_height * width:  # the width fills the screen first
        return screen_width, max(1, round(height * screen_width / width))
    return max(1, round(width * screen_height / height)), screen_height


def crop_offsets(seed: int | None, generation: int, jitter: int) -> dict[str, int]:
    """How many pixels the loose crop takes off each edge: a whole number from 0 to `jitter`.

    Each number comes from a hash of the seed, the generation and the edge's name, so a chain
    gets the same crops on every machine and different ones every generation. Python's own
    hash() is not used, because it changes from one run of Python to the next.
    """
    if jitter <= 0:
        return dict.fromkeys(EDGES, 0)
    return {
        edge: int(stable_hash(["screenshot crop", seed, generation, edge]), 16) % (jitter + 1)
        for edge in EDGES
    }


def clamp_crop(crop: dict[str, int], width: int, height: int) -> dict[str, int]:
    """Limit the crop so a tiny picture is never cut down to nothing.

    No edge may take more than just under half of its side, so at least one pixel is left
    however small the picture is.
    """
    most_x, most_y = (width - 1) // 2, (height - 1) // 2
    return {
        "left": min(crop["left"], most_x),
        "top": min(crop["top"], most_y),
        "right": min(crop["right"], most_x),
        "bottom": min(crop["bottom"], most_y),
    }


class ScreenshotStation(Station):
    kind = "screenshot"

    def __init__(self, cfg: StationConfig):
        super().__init__(cfg)
        self.params = resolve_params(cfg.params)  # checked once, when the station is built

    def crop_for(self, ctx: StationContext) -> dict[str, int]:
        """The crop this generation asks for, before it is limited to the picture's size."""
        return crop_offsets(self.seed_for(ctx), ctx.generation, self.params["crop_jitter_px"])

    def cache_key(self, image_sha: str | None, ctx: StationContext) -> str:
        """The usual key, plus the crop this generation asks for.

        Without this, a later generation that happens to receive the same bytes as an earlier
        one would be handed the earlier one's output, cut with the wrong crop. With an exact
        crop the offsets are always zero, so generations still share the cache.
        """
        return StationCache.key(
            image_sha,
            self.cfg.kind,
            self.cfg.provider,
            self.cfg.model,
            {**self.params, "crop": self.crop_for(ctx)},
            self.seed_for(ctx),
        )

    def _run(self, image: bytes, ctx: StationContext) -> StationResult:
        p = self.params
        img = from_bytes(image)
        scale = min(p["screen_width"] / img.width, p["screen_height"] / img.height)
        shown = screen_size(img.width, img.height, p["screen_width"], p["screen_height"])
        img = img.resize(shown, RESAMPLE[p["resample"]])
        crop = clamp_crop(self.crop_for(ctx), *shown)
        img = img.crop(
            (crop["left"], crop["top"], shown[0] - crop["right"], shown[1] - crop["bottom"])
        )
        data = to_png_bytes(img)  # a screenshot is a PNG: nothing is lost in the saving
        record = StationRecord(
            kind="screenshot",
            provider="local",
            model="pillow",
            params=dict(p),
            # the seed only matters when the crop is loose
            seed=self.seed_for(ctx) if p["crop_jitter_px"] > 0 else None,
            usage=Usage(),
            raw={
                "scale": scale,
                "displayed_width": shown[0],
                "displayed_height": shown[1],
                "crop": crop,
                "width": img.width,
                "height": img.height,
                "bytes": len(data),
            },
        )
        return StationResult(image=data, record=record, caption=ctx.caption)
