"""Ledger -> static JSON + thumbnails for the website.

Layout under the output folder:
  index.json                 experiments, chains, totals
  chains/<key>.json          one file per chain (all generations, captions, metrics, survival)
  img/<key>/<gen>.jpg        thumbnails (long edge `thumb_size`)
  img/<key>/<gen>_full.jpg   viewing size (long edge 1280)
Images listed in data/originals/private.txt (one stem per line) are excluded unless asked.
"""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PIL import Image

from .config import get_settings
from .experiments import load_all
from .imageio import fit_within
from .ledger import Ledger
from .metrics.survival import first_failure
from .models import GenerationRecord
from .render import image_of, summarise, type_of, variant_of


def chain_key(chain_id: str, repeat: int) -> str:
    return f"{chain_id}__r{repeat}".replace("/", "_")


def _private_stems() -> set[str]:
    p = get_settings().originals_dir / "private.txt"
    if not p.exists():
        return set()
    return {
        line.strip()
        for line in p.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    }


def _write_images(
    rec: GenerationRecord, folder: Path, thumb_size: int, full_size: int
) -> tuple[str | None, str | None]:
    src = Path(rec.output_path)
    if not src.exists():
        return None, None
    folder.mkdir(parents=True, exist_ok=True)
    img = Image.open(src).convert("RGB")
    t = folder / f"{rec.generation:03d}.jpg"
    f = folder / f"{rec.generation:03d}_full.jpg"
    if not t.exists():
        fit_within(img, thumb_size).save(t, format="JPEG", quality=82, optimize=True)
    if not f.exists():
        fit_within(img, full_size).save(f, format="JPEG", quality=88, optimize=True)
    return t.name, f.name


def _station_view(rec: GenerationRecord) -> list[dict[str, Any]]:
    return [
        {
            "kind": s.kind,
            "provider": s.provider,
            "model": s.model,
            "model_version": s.model_version,
            "params": s.params,
            "seed": s.seed,
            "cached": s.cached,
            "error": s.error,
            "latency_ms": s.usage.latency_ms,
            "cost_usd": s.usage.cost_usd,
            "list_price_usd": s.usage.list_price_usd,
            "tokens": {"input": s.usage.input_tokens, "output": s.usage.output_tokens},
        }
        for s in rec.stations
    ]


def export_chain(
    recs: list[GenerationRecord],
    out: Path,
    thumb_size: int,
    full_size: int,
    experiment_meta: dict | None,
) -> dict[str, Any]:
    recs = sorted(recs, key=lambda r: r.generation)
    first = recs[0]
    key = chain_key(first.chain_id, first.repeat)
    img_dir = out / "img" / key
    gens = []
    for r in recs:
        thumb, full = _write_images(r, img_dir, thumb_size, full_size)
        gens.append(
            {
                "generation": r.generation,
                "thumb": f"img/{key}/{thumb}" if thumb else None,
                "full": f"img/{key}/{full}" if full else None,
                "caption": r.caption,
                "metrics": r.metrics.model_dump(),
                "attributes": r.attributes.model_dump() if r.attributes else None,
                "survival": r.survival.model_dump() if r.survival else None,
                "stations": _station_view(r),
                "cost_usd": r.cost_usd,
                "list_price_usd": r.list_price_usd,
                "latency_ms": r.latency_ms,
                "error": r.error,
                "created_at": r.created_at,
            }
        )
    variant = variant_of(first.chain_id)
    stations_cfg = None
    if experiment_meta:
        for v in experiment_meta.get("variants", []):
            if v["name"] == variant:
                stations_cfg = v["stations"]
    doc = {
        "key": key,
        "chain_id": first.chain_id,
        "experiment_id": first.experiment_id,
        "variant": variant,
        "image": image_of(first.chain_id),
        "type": type_of(first.chain_id),
        "repeat": first.repeat,
        "seed": first.seed,
        "station_sequence": first.station_sequence,
        "stations": stations_cfg,
        "generations": gens,
        "first_failure": first_failure([r.survival for r in recs]),
        "cost_usd": round(sum(r.cost_usd for r in recs), 5),
        "list_price_usd": round(sum(r.list_price_usd for r in recs), 5),
        "errors": [{"generation": r.generation, "error": r.error} for r in recs if r.error],
        "last_generation": max(r.generation for r in recs if r.error is None),
    }
    (out / "chains").mkdir(parents=True, exist_ok=True)
    (out / "chains" / f"{key}.json").write_text(json.dumps(doc, indent=None))
    last = next((g for g in reversed(gens) if g["error"] is None), gens[0])
    return {
        "key": key,
        "chain_id": first.chain_id,
        "experiment_id": first.experiment_id,
        "variant": variant,
        "image": doc["image"],
        "type": doc["type"],
        "repeat": first.repeat,
        "station_sequence": first.station_sequence,
        "generations": len(gens),
        "last_generation": doc["last_generation"],
        "thumb0": gens[0]["thumb"],
        "thumb_last": last["thumb"],
        "final_clip": last["metrics"].get("clip_dist_to_g0"),
        "final_hist": last["metrics"].get("hist_dist_to_g0"),
        "final_survival": (last["survival"]["alive_count"] / last["survival"]["total"])
        if last["survival"]
        else None,
        "cost_usd": doc["cost_usd"],
        "errors": len(doc["errors"]),
    }


def export_all(
    out: Path,
    thumb_size: int = 512,
    full_size: int = 1280,
    include_private: bool = False,
    experiments: list[str] | None = None,
    clean: bool = False,
) -> dict[str, Any]:
    s = get_settings()
    ledger = Ledger(s.ledger_path, s.ledger_jsonl)
    defs = load_all()
    private = set() if include_private else _private_stems()
    out = Path(out)
    if clean and out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    exp_rows = []
    all_chains = []
    for row in ledger.experiments():
        eid = row["experiment_id"]
        if experiments and eid not in experiments:
            continue
        records = ledger.experiment(eid)
        by_chain: dict[tuple[str, int], list[GenerationRecord]] = {}
        for r in records:
            by_chain.setdefault((r.chain_id, r.repeat), []).append(r)
        meta = defs[eid].summary() if eid in defs else {"id": eid, "title": eid, "variants": []}
        chains = []
        kept_records = []
        for (cid, _rep), recs in sorted(by_chain.items()):
            if image_of(cid) in private:
                continue
            chains.append(export_chain(recs, out, thumb_size, full_size, meta))
            kept_records.extend(recs)
        exp_rows.append(
            {
                **meta,
                "chains": chains,
                "summary": summarise(kept_records),
                "cost_usd": round(sum(c["cost_usd"] for c in chains), 4),
            }
        )
        all_chains.extend(chains)
    paid, listp = ledger.total_cost()
    index = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "experiments": exp_rows,
        "totals": {
            "chains": len(all_chains),
            "generations": sum(c["generations"] for c in all_chains),
            "paid_usd": round(paid, 4),
            "list_price_usd": round(listp, 4),
        },
        "images": sorted({c["image"] for c in all_chains}),
        "types": sorted({c["type"] for c in all_chains}),
    }
    (out / "index.json").write_text(json.dumps(index, indent=None))
    return {"out": str(out), **index["totals"], "experiments": [e["id"] for e in exp_rows]}
