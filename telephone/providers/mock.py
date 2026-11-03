"""Deterministic offline providers.

They exist so the whole pipeline, the tests, the website and the CI run with no keys and no
spend. They also drift on purpose: each caption/regeneration round changes a little, so chains
built with them look like chains (just not like photographs).
"""

from __future__ import annotations

import hashlib
import random
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from ..imageio import from_bytes, to_png_bytes
from ..models import Attributes, Usage
from .base import CaptionMode

OBJECTS = [
    "bicycle",
    "lamp post",
    "red car",
    "dog",
    "shop sign",
    "umbrella",
    "tree",
    "bench",
    "bus",
    "window",
    "balloon",
    "coffee cup",
    "pigeon",
    "scooter",
    "traffic light",
    "awning",
    "puddle",
]
SETTINGS = [
    "busy city street",
    "quiet suburban road",
    "harbour at dusk",
    "market square",
    "railway platform",
]
MOODS = ["calm", "hectic", "melancholy", "cheerful", "tense"]
LIGHTING = ["daylight", "overcast", "golden hour", "night", "artificial"]
COLORS = ["red", "blue", "green", "yellow", "grey", "white", "black", "orange", "purple", "brown"]


def _rng_for(data: bytes, salt: str = "") -> random.Random:
    h = hashlib.sha256(data + salt.encode()).digest()
    return random.Random(int.from_bytes(h[:8], "big"))


def _dominant_colors(img: Image.Image, n: int = 3) -> list[str]:
    small = img.resize((16, 16))
    counts: dict[str, int] = {}
    for r, g, b in np.asarray(small).reshape(-1, 3).tolist():
        name = _nearest_color(r, g, b)
        counts[name] = counts.get(name, 0) + 1
    return [c for c, _ in sorted(counts.items(), key=lambda kv: -kv[1])[:n]]


def _nearest_color(r: int, g: int, b: int) -> str:
    palette = {
        "red": (200, 40, 40),
        "blue": (40, 60, 200),
        "green": (40, 160, 60),
        "yellow": (220, 200, 40),
        "grey": (128, 128, 128),
        "white": (240, 240, 240),
        "black": (15, 15, 15),
        "orange": (230, 130, 30),
        "purple": (130, 40, 160),
        "brown": (120, 80, 40),
    }
    return min(
        palette,
        key=lambda k: sum((a - b_) ** 2 for a, b_ in zip((r, g, b), palette[k], strict=True)),
    )


class MockVision:
    name = "mock"
    supports_seed = True

    def __init__(self, model: str = "mock-vision", drift: float = 0.25):
        self.model = model
        self.drift = drift  # probability each object is swapped per reading

    def _read(self, image: bytes) -> dict[str, Any]:
        img = from_bytes(image)
        rng = _rng_for(image, "read")
        k = 3 + rng.randint(0, 4)
        objects = rng.sample(OBJECTS, k)
        return {
            "objects": objects,
            "people_count": rng.choice([0, 0, 1, 1, 2, 3]),
            "visible_text": ["TELEPHONE"] if rng.random() < 0.6 else [],
            "setting": rng.choice(SETTINGS),
            "lighting": rng.choice(LIGHTING),
            "mood": rng.choice(MOODS),
            "dominant_colors": _dominant_colors(img),
            "camera_angle": rng.choice(["eye level", "high angle", "low angle"]),
            "is_photograph": rng.random() < 0.8,
            "size": img.size,
        }

    def caption(
        self, image: bytes, mode: CaptionMode, seed: int | None = None
    ) -> tuple[str, Usage, dict[str, Any]]:
        r = self._read(image)
        objs = ", ".join(r["objects"])
        if mode == "short":
            text = f"A {r['mood']} {r['setting']} with {r['objects'][0]} and {r['objects'][1]}."
        elif mode == "literal":
            text = objs
        else:
            text = (
                f"A photograph of a {r['setting']} in {r['lighting']} light. In the frame: {objs}. "
                f"{r['people_count']} people are visible. The mood is {r['mood']}. Dominant colours are "
                f"{', '.join(r['dominant_colors'])}. Camera at {r['camera_angle']}."
                + (" A sign reads 'TELEPHONE'." if r["visible_text"] else "")
            )
        usage = Usage(
            input_tokens=1200,
            output_tokens=len(text.split()) * 2,
            cost_usd=0.0,
            list_price_usd=0.0,
            latency_ms=1,
        )
        return text, usage, {"mock": True}

    def extract(self, image: bytes) -> tuple[Attributes, Usage, dict[str, Any]]:
        r = self._read(image)
        r.pop("size")
        attrs = Attributes(**r)
        return attrs, Usage(input_tokens=1200, output_tokens=120, latency_ms=1), {"mock": True}


class MockImageGen:
    name = "mock"
    supports_seed = True

    def __init__(self, model: str = "mock-gen"):
        self.model = model

    def generate(
        self, prompt: str, seed: int | None = None, width: int = 1024, height: int = 1024
    ) -> tuple[bytes, Usage, dict[str, Any]]:
        rng = _rng_for(prompt.encode(), f"gen{seed}")
        words = [w.strip(".,'\"").lower() for w in prompt.split()]
        colors = [c for c in COLORS if c in words] or ["grey"]
        palette = {
            "red": (200, 40, 40),
            "blue": (40, 60, 200),
            "green": (40, 160, 60),
            "yellow": (220, 200, 40),
            "grey": (128, 128, 128),
            "white": (240, 240, 240),
            "black": (15, 15, 15),
            "orange": (230, 130, 30),
            "purple": (130, 40, 160),
            "brown": (120, 80, 40),
        }
        img = Image.new("RGB", (width, height), palette[colors[0]])
        d = ImageDraw.Draw(img)
        n_shapes = 6 + sum(
            1 for w in words if w in OBJECTS or w in {o.split()[-1] for o in OBJECTS}
        )
        for _ in range(n_shapes):
            c = palette[rng.choice(colors + ["white", "black"])]
            x0, y0 = rng.randint(0, width - 60), rng.randint(0, height - 60)
            x1, y1 = x0 + rng.randint(40, width // 2), y0 + rng.randint(40, height // 2)
            (d.rectangle if rng.random() < 0.5 else d.ellipse)([x0, y0, x1, y1], fill=c)
        if "telephone" in words or "sign" in words:
            d.text((width // 10, height // 10), "TELEPHONE", fill=(255, 255, 255))
        data = to_png_bytes(img)
        return data, Usage(images=1, latency_ms=1), {"mock": True, "prompt_words": len(words)}
