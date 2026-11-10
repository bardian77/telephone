"""What the dashboard reads and decides: photographs, experiments, estimates and results.

No web framework in here. The server (server.py) is a thin layer over these functions and the
job manager (jobs.py), so they can be tested and reused without HTTP.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

from .. import paths
from ..config import get_settings
from ..experiments import MOCK_SUFFIX, Experiment, load_all, mockify
from ..ledger import Ledger
from ..models import ChainConfig, GenerationRecord, StationConfig
from ..render import image_of, type_of, variant_of
from .reading import (
    chain_reading,
    describe_station,
    drift_band,
    drift_position,
    experiment_findings,
    photo_label,
    variant_label,
)

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")
MAX_GENERATIONS = 40

# Plain-language names for the experiments that ship with the project. An experiment file that
# is not listed here still works: the dashboard falls back to its own title and question.
EXPERIMENT_PLAIN: dict[str, dict[str, str]] = {
    "exp00_smoke": {
        "name": "Practice run",
        "plain": "Sends five made-up test images round the whole loop with stand-in models. "
        "Nothing in it is real. Use it to see what a run looks like and to check that "
        "everything works.",
    },
    "exp01_compression": {
        "name": "Upload it again and again",
        "plain": "Each photograph is uploaded 20 times in a row, four different ways. There is "
        "no AI in this one. It is the baseline: how much damage does plain compression do?",
    },
    "exp02_caption_length": {
        "name": "Short description or long",
        "plain": "A Reader describes the photograph and a Painter redraws it from the words, "
        "12 times round. Does a 150-word description keep more of the photograph alive than "
        "a 20-word one?",
    },
    "exp03_system_swap": {
        "name": "Swap the models",
        "plain": "The same loop with a different Reader and a different Painter. Does the "
        "drift come from one particular model, or from describing and redrawing as such?",
    },
    "exp04_photo_types": {
        "name": "Five kinds of photograph",
        "plain": "The same loop on a portrait, a street scene, a landscape, a picture with "
        "text and an abstract one, three times each. Which facts die first for which kind?",
    },
    "exp05_mixed_chains": {
        "name": "Compression and AI together",
        "plain": "Upload steps and AI steps in different orders. Which of the two does the damage?",
    },
    "exp06_physical": {
        "name": "Photographing a screen",
        "plain": "Each generation is a phone photograph of a screen showing the one before. "
        "You take those photographs yourself, so this experiment cannot be started from here.",
    },
}


class RunRefused(Exception):
    """A run that must not start, with a sentence the interface can show as it is."""


class NotFound(Exception):
    pass


# -- photographs ----------------------------------------------------------------------------


def _ledger() -> Ledger | None:
    s = get_settings()
    return Ledger(s.ledger_path) if s.ledger_path.exists() else None


def originals() -> list[Path]:
    """The photographs in data/originals/. The private sub-folder is never searched."""
    folder = get_settings().originals_dir
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.glob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTS)


def find_original(stem: str) -> Path:
    for p in originals():
        if p.stem == stem:
            return p
    raise NotFound(f"No photograph named {stem}")


def photos(chains: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Every public original, with the real chain in which it drifted furthest (if any)."""
    furthest: dict[str, dict[str, Any]] = {}
    counts: dict[str, int] = {}
    for c in chains or []:
        if c["reading"]["simulation"]:
            continue
        counts[c["photo"]] = counts.get(c["photo"], 0) + 1
        d = c["reading"]["drift"]
        if d is None:
            continue
        best = furthest.get(c["photo"])
        if best is None or d > best["drift"]:
            furthest[c["photo"]] = {
                "key": c["key"],
                "experiment": c["experiment_id"],
                "variant_label": c["variant_label"],
                "drift": d,
                "position": drift_position(d),
                "band": drift_band(d),
                "trips": c["reading"]["trips"],
            }
    out = []
    for p in originals():
        with Image.open(p) as img:
            w, h = img.size
        out.append(
            {
                "stem": p.stem,
                **photo_label(p.stem),
                "width": w,
                "height": h,
                "image": f"/api/image/photo/{p.stem}",
                "chains": counts.get(p.stem, 0),
                "furthest": furthest.get(p.stem),
            }
        )
    return out


def resized_jpeg(src: Path, width: int | None, cache_key: str) -> bytes:
    """The image at `src`, long edge at most `width`, as JPEG bytes. Cached on disk.

    Previews are re-encoded at high quality so a page of them loads quickly. They are previews:
    the interface links to the real file for anyone who wants to look at actual pixels.
    """
    width = max(64, min(int(width or 1600), 2400))
    cache = get_settings().cache_dir / "dashboard" / f"{cache_key}_{width}.jpg"
    if cache.exists():
        return cache.read_bytes()
    with Image.open(src) as img:
        img = img.convert("RGB")
        img.thumbnail((width, width), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=92, subsampling=0)
    data = buf.getvalue()
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_bytes(data)
    return data


# -- experiments: what can run, and what it would cost --------------------------------------


def _kinds(exp: Experiment) -> set[str]:
    return {st.get("kind") for v in exp.variants for st in v["stations"]}


def _declares_only_mock(exp: Experiment) -> bool:
    model = [
        st
        for v in exp.variants
        for st in v["stations"]
        if st.get("kind") in ("caption", "regenerate")
    ]
    return bool(model) and all(st.get("provider") == "mock" for st in model)


def experiment_card(exp: Experiment, doctor_info: dict[str, Any]) -> dict[str, Any]:
    """One experiment as the Run screen shows it: plain words, and the ways it can run now."""
    kinds = _kinds(exp)
    has_models = bool(kinds & {"caption", "regenerate"})
    missing = doctor_info.get("missing_keys", [])
    modes: list[str] = []
    blocked = ""
    if "physical" in kinds:
        blocked = (
            "This one needs phone photographs of a screen, which you take yourself. "
            "The README explains how to run it from the terminal."
        )
    elif _declares_only_mock(exp):
        modes = ["simulation"]
    else:
        if not missing:
            modes.append("real")
        if not has_models:
            modes.append("free")
        else:
            modes.append("simulation")
    plain = EXPERIMENT_PLAIN.get(exp.id, {})
    return {
        "id": exp.id,
        "name": plain.get("name") or exp.title,
        "plain": plain.get("plain") or exp.description.strip(),
        "title": exp.title,
        "question": exp.question,
        "generations": exp.generations,
        "repeats": exp.repeats,
        "images": doctor_info.get("images", 0),
        "uses_fixtures": "fixtures" in exp.images,
        "has_models": has_models,
        "has_survival_form": bool(exp.extractor),
        "variants": [
            {
                "name": v["name"],
                "label": variant_label(v["name"]),
                "notes": v.get("notes"),
                "stations": [describe_station(st) for st in v["stations"]],
            }
            for v in exp.variants
        ],
        "modes": modes,
        "missing_keys": missing,
        "blocked": blocked,
        "references": exp.references,
    }


@dataclass
class RunPlan:
    experiment: Experiment
    mode: str
    chains: list[ChainConfig]
    extractor: StationConfig | None
    clip: bool
    lpips: bool
    calls: int
    estimate_usd: float

    @property
    def result_experiment(self) -> str:
        return self.chains[0].experiment_id

    @property
    def generations(self) -> int:
        return sum(c.generations for c in self.chains)


def plan_run(
    experiment: str,
    mode: str,
    photos: list[str] | None = None,
    variants: list[str] | None = None,
    generations: int | None = None,
    clip: bool = True,
) -> RunPlan:
    """Turn a request from the interface into chains and a cost estimate. Runs nothing."""
    from ..chain import ChainRunner, RunnerOptions
    from ..doctor import collect

    exps = load_all()
    if experiment not in exps:
        raise NotFound(f"No experiment called {experiment}")
    exp = exps[experiment]
    card = experiment_card(exp, collect()["experiments"].get(exp.id, {}))
    if card["blocked"]:
        raise RunRefused(card["blocked"])
    if mode not in ("real", "free", "simulation"):
        raise RunRefused(f"Unknown way to run: {mode}")
    if mode not in card["modes"]:
        if mode == "real":
            keys = ", ".join(card["missing_keys"])
            raise RunRefused(
                f"This run needs {keys}, which is not set. Add the key to the .env file in the "
                "project folder, or run it as a simulation."
            )
        raise RunRefused(f"{card['name']} cannot run as “{mode}”.")

    if card["uses_fixtures"] and not exp.resolve_images():
        from ..fixtures import make_all

        make_all(get_settings().fixtures_dir)
    images = exp.resolve_images()
    if photos:
        wanted = set(photos)
        images = [p for p in images if p.stem in wanted]
    if not images:
        raise RunRefused(
            "There are no photographs to run on. Put your own in data/originals/ "
            "(see the README in that folder for how to name them)."
        )
    if generations is not None and not 1 <= generations <= MAX_GENERATIONS:
        raise RunRefused(f"Choose between 1 and {MAX_GENERATIONS} generations.")

    chains = exp.chains(images=images, generations=generations)
    extractor = exp.extractor_config()
    if mode == "free":
        extractor = None
    elif mode == "simulation" and not _declares_only_mock(exp):
        # an experiment that already names the stand-ins everywhere runs as it is written
        chains = [mockify(c) for c in chains]
        if extractor is not None:
            extractor = StationConfig(kind="extract", provider="mock")
    if variants:
        chains = [c for c in chains if variant_of(c.chain_id) in set(variants)]
    if not chains:
        raise RunRefused("Nothing is selected to run. Tick at least one version of the loop.")

    use_clip = clip and exp.metrics.get("clip", True)
    use_lpips = use_clip and bool(exp.metrics.get("lpips", False))
    probe = ChainRunner(options=RunnerOptions(extractor=extractor))
    calls, cost = 0, 0.0
    for c in chains:
        n, usd = probe.estimate(c)
        calls, cost = calls + n, cost + usd
    if probe.ledger is not None:
        probe.ledger.close()
    return RunPlan(exp, mode, chains, extractor, use_clip, use_lpips, calls, round(cost, 4))


def check_budget(estimate_usd: float, confirm_usd: float | None, remaining: float) -> None:
    """A paid run starts only when it fits the budget and its estimate has been confirmed."""
    if estimate_usd <= 0:
        return
    if estimate_usd > remaining:
        raise RunRefused(
            f"This run is estimated at ${estimate_usd:.2f}, which is more than the "
            f"${remaining:.2f} left in the budget. Choose fewer photographs or generations."
        )
    if confirm_usd is None or abs(confirm_usd - estimate_usd) > 0.005:
        raise RunRefused(
            f"This run is estimated to cost ${estimate_usd:.2f}. Please confirm that amount "
            "before it starts."
        )


def estimate(plan: RunPlan) -> dict[str, Any]:
    from ..cost import get_tracker

    t = get_tracker()
    remaining = t.remaining()
    blocked = ""
    if plan.estimate_usd > remaining:
        blocked = (
            f"Estimated at ${plan.estimate_usd:.2f}, which is more than the ${remaining:.2f} "
            "left in the budget. Choose fewer photographs or generations."
        )
    return {
        "experiment": plan.experiment.id,
        "mode": plan.mode,
        "chains": len(plan.chains),
        "generations": plan.generations,
        "paid_calls": plan.calls if plan.estimate_usd > 0 else 0,
        "estimate_usd": plan.estimate_usd,
        "remaining_usd": round(remaining, 4),
        "needs_confirmation": plan.estimate_usd > 0,
        "blocked": blocked,
        "result_experiment": plan.result_experiment,
    }


# -- results --------------------------------------------------------------------------------


def chain_key(chain_id: str, repeat: int) -> str:
    return f"{chain_id}__r{repeat}"


def split_key(key: str) -> tuple[str, int]:
    chain_id, sep, rep = key.rpartition("__r")
    if not sep or not rep.isdigit():
        raise NotFound(f"No chain called {key}")
    return chain_id, int(rep)


def _image_url(key: str, rec: GenerationRecord) -> str | None:
    if rec.error is not None or not rec.output_path:
        return None
    if not paths.resolve(rec.output_path).exists():
        return None
    return f"/api/image/chain/{key}/{rec.generation}?v={rec.output_sha[:10]}"


def chain_summary(recs: list[GenerationRecord]) -> dict[str, Any]:
    recs = sorted(recs, key=lambda r: r.generation)
    first = recs[0]
    ok = [r for r in recs if r.error is None]
    last = ok[-1]
    key = chain_key(first.chain_id, first.repeat)
    stem = image_of(first.chain_id)
    variant = variant_of(first.chain_id)
    return {
        "key": key,
        "chain_id": first.chain_id,
        "experiment_id": first.experiment_id,
        "repeat": first.repeat,
        "photo": stem,
        "photo_label": photo_label(stem),
        "type": type_of(first.chain_id),
        "variant": variant,
        "variant_label": variant_label(variant),
        "station_sequence": first.station_sequence,
        "last_generation": last.generation,
        "errors": sum(1 for r in recs if r.error is not None),
        "images_available": _image_url(key, first) is not None,
        "image_first": _image_url(key, first),
        "image_last": _image_url(key, last),
        "drift": [r.metrics.clip_dist_to_g0 for r in ok],
        "cost_usd": round(sum(r.cost_usd for r in recs), 4),
        "reading": chain_reading(recs),
    }


def _grouped(records: list[GenerationRecord]) -> list[list[GenerationRecord]]:
    by: dict[tuple[str, int], list[GenerationRecord]] = {}
    for r in records:
        by.setdefault((r.chain_id, r.repeat), []).append(r)
    return [by[k] for k in sorted(by)]


def _private_stems() -> set[str]:
    from ..export import _private_stems as stems

    return stems()


def all_chain_summaries() -> list[dict[str, Any]]:
    led = _ledger()
    if led is None:
        return []
    try:
        private = _private_stems()
        return [
            chain_summary(g) for g in _grouped(led.all()) if image_of(g[0].chain_id) not in private
        ]
    finally:
        led.close()


def _base_experiment(experiment_id: str) -> str:
    return experiment_id.removesuffix(MOCK_SUFFIX)


def _experiment_meta(experiment_id: str) -> dict[str, Any]:
    base = _base_experiment(experiment_id)
    exps = load_all()
    plain = EXPERIMENT_PLAIN.get(base, {})
    exp = exps.get(base)
    return {
        "id": experiment_id,
        "base": base,
        "name": plain.get("name") or (exp.title if exp else experiment_id),
        "plain": plain.get("plain") or (exp.description.strip() if exp else ""),
        "question": exp.question if exp else "",
        "defined": exp is not None,
    }


def results_index(chains: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by: dict[str, list[dict[str, Any]]] = {}
    for c in chains:
        by.setdefault(c["experiment_id"], []).append(c)
    out = []
    for eid, group in sorted(by.items()):
        out.append(
            {
                **_experiment_meta(eid),
                "simulation": any(c["reading"]["simulation"] for c in group),
                "chains": len(group),
                "photos": len({c["photo"] for c in group}),
                "variants": len({c["variant"] for c in group}),
                "generations": sum(c["last_generation"] + 1 for c in group),
                "errors": sum(c["errors"] for c in group),
                "sample": next((c["image_last"] for c in group if c["image_last"]), None),
            }
        )
    return out


def experiment_results(experiment_id: str) -> dict[str, Any]:
    led = _ledger()
    records = led.experiment(experiment_id) if led is not None else []
    if led is not None:
        led.close()
    private = _private_stems()
    chains = [chain_summary(g) for g in _grouped(records) if image_of(g[0].chain_id) not in private]
    if not chains:
        raise NotFound(f"No results for {experiment_id}")
    meta = _experiment_meta(experiment_id)
    exp = load_all().get(meta["base"])
    order = [v["name"] for v in exp.variants] if exp else []
    names = sorted(
        {c["variant"] for c in chains}, key=lambda n: (order.index(n) if n in order else 99, n)
    )
    variants = []
    for name in names:
        cfg = next((v for v in (exp.variants if exp else []) if v["name"] == name), None)
        variants.append(
            {
                "name": name,
                "label": variant_label(name),
                "notes": cfg.get("notes") if cfg else None,
                "stations": [describe_station(st) for st in cfg["stations"]] if cfg else [],
            }
        )
    photo_stems = sorted({c["photo"] for c in chains})
    figures_dir = get_settings().figures_dir / experiment_id
    figures = (
        [f"/api/figures/{experiment_id}/{p.name}" for p in sorted(figures_dir.glob("*.png"))]
        if figures_dir.is_dir()
        else []
    )
    return {
        **meta,
        "simulation": any(c["reading"]["simulation"] for c in chains),
        "variants": variants,
        "photos": [{"stem": s, **photo_label(s)} for s in photo_stems],
        "chains": chains,
        "findings": experiment_findings(chains),
        "images_available": any(c["images_available"] for c in chains),
        "figures": figures,
    }


def chain_detail(key: str) -> dict[str, Any]:
    chain_id, repeat = split_key(key)
    led = _ledger()
    recs = led.chain(chain_id, repeat) if led is not None else []
    if led is not None:
        led.close()
    if not recs or image_of(chain_id) in _private_stems():
        raise NotFound(f"No chain called {key}")
    summary = chain_summary(recs)
    meta = _experiment_meta(summary["experiment_id"])
    exp = load_all().get(meta["base"])
    cfg = next((v for v in (exp.variants if exp else []) if v["name"] == summary["variant"]), None)
    if cfg:
        stations = [describe_station(st) for st in cfg["stations"]]
    else:
        later = next((r for r in recs if r.generation > 0 and r.stations), None)
        stations = [
            describe_station(s.model_dump())
            for s in (later.stations if later else [])
            if s.kind != "extract"
        ]
    used = {}
    for r in recs:
        for s in r.stations:
            if s.provider and s.kind not in used:
                used[s.kind] = {"provider": s.provider, "model": s.model}
    gens = []
    for r in recs:
        gens.append(
            {
                "generation": r.generation,
                "image": _image_url(key, r),
                "file": f"/api/image/chain/{key}/{r.generation}?raw=1"
                if _image_url(key, r)
                else None,
                "caption": r.caption,
                "metrics": r.metrics.model_dump(),
                "position": drift_position(r.metrics.clip_dist_to_g0),
                "band": drift_band(r.metrics.clip_dist_to_g0) if r.generation else None,
                "attributes": r.attributes.model_dump() if r.attributes else None,
                "survival": r.survival.model_dump() if r.survival else None,
                "error": r.error,
                "cost_usd": r.cost_usd,
                "created_at": r.created_at,
            }
        )
    return {
        **summary,
        "experiment": meta,
        "stations": stations,
        "models": used,
        "seed": recs[0].seed,
        "config_sha": recs[0].config_sha,
        "notes": cfg.get("notes") if cfg else None,
        "generations": gens,
    }


def chain_image_path(key: str, generation: int) -> tuple[Path, str]:
    chain_id, repeat = split_key(key)
    led = _ledger()
    rec = led.get(chain_id, generation, repeat) if led is not None else None
    if led is not None:
        led.close()
    if rec is None or rec.error is not None or image_of(chain_id) in _private_stems():
        raise NotFound("No such generation")
    src = paths.resolve(rec.output_path)
    if not rec.output_path or not src.exists():
        raise NotFound("The picture for this generation is not on this computer")
    return src, rec.output_sha[:16]


# -- saved snapshots ------------------------------------------------------------------------


def saved_results() -> list[dict[str, Any]]:
    s = get_settings()
    if not s.results_dir.is_dir():
        return []
    led = _ledger()
    loaded = {row["experiment_id"] for row in led.experiments()} if led is not None else set()
    if led is not None:
        led.close()
    out = []
    for p in sorted(s.results_dir.glob("*.jsonl")):
        with p.open(encoding="utf-8") as f:
            rows = sum(1 for line in f if line.strip())
        out.append({"experiment": p.stem, "rows": rows, "loaded": p.stem in loaded})
    return out


def load_saved(experiment: str) -> int:
    s = get_settings()
    path = s.results_dir / f"{experiment}.jsonl"
    if "/" in experiment or "\\" in experiment or not path.is_file():
        raise NotFound(f"No saved results for {experiment}")
    led = Ledger(s.ledger_path)
    try:
        return led.import_jsonl(path)
    finally:
        led.close()


def save_snapshot(experiment: str) -> dict[str, Any]:
    if experiment.endswith(MOCK_SUFFIX):
        raise RunRefused("Simulations are not saved as results.")
    s = get_settings()
    led = _ledger()
    if led is None or experiment not in {r["experiment_id"] for r in led.experiments()}:
        raise NotFound(f"No results for {experiment}")
    try:
        path = s.results_dir / f"{experiment}.jsonl"
        n = led.save_results(experiment, path)
    finally:
        led.close()
    return {"rows": n, "path": paths.to_stored(path)}


def make_figures(experiment: str) -> list[str]:
    from ..render import render_all

    s = get_settings()
    led = _ledger()
    known = {r["experiment_id"] for r in led.experiments()} if led is not None else set()
    if led is not None:
        led.close()
    if experiment not in known:
        raise NotFound(f"No results for {experiment}")
    written = render_all(experiment, s.figures_dir)
    return [paths.to_stored(p) for p in written]


def figure_path(experiment: str, name: str) -> Path:
    folder = (get_settings().figures_dir / experiment).resolve()
    p = (folder / name).resolve()
    if p.parent != folder or p.suffix.lower() != ".png" or not p.is_file():
        raise NotFound("No such figure")
    return p
