"""Pixel-structure metrics. Meaningful for compression-only chains, where geometry is preserved;
for regenerated images they mostly measure 'is this a completely different picture', which the
README says plainly."""

from __future__ import annotations

import numpy as np
from PIL import Image

from ..imageio import from_bytes
from .embed import MetricsUnavailable


def _pair_gray(image_a: bytes, image_b: bytes, size: int = 512) -> tuple[np.ndarray, np.ndarray]:
    a = from_bytes(image_a).convert("L")
    b = from_bytes(image_b).convert("L").resize(a.size, Image.BICUBIC)
    a = a.resize((size, round(size * a.height / a.width)), Image.BICUBIC)
    b = b.resize(a.size, Image.BICUBIC)
    return np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)


def ssim_score(image_a: bytes, image_b: bytes) -> float:
    """Structural similarity, 1 identical.

    Uses scikit-image's windowed SSIM when installed. Without it, falls back to a single global
    SSIM term over the whole image, which barely reacts to local JPEG damage and is not
    comparable to published SSIM values. Install scikit-image for the real metric.
    """
    ga, gb = _pair_gray(image_a, image_b)
    try:
        from skimage.metrics import structural_similarity

        return float(structural_similarity(ga, gb, data_range=255.0))
    except ImportError:
        return _ssim_global(ga, gb)


def _ssim_global(a: np.ndarray, b: np.ndarray) -> float:
    """One SSIM term over the whole image (no sliding window). A coarse stand-in only."""
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    mu_a, mu_b = a.mean(), b.mean()
    va, vb = a.var(), b.var()
    cov = ((a - mu_a) * (b - mu_b)).mean()
    return float(
        ((2 * mu_a * mu_b + c1) * (2 * cov + c2)) / ((mu_a**2 + mu_b**2 + c1) * (va + vb + c2))
    )


_lpips_model = None


def lpips_distance(image_a: bytes, image_b: bytes) -> float:
    """LPIPS (AlexNet), 0 identical. Needs torch and the lpips package plus a one-off weight download."""
    global _lpips_model
    try:
        import lpips
        import torch
    except ImportError as e:
        raise MetricsUnavailable("pip install 'telephone[metrics]' for LPIPS") from e
    if _lpips_model is None:
        try:
            _lpips_model = lpips.LPIPS(net="alex", verbose=False).eval()
        except Exception as e:  # noqa: BLE001
            raise MetricsUnavailable(f"Could not load LPIPS weights: {e}") from e
    a = from_bytes(image_a).resize((256, 256))
    b = from_bytes(image_b).resize((256, 256))

    def t(img: Image.Image):
        arr = np.asarray(img, dtype=np.float32) / 127.5 - 1.0
        return torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0)

    with torch.no_grad():
        return float(_lpips_model(t(a), t(b)).item())
