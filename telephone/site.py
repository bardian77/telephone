"""The small export the one-page website reads.

Layout under the output folder (web/public/data by default):
  site.json            every photograph, its journeys, the passes that are shown and the numbers
  img/<sha>.jpg        the pictures, named by their content so the same bytes are stored once
  img/<sha>_thumb.jpg  one small picture per photograph, for the picker

What the page shows is what the pipeline wrote. A published pass is the output file copied byte
for byte, never re-compressed for the web, because a second compression would add damage the
experiment did not make. Pass 0 is the author's own file from data/originals when it is there.

Only some passes get a picture, to keep the committed site small; `series` holds one number per
generation for every pass, shown or not. Detail and place numbers come from the files that
`telephone detail-test` and `telephone place-test` saved, and a row is only attached when it was
measured on the same bytes the ledger holds now.

Photographs under data/originals/private/ and runs on mock providers are never exported.
"""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import paths
from .config import get_settings
from .doctor import IMAGE_EXTS
from .experiments import MOCK_SUFFIX
from .export import _private_stems
from .imageio import fit_within, from_bytes, media_type_of, sha256_bytes, to_jpeg_bytes
from .ledger import Ledger
from .metrics.structural import settled_at
from .models import GenerationRecord
from .render import image_of, type_of, variant_of

DEFAULT_PASSES = [0, 1, 2, 5, 10, 20, 40]
DETAIL_KEYS = ("ssim_native", "detail_kept", "frame_kept", "box")
PLACE_KEYS = ("rank", "prob", "top", "place", "lineup_size")


def _saved_rows(path: Path) -> dict[tuple[str, int, int], dict]:
    """A results file as {(chain, repeat, generation): row}; empty when there is no file."""
    if not path.is_file():
        return {}
    rows = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            rows[(row["chain_id"], int(row.get("repeat", 0)), int(row["generation"]))] = row
    return rows


def _measured(rows: dict, rec: GenerationRecord, keys: tuple[str, ...]) -> dict | None:
    """The saved numbers for this generation, if they were measured on the bytes it holds now."""
    row = rows.get((rec.chain_id, rec.repeat, rec.generation))
    if row is None or row.get("output_sha") != rec.output_sha:
        return None
    return {k: row.get(k) for k in keys}


def _picker(rows: dict, key: str):
    """A function that reads one saved number for a generation, or None when it is not there."""

    def pick(rec: GenerationRecord):
        got = _measured(rows, rec, (key,))
        return None if got is None else got[key]

    return pick


def _original_file(stem: str) -> Path | None:
    """The author's own file for a photograph. Only the top of data/originals is looked at;
    the private folder below it is never read."""
    folder = get_settings().originals_dir
    if not folder.is_dir():
        return None
    for p in sorted(folder.glob("*")):
        if p.is_file() and p.stem == stem and p.suffix.lower() in IMAGE_EXTS:
            return p
    return None


def export_site(
    out: Path,
    experiment: str,
    variants: list[str] | None = None,
    passes: list[int] | None = None,
    max_mb: float = 40.0,
) -> dict[str, Any]:
    """Write site.json and its pictures for one experiment. Returns a short summary.

    `variants` picks the journeys and their order (default: every variant, by name). `passes`
    picks which generations get a picture. Raises ValueError, with one plain sentence, when
    there is nothing to export or the pictures would be larger than `max_mb`.
    """
    s = get_settings()
    if experiment.endswith(MOCK_SUFFIX):
        raise ValueError(
            f"{experiment} is a run on mock providers. Mock output is for tests, not the site."
        )
    led = Ledger(s.ledger_path)
    known = [row["experiment_id"] for row in led.experiments()] if s.ledger_path.exists() else []
    if experiment not in known:
        matches = [k for k in known if k.startswith(experiment) and not k.endswith(MOCK_SUFFIX)]
        if len(matches) != 1:
            raise ValueError(f"No experiment {experiment!r} in the ledger. Known: {known}")
        experiment = matches[0]
    wanted = sorted(set(passes if passes is not None else DEFAULT_PASSES))

    chains: dict[str, list[GenerationRecord]] = {}
    for rec in led.experiment(experiment):
        if rec.repeat == 0:  # the page tells one journey per variant
            chains.setdefault(rec.chain_id, []).append(rec)
    private = _private_stems()
    detail_rows = _saved_rows(s.results_dir / f"{experiment}_detail.jsonl")
    place_rows = _saved_rows(s.results_dir / f"{experiment}_place.jsonl")

    out = Path(out)
    staging = out / "img.tmp"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    written: dict[str, int] = {}  # file name -> bytes, so the same picture is stored once

    def store(data: bytes, suffix: str = "") -> str:
        name = f"{sha256_bytes(data)[:16]}{suffix}.jpg"
        if name not in written:
            (staging / name).write_bytes(data)
            written[name] = len(data)
        return f"img/{name}"

    photos: dict[str, dict[str, Any]] = {}
    made_with: dict[str, Any] = {}
    for chain_id in sorted(chains):
        stem, variant = image_of(chain_id), variant_of(chain_id)
        if stem in private or (variants is not None and variant not in variants):
            continue
        recs = sorted(chains[chain_id], key=lambda r: r.generation)
        good = [r for r in recs if not r.error and r.output_path]
        if not good or good[0].generation != 0:
            continue
        g0_path = paths.resolve(good[0].output_path)
        if not g0_path.is_file():
            continue

        photo = photos.get(stem)
        if photo is None:
            g0 = from_bytes(g0_path.read_bytes())
            thumb = to_jpeg_bytes(fit_within(g0, 320), quality=80)
            photo = photos[stem] = {
                "stem": stem,
                "type": type_of(chain_id),
                "width": g0.width,
                "height": g0.height,
                "thumb": store(thumb, "_thumb"),
                "journeys": {},
            }

        shown = []
        for rec in good:
            if rec.generation not in wanted:
                continue
            path = paths.resolve(rec.output_path)
            if not path.is_file():
                continue
            data, size, reencoded = path.read_bytes(), rec.metrics.file_bytes, False
            mine = _original_file(stem) if rec.generation == 0 else None
            if mine is not None and media_type_of(mine.read_bytes()) == "image/jpeg":
                data = mine.read_bytes()  # the photograph exactly as it entered the project
                size = len(data)
            elif media_type_of(data) != "image/jpeg":
                # generation 0 is kept as a PNG; with no original file to hand it is saved as a
                # JPEG for the page, and the page is told that these are not the first bytes
                data, size, reencoded = to_jpeg_bytes(from_bytes(data), quality=92), None, True
            place = _measured(place_rows, rec, PLACE_KEYS)
            row = place_rows.get((rec.chain_id, rec.repeat, rec.generation))
            if place is not None and row is not None and not made_with:
                made_with = {
                    k: row[k] for k in ("clip_model", "preprocessing", "lineup") if k in row
                }
            shown.append(
                {
                    "pass": rec.generation,
                    "img": store(data),
                    "width": rec.metrics.width,
                    "height": rec.metrics.height,
                    "bytes": size,
                    "reencoded": reencoded,
                    "detail": _measured(detail_rows, rec, DETAIL_KEYS),
                    "place": place,
                }
            )

        by_gen = {r.generation: r for r in good}
        last = max(by_gen)

        def column(pick, by_gen=by_gen, last=last) -> list:
            return [pick(by_gen[g]) if g in by_gen else None for g in range(last + 1)]

        ssim_prev = column(lambda r: r.metrics.ssim_to_prev)
        series = {
            "file_bytes": column(lambda r: r.metrics.file_bytes if r.generation else None),
            "ssim_to_prev": [None if v is None else round(v, 6) for v in ssim_prev],
            "ssim_native": column(_picker(detail_rows, "ssim_native")),
            "detail_kept": column(_picker(detail_rows, "detail_kept")),
            "frame_kept": column(_picker(detail_rows, "frame_kept")),
            "place_prob": column(_picker(place_rows, "prob")),
            "place_rank": column(_picker(place_rows, "rank")),
        }
        # settled: the pass from which no later pass changes the picture (see settled_at)
        settled = settled_at(series["ssim_to_prev"])
        photo["journeys"][variant] = {
            "chain_id": chain_id,
            "generations": last,
            "settled_at": settled,
            "passes": shown,
            "series": series,
        }

    photos = {k: v for k, v in photos.items() if v["journeys"]}
    if not photos:
        shutil.rmtree(staging)
        raise ValueError(
            f"Nothing to export for {experiment}: no public photograph has a finished chain"
            + (f" among the variants {variants}" if variants else "")
            + "."
        )
    if variants is not None:  # the order that was asked for
        for photo in photos.values():
            photo["journeys"] = {
                v: photo["journeys"][v] for v in variants if v in photo["journeys"]
            }
    total_mb = sum(written.values()) / 1_000_000
    if total_mb > max_mb:
        shutil.rmtree(staging)
        raise ValueError(
            f"The pictures come to {total_mb:.1f} MB, over the limit of {max_mb} MB. "
            "Export fewer passes or fewer variants, or raise --max-mb."
        )

    site = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "experiment": experiment,
        "passes": wanted,
        "photos": [photos[k] for k in sorted(photos)],
        "made_with": made_with,
    }
    final = out / "img"
    if final.exists():
        shutil.rmtree(final)  # pictures that are no longer on the page are not left behind
    staging.rename(final)
    tmp = out / "site.json.tmp"
    tmp.write_text(json.dumps(site, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(out / "site.json")
    return {
        "out": str(out),
        "experiment": experiment,
        "photos": len(photos),
        "pictures": len(written),
        "mb": round(total_mb, 2),
    }
