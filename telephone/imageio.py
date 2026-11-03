"""Small image helpers: loading, hashing, encoding. Everything in the pipeline passes PNG bytes around."""

from __future__ import annotations

import base64
import hashlib
import io
from pathlib import Path

from PIL import Image, ImageOps


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_image(path: str | Path) -> Image.Image:
    """Open, apply EXIF orientation, convert to RGB."""
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)
    return img.convert("RGB")


def to_png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=False)
    return buf.getvalue()


def to_jpeg_bytes(img: Image.Image, quality: int = 85, subsampling: int | str = "4:2:0") -> bytes:
    """JPEG with no metadata. subsampling 0=4:4:4, 1=4:2:2, 2=4:2:0."""
    buf = io.BytesIO()
    sub = (
        {"4:4:4": 0, "4:2:2": 1, "4:2:0": 2}.get(subsampling, subsampling)
        if isinstance(subsampling, str)
        else subsampling
    )
    img.save(buf, format="JPEG", quality=quality, subsampling=sub, optimize=True)
    return buf.getvalue()


def from_bytes(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data)).convert("RGB")


def to_base64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def media_type_of(data: bytes) -> str:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "application/octet-stream"


def fit_within(img: Image.Image, max_side: int) -> Image.Image:
    """Downscale so the longest side is max_side. Never upscales."""
    w, h = img.size
    scale = max_side / max(w, h)
    if scale >= 1:
        return img
    return img.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)


def prepare_for_vision_api(img: Image.Image, max_side: int = 1024, quality: int = 90) -> bytes:
    """Vision models downsample internally; send a bounded JPEG to keep tokens and cost predictable."""
    return to_jpeg_bytes(fit_within(img, max_side), quality=quality, subsampling="4:4:4")


def save_bytes(path: str | Path, data: bytes) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return p
