"""Fine detail at a picture's own size, compared with the same part of the original.

Why this exists. The project's SSIM (structural.py) shrinks both pictures to 512 px wide before
it compares them, so it cannot see the loss of detail finer than that. And when a chain crops
the picture a little every pass, any comparison with the WHOLE original mostly measures the
cropping, not the damage.

So here each generation is compared, at its own size, with a reference: the part of the
original that the generation still shows, resampled once to the generation's size. "Registered"
means lined up like that. Three numbers come out:

  ssim_native  SSIM against the reference at the generation's own size, 1 identical.
  detail_kept  How much pixel-to-pixel variation the generation has, as a share of the
               reference's. 1.0 means as much fine detail as one clean resize. JPEG blocks add
               false edges, so this can overstate what is left and can go above 1. It is read
               together with ssim_native, never alone.
  frame_kept   The share of the original's area that is still in the picture.

This only means something for chains that scale, crop and re-save the same picture (the
platform and screenshot stations). A picture that was redrawn from a description has no "same
part of the original" to compare with.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from PIL import Image

from ..imageio import from_bytes
from ..models import StationRecord
from .structural import _ssim_global

METHOD = (
    "each generation at its own size, against the same region of the original resampled once "
    "(Lanczos); ssim_native: windowed SSIM on luminance; detail_kept: variance of the "
    "4-neighbour Laplacian, generation over reference"
)
SEARCH_PX = 3  # how far registration_shift looks in each direction


@dataclass(frozen=True)
class CropBox:
    """The part of the original a generation still shows, in the original's own pixels."""

    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    @property
    def area(self) -> float:
        return self.width * self.height


def whole(width: int, height: int) -> CropBox:
    """The box before anything has been cropped: the whole original."""
    return CropBox(0.0, 0.0, float(width), float(height))


def after_screenshot(box: CropBox, raw: dict[str, Any]) -> CropBox:
    """The box after one screenshot pass.

    The station showed what was left of the picture at `displayed_width` x `displayed_height`
    and then took `crop` pixels off each edge, counted in displayed pixels. One displayed pixel
    is box.width / displayed_width original pixels across, and likewise down. The two sides are
    scaled on their own because the displayed size is rounded to whole pixels.
    """
    per_px_x = box.width / raw["displayed_width"]
    per_px_y = box.height / raw["displayed_height"]
    crop = raw["crop"]
    return CropBox(
        box.x0 + crop["left"] * per_px_x,
        box.y0 + crop["top"] * per_px_y,
        box.x1 - crop["right"] * per_px_x,
        box.y1 - crop["bottom"] * per_px_y,
    )


def box_after(box: CropBox, stations: list[StationRecord]) -> CropBox:
    """The box after one generation, given what each of its stations recorded.

    Only a screenshot can crop. An upload scales the picture and leaves the box alone.
    """
    for record in stations:
        if record.kind == "screenshot" and record.raw and "crop" in record.raw:
            box = after_screenshot(box, record.raw)
    return box


def reference_for(original: bytes, box: CropBox, size: tuple[int, int]) -> Image.Image:
    """What the generation would be with no damage at all: the original's `box`, resampled
    once to `size`. Greyscale, because the comparison is made on brightness."""
    grey = from_bytes(original).convert("L")
    return grey.resize(size, Image.Resampling.LANCZOS, box=(box.x0, box.y0, box.x1, box.y1))


def _fine_detail(a: np.ndarray) -> float:
    """Variance of the 4-neighbour Laplacian: how much each pixel differs from the average of
    the four beside it. High for crisp texture, low for a blur."""
    lap = a[:-2, 1:-1] + a[2:, 1:-1] + a[1:-1, :-2] + a[1:-1, 2:] - 4.0 * a[1:-1, 1:-1]
    return float(lap.var())


def _ssim(a: np.ndarray, b: np.ndarray) -> float:
    if min(a.shape) < 7:  # too small for the sliding window
        return _ssim_global(a, b)
    try:
        from skimage.metrics import structural_similarity

        return float(structural_similarity(a, b, data_range=255.0))
    except ImportError:
        return _ssim_global(a, b)


def registration_shift(
    generation: Image.Image, reference: Image.Image, search: int = SEARCH_PX
) -> tuple[int, int]:
    """Is the generation lined up with its reference? Returns (dx, dy), the whole-pixel shift
    of the reference that matches the generation best, looking up to `search` px each way.

    (0, 0) means the box is right. Anything else means the generation shows a slightly different
    part of the original than the box says: (2, -1) is 2 px to the right and 1 px up.
    """
    a = np.asarray(generation.convert("L"), dtype=np.float64)
    b = np.asarray(reference.convert("L"), dtype=np.float64)
    h, w = a.shape
    if h <= 2 * search + 1 or w <= 2 * search + 1:
        return (0, 0)
    inner = a[search : h - search, search : w - search]
    best, best_err = (0, 0), None
    # nearest shifts first, so that a tie goes to the smaller shift
    shifts = sorted(
        ((dx, dy) for dx in range(-search, search + 1) for dy in range(-search, search + 1)),
        key=lambda s: (abs(s[0]) + abs(s[1]), s),
    )
    for dx, dy in shifts:
        moved = b[search + dy : h - search + dy, search + dx : w - search + dx]
        err = float(((inner - moved) ** 2).mean())
        if best_err is None or err < best_err:
            best, best_err = (dx, dy), err
    return best


def detail_scores(generation: bytes, original: bytes, box: CropBox) -> dict[str, Any]:
    """The three numbers for one generation, plus what they were measured on.

    `box` is the part of the original this generation still shows (see box_after).
    """
    gen = from_bytes(generation).convert("L")
    orig_w, orig_h = from_bytes(original).size
    ref = reference_for(original, box, gen.size)
    a = np.asarray(gen, dtype=np.float64)
    b = np.asarray(ref, dtype=np.float64)
    ref_detail = _fine_detail(b)
    return {
        "width": gen.width,
        "height": gen.height,
        "box": [box.x0, box.y0, box.x1, box.y1],
        "frame_kept": box.area / float(orig_w * orig_h),
        "ssim_native": _ssim(a, b),
        # a flat reference has no detail to keep a share of
        "detail_kept": _fine_detail(a) / ref_detail if ref_detail > 0 else None,
        "shift": list(registration_shift(gen, ref)),
    }
