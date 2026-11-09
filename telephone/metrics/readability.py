"""Machine readability: can OCR still read the text, can a face detector still find the faces?"""

from __future__ import annotations

import logging
import shutil

import numpy as np

from ..imageio import from_bytes

_cascade = None
CASCADE_FILE = "haarcascade_frontalface_default.xml"
CASCADE_URL = (
    f"https://raw.githubusercontent.com/opencv/opencv/4.x/data/haarcascades/{CASCADE_FILE}"
)


def _cascade_path() -> str | None:
    """Find the Haar cascade: env var, OpenCV's bundled copy, our data dir, else download it once."""
    import os
    from pathlib import Path

    env = os.environ.get("TELEPHONE_HAARCASCADE")
    if env and Path(env).exists():
        return env
    try:
        import cv2

        bundled = Path(getattr(cv2.data, "haarcascades", "")) / CASCADE_FILE
        if bundled.exists():
            return str(bundled)
    except Exception:  # noqa: BLE001
        pass
    from ..config import get_settings

    local = get_settings().telephone_data_dir / "models" / CASCADE_FILE
    if local.exists():
        return str(local)
    try:
        import httpx

        local.parent.mkdir(parents=True, exist_ok=True)
        r = httpx.get(CASCADE_URL, timeout=60, follow_redirects=True)
        r.raise_for_status()
        local.write_bytes(r.content)
        return str(local)
    except Exception:  # noqa: BLE001
        return None


def ocr_stats(image: bytes) -> tuple[int, int] | None:
    """(characters, words) read by tesseract, or None when tesseract is not installed."""
    if shutil.which("tesseract") is None:
        return None
    try:
        import pytesseract
    except ImportError:
        return None
    img = from_bytes(image)
    text = pytesseract.image_to_string(img)
    words = [w for w in text.split() if any(c.isalnum() for c in w)]
    return sum(len(w) for w in words), len(words)


def face_count(image: bytes) -> int | None:
    """Frontal faces found by the OpenCV Haar cascade, or None when OpenCV is missing or broken.

    A readability helper must never stop a chain: any failure (no cv2, a partial cv2 build
    without CascadeClassifier, a missing cascade file) is recorded as None, once, with a warning.
    """
    global _cascade, _face_failed
    if _face_failed:
        return None
    try:
        import cv2

        if _cascade is None:
            path = _cascade_path()
            if path is None:
                raise RuntimeError("Haar cascade file not found")
            _cascade = cv2.CascadeClassifier(path)
        img = from_bytes(image)
        arr = cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2GRAY)
        faces = _cascade.detectMultiScale(arr, scaleFactor=1.1, minNeighbors=5, minSize=(24, 24))
        return int(len(faces))
    except Exception as e:  # noqa: BLE001
        _face_failed = True
        logging.getLogger("telephone").warning("face count unavailable, recording None: %s", e)
        return None


_face_failed = False
