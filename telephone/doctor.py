"""`telephone doctor`: what is installed, which keys are set, where the photos are, what can run.

Everything here is read-only and offline. Keys are reported as set or not set, never shown.
"""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path
from typing import Any

from . import paths
from .config import get_settings
from .experiments import load_all

KEYS = [
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "CLOUDFLARE_ACCOUNT_ID",
    "CLOUDFLARE_API_TOKEN",
    "REPLICATE_API_TOKEN",
    "OPENAI_API_KEY",
]
KEYS_FOR_PROVIDER: dict[str, list[str]] = {
    "anthropic": ["ANTHROPIC_API_KEY"],
    "gemini": ["GEMINI_API_KEY"],
    "cloudflare": ["CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN"],
    "replicate": ["REPLICATE_API_TOKEN"],
    "openai": ["OPENAI_API_KEY"],
    "mock": [],
}
PACKAGES: dict[str, str] = {
    "torch": "CLIP and LPIPS drift metrics",
    "open_clip": "CLIP drift metric",
    "lpips": "LPIPS metric",
    "skimage": "windowed SSIM (without it a coarse global SSIM is used)",
    "cv2": "face count",
    "pytesseract": "OCR word count (also needs the tesseract binary)",
    "google.genai": "Gemini provider",
    "anthropic": "Anthropic provider",
    "fastapi": "the API",
    "pptx": "the deck builder",
}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def _installed(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ModuleNotFoundError, ValueError):
        return False


def _clip_weights_cached() -> bool:
    try:
        from huggingface_hub.constants import HF_HUB_CACHE

        hub = Path(HF_HUB_CACHE)
    except Exception:  # noqa: BLE001
        return False
    return any(hub.glob("models--timm--vit_base_patch32_clip_224.openai*"))


def _count_images(folder: Path, recursive: bool = False) -> int:
    if not folder.is_dir():
        return 0
    it = folder.rglob("*") if recursive else folder.glob("*")
    return sum(1 for p in it if p.is_file() and p.suffix.lower() in IMAGE_EXTS)


def collect() -> dict[str, Any]:
    s = get_settings()
    root = paths.project_root()
    keys = {k: bool(getattr(s, k.lower())) for k in KEYS}

    packages = {m: _installed(m) for m in PACKAGES}
    tesseract = shutil.which("tesseract") is not None

    ledger_info: dict[str, Any] = {"path": str(s.ledger_path), "exists": s.ledger_path.exists()}
    paid, listp = 0.0, 0.0
    if s.ledger_path.exists():
        from .ledger import Ledger

        led = Ledger(s.ledger_path)
        ledger_info["experiments"] = {
            row["experiment_id"]: {"chains": row["chains"], "generations": row["generations"]}
            for row in led.experiments()
        }
        paid, listp = led.total_spend()
        led.close()
    cap = s.telephone_spend_cap_usd
    spend = {
        "paid_usd": round(paid, 4),
        "list_price_usd": round(listp, 4),
        "cap_usd": cap,
        "remaining_usd": round(max(0.0, cap - paid), 4),
    }

    experiments: dict[str, Any] = {}
    for exp in load_all().values():
        needed: set[str] = set()
        extractor_only: set[str] = set()
        for variant in exp.variants:
            for st in variant["stations"]:
                kind = st.get("kind")
                if kind in ("caption", "extract"):
                    prov = st.get("provider") or s.default_captioner
                elif kind == "regenerate":
                    prov = st.get("provider") or s.default_generator
                else:
                    continue
                needed.update(KEYS_FOR_PROVIDER.get(prov, []))
        if exp.extractor:
            prov = exp.extractor.get("provider") or s.default_captioner
            extractor_only = set(KEYS_FOR_PROVIDER.get(prov, [])) - needed
            needed |= extractor_only
        missing = sorted(k for k in needed if not keys[k])
        n_images = len(exp.resolve_images())
        if not missing:
            status = "ready" if n_images else "ready once it has images"
        elif set(missing) <= extractor_only:
            status = (
                f"runs with --no-extract (the survival form needs {', '.join(missing)}); "
                "or with --mock"
            )
        else:
            status = f"needs {', '.join(missing)}; or runs with --mock (offline stand-ins)"
        experiments[exp.id] = {
            "title": exp.title,
            "images": n_images,
            "needs_keys": sorted(needed),
            "missing_keys": missing,
            "status": status,
        }

    return {
        "root": str(root),
        "cwd": str(Path.cwd()),
        "env_file": str(root / ".env"),
        "env_file_found": (root / ".env").exists(),
        "data_dir": str(s.telephone_data_dir),
        "keys": keys,
        "gemini_billing": "free tier, costed at 0" if s.gemini_free_tier else "list price",
        "spend": spend,
        "packages": packages,
        "tesseract_binary": tesseract,
        "clip_weights_cached": _clip_weights_cached(),
        "ssim": "windowed (scikit-image)" if packages["skimage"] else "global fallback",
        "photos": {
            "originals_dir": str(s.originals_dir),
            "originals": _count_images(s.originals_dir),
            "private": _count_images(s.private_dir, recursive=True),
            "fixtures": _count_images(s.fixtures_dir),
        },
        "ledger": ledger_info,
        "experiments": experiments,
    }


def render_text(d: dict[str, Any]) -> str:
    yes, no = "yes", "no"
    lines = [
        f"project root     {d['root']}",
        f"working folder   {d['cwd']}",
        f".env             {d['env_file']} ({'found' if d['env_file_found'] else 'not found'})",
        f"data folder      {d['data_dir']}",
        "",
        "keys (set in .env or the environment; values are never shown)",
    ]
    lines += [f"  {k:<22} {'set' if v else 'not set'}" for k, v in d["keys"].items()]
    sp = d["spend"]
    lines += [
        "",
        f"spend            ${sp['paid_usd']:.4f} of the ${sp['cap_usd']:.2f} cap, "
        f"${sp['remaining_usd']:.2f} left (list price ${sp['list_price_usd']:.4f})",
        f"gemini billing   {d['gemini_billing']}",
        "",
        "packages",
    ]
    for m, ok in d["packages"].items():
        lines.append(f"  {m:<14} {yes if ok else no:<4} {PACKAGES[m]}")
    lines += [
        f"  {'tesseract':<14} {yes if d['tesseract_binary'] else no:<4} OCR binary",
        f"  CLIP weights cached: {yes if d['clip_weights_cached'] else no}",
        f"  SSIM: {d['ssim']}",
        "",
        "photos",
        f"  originals  {d['photos']['originals']} in {d['photos']['originals_dir']}",
        f"  private    {d['photos']['private']} (processed on request, never exported)",
        f"  fixtures   {d['photos']['fixtures']} (synthetic, only exp00 uses them)",
        "",
        f"ledger           {d['ledger']['path']} "
        f"({'exists' if d['ledger']['exists'] else 'not created yet'})",
    ]
    for eid, info in d["ledger"].get("experiments", {}).items():
        lines.append(f"  {eid:<28} {info['chains']} chains, {info['generations']} generations")
    lines += ["", "experiments: what can run now"]
    for eid, info in d["experiments"].items():
        lines.append(f"  {eid:<28} images {info['images']:>2}   {info['status']}")
    return "\n".join(lines)
