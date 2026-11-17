"""Fine detail at a picture's own size, compared with the same part of the original.

Why this exists. The project's SSIM (structural.py) shrinks both pictures to 512 px wide before
it compares them, so it cannot see the loss of detail finer than that. And when a chain crops
the picture a little every pass, any comparison with the WHOLE original mostly measures the
cropping, not the damage.

So here each generation is compared, at its own size, with a reference: the part of the
original that the generation still shows, resampled once to the generation's size. "Registered"
means lined up like that. Three numbers come out:

  ssim_native    SSIM against the reference at the generation's own size, 1 identical.
  detail_kept    The share of the reference's fine detail that is still there, in the same
                 place. 1.0 means all of it. "Fine detail" is what a slight blur would take
                 away from a picture. Marks that were never in the photograph, such as the
                 speckle that saving a JPEG adds, do not count: they are not in the same place
                 as anything in the reference.
  detail_energy  How much fine detail the generation has in total, whatever it is, as a share
                 of the reference's. It counts what saving added as well, so it can go well
                 above 1 for a picture that has got worse. It is kept beside detail_kept to
                 show when that has happened; it is not a measure of what is left.
  frame_kept     The share of the original's area that is still in the picture.

Why two detail numbers: the first version of this file only had the total (as the variance of
a Laplacian). On a chain that saved a JPEG at quality 80 and then at quality 60 it reported
1.83, "183% of the detail", for a picture whose SSIM had fallen to 0.86. Counting only what
lines up with the reference is the correction.

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
    "(Lanczos); ssim_native: windowed SSIM on luminance; fine detail: a picture minus a "
    "Gaussian blur of itself (sigma 1.5 px); detail_kept: the generation's fine detail "
    "projected on the reference's; detail_energy: the generation's total over the reference's"
)
SEARCH_PX = 3  # how far registration_shift looks in each direction
BLUR_SIGMA = 1.5  # the slight blur that defines "fine detail", in pixels


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


def _picture(original: bytes | Image.Image) -> Image.Image:
    """The original as a picture. A chain's original can be opened once and passed in."""
    return original if isinstance(original, Image.Image) else from_bytes(original)


def reference_for(
    original: bytes | Image.Image, box: CropBox, size: tuple[int, int]
) -> Image.Image:
    """What the generation would be with no damage at all: the original's `box`, resampled
    once to `size`. Greyscale, because the comparison is made on brightness."""
    grey = _picture(original).convert("L")
    return grey.resize(size, Image.Resampling.LANCZOS, box=(box.x0, box.y0, box.x1, box.y1))


def _blur(a: np.ndarray, sigma: float = BLUR_SIGMA) -> np.ndarray:
    """A Gaussian blur with numpy alone: one pass across, one pass down."""
    radius = int(3 * sigma + 0.5)
    x = np.arange(-radius, radius + 1)
    weights = np.exp(-(x**2) / (2 * sigma**2))
    weights /= weights.sum()
    out = a
    for axis in (0, 1):
        pad = [(radius, radius) if ax == axis else (0, 0) for ax in (0, 1)]
        padded = np.pad(out, pad, mode="edge")
        total = np.zeros_like(out, dtype=np.float64)
        for i, w in enumerate(weights):
            window = [slice(None), slice(None)]
            window[axis] = slice(i, i + out.shape[axis])
            total += w * padded[tuple(window)]
        out = total
    return out


def _fine(a: np.ndarray) -> np.ndarray:
    """A picture's fine detail: what a slight blur takes away from it. The outer few pixels
    are left out, where the blur has nothing beyond the edge to work with."""
    edge = int(3 * BLUR_SIGMA + 0.5)
    detail = a - _blur(a)
    if min(a.shape) > 4 * edge:
        detail = detail[edge:-edge, edge:-edge]
    return detail


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
    if h > 640 or w > 640:  # the middle of a large picture is enough to tell, and much quicker
        top, left = max(0, (h - 640) // 2), max(0, (w - 640) // 2)
        a, b = a[top : top + 640, left : left + 640], b[top : top + 640, left : left + 640]
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


def detail_scores(generation: bytes, original: bytes | Image.Image, box: CropBox) -> dict[str, Any]:
    """The numbers for one generation, plus what they were measured on.

    `box` is the part of the original this generation still shows (see box_after). `original`
    is the original's bytes, or the picture already opened.
    """
    gen = from_bytes(generation).convert("L")
    whole_original = _picture(original)
    orig_w, orig_h = whole_original.size
    ref = reference_for(whole_original, box, gen.size)
    a = np.asarray(gen, dtype=np.float64)
    b = np.asarray(ref, dtype=np.float64)
    fine_a, fine_b = _fine(a), _fine(b)
    in_reference = float((fine_b * fine_b).sum())
    return {
        "width": gen.width,
        "height": gen.height,
        "box": [box.x0, box.y0, box.x1, box.y1],
        "frame_kept": box.area / float(orig_w * orig_h),
        "ssim_native": _ssim(a, b),
        # a flat reference has no fine detail to keep a share of
        "detail_kept": float((fine_a * fine_b).sum()) / in_reference if in_reference else None,
        "detail_energy": float((fine_a * fine_a).sum()) / in_reference if in_reference else None,
        "shift": list(registration_shift(gen, ref)),
    }
