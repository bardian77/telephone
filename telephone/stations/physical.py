"""Physical station: the loop leaves the computer.

The author displays generation n-1 on a screen, photographs it with a camera or phone, and
drops the file in a folder. This station picks up frame n from that folder so physical loops
get exactly the same metrics as digital ones. Missing frames stop the chain with a clear message
rather than inventing anything.
"""

from __future__ import annotations

from pathlib import Path

from ..imageio import load_image, to_png_bytes
from ..models import StationRecord
from .base import Station, StationContext, StationResult

EXTS = {".jpg", ".jpeg", ".png", ".heic", ".webp", ".tif", ".tiff"}


class MissingFrame(RuntimeError):
    pass


class PhysicalStation(Station):
    kind = "physical"

    def frames(self) -> list[Path]:
        folder = Path(self.cfg.params["folder"])
        return (
            sorted(p for p in folder.iterdir() if p.suffix.lower() in EXTS)
            if folder.exists()
            else []
        )

    def _run(self, image: bytes, ctx: StationContext) -> StationResult:
        frames = self.frames()
        idx = ctx.generation - 1  # frame 0 is the photograph of generation 0
        if idx >= len(frames):
            raise MissingFrame(
                f"Physical loop needs frame {ctx.generation} (file index {idx}) in {self.cfg.params['folder']}; "
                f"only {len(frames)} frames present. Photograph the screen showing generation {ctx.generation - 1} and add it."
            )
        path = frames[idx]
        img = load_image(path)
        max_side = int(self.cfg.params.get("max_side", 2048))
        from ..imageio import fit_within

        img = fit_within(img, max_side)
        record = StationRecord(
            kind="physical",
            provider="camera",
            model=self.cfg.params.get("device", "unknown"),
            params={
                "folder": str(self.cfg.params["folder"]),
                "frame": path.name,
                "max_side": max_side,
            },
            raw={"source_file": str(path)},
        )
        return StationResult(image=to_png_bytes(img), record=record, caption=ctx.caption)
