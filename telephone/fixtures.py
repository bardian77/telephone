"""Synthetic test images. They are not photographs and are never part of the work; they exist so
the pipeline, the tests, the CI and the sample website run without the author's originals."""

from __future__ import annotations

import random
from pathlib import Path

from PIL import Image, ImageDraw

KINDS = ["portrait", "street", "landscape", "text", "abstract"]


def make_fixture(path: Path, kind: str, seed: int = 0, size: tuple[int, int] = (768, 576)) -> Path:
    rng = random.Random(f"{kind}{seed}")
    w, h = size
    img = Image.new("RGB", size, (rng.randint(60, 200), rng.randint(60, 200), rng.randint(60, 200)))
    d = ImageDraw.Draw(img)
    if kind == "landscape":
        d.rectangle(
            [0, 0, w, h * 0.55], fill=(120 + rng.randint(0, 60), 160 + rng.randint(0, 60), 220)
        )
        d.rectangle(
            [0, h * 0.55, w, h], fill=(60 + rng.randint(0, 40), 120 + rng.randint(0, 50), 50)
        )
        d.ellipse([w * 0.7, h * 0.1, w * 0.8, h * 0.1 + w * 0.1], fill=(255, 240, 180))
    elif kind == "portrait":
        d.ellipse([w * 0.35, h * 0.15, w * 0.65, h * 0.55], fill=(230, 190, 160))
        d.rectangle(
            [w * 0.3, h * 0.55, w * 0.7, h],
            fill=(40 + rng.randint(0, 60), 40, 90 + rng.randint(0, 80)),
        )
        d.ellipse([w * 0.43, h * 0.3, w * 0.47, h * 0.34], fill=(30, 30, 30))
        d.ellipse([w * 0.53, h * 0.3, w * 0.57, h * 0.34], fill=(30, 30, 30))
    elif kind == "text":
        d.rectangle([0, 0, w, h], fill=(245, 245, 240))
        for i, line in enumerate(
            ["OPEN", "FRESH BREAD", "SINCE 1974", f"No. {rng.randint(1, 99)}"]
        ):
            d.text(
                (w * 0.1, h * 0.15 + i * h * 0.18), line, fill=(20, 20, 20), font_size=int(h * 0.12)
            )
    elif kind == "abstract":
        for _ in range(40):
            x0, y0 = rng.randint(0, w), rng.randint(0, h)
            d.line(
                [x0, y0, x0 + rng.randint(-300, 300), y0 + rng.randint(-300, 300)],
                fill=(rng.randint(0, 255), rng.randint(0, 255), rng.randint(0, 255)),
                width=rng.randint(2, 30),
            )
    else:  # street
        d.rectangle([0, h * 0.6, w, h], fill=(70, 70, 75))
        for i in range(5):
            x = i * w / 5
            d.rectangle(
                [x, h * 0.1 + rng.randint(0, 80), x + w / 5 - 10, h * 0.6],
                fill=(rng.randint(90, 180), rng.randint(80, 150), rng.randint(80, 150)),
            )
        d.rectangle([w * 0.3, h * 0.5, w * 0.5, h * 0.62], fill=(200, 30, 30))
        d.text((w * 0.08, h * 0.25), "CAFE", fill=(255, 255, 255), font_size=int(h * 0.08))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="PNG")
    return path


def make_all(folder: Path) -> list[Path]:
    return [
        make_fixture(folder / f"{kind}_fixture_{i:02d}.png", kind, seed=i)
        for i, kind in enumerate(KINDS)
    ]
