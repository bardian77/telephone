"""Model ids live in one place: telephone/providers/defaults.py (prices in cost.py)."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MODEL_LITERALS = [
    "claude-sonnet-5-5",
    "gemini-2.5-flash-image",
    "gemini-2.5-flash",
    "@cf/black-forest-labs/flux-1-schnell",
    "black-forest-labs/flux-schnell",
    "gpt-5-mini",
    "gpt-image-1-mini",
    "mock-vision",
    "mock-gen",
]
ALLOWED = {
    "telephone/providers/defaults.py",  # the single source of truth
    "telephone/cost.py",  # the price table is keyed by model id
}


def test_model_ids_appear_only_in_defaults_and_price_table():
    offenders: list[str] = []
    for folder in ("telephone", "api", "analysis"):
        for py in (REPO / folder).rglob("*.py"):
            rel = py.relative_to(REPO).as_posix()
            if rel in ALLOWED:
                continue
            text = py.read_text()
            for lit in MODEL_LITERALS:
                if lit in text:
                    offenders.append(f"{rel}: {lit}")
    assert offenders == []


def test_defaults_are_used_everywhere():
    from telephone.config import get_settings
    from telephone.providers import defaults
    from telephone.providers.mock import MockImageGen, MockVision

    assert get_settings().default_captioner == defaults.DEFAULT_CAPTIONER
    assert get_settings().default_generator == defaults.DEFAULT_GENERATOR
    assert MockVision().model == defaults.VISION_DEFAULT_MODELS["mock"]
    assert MockImageGen().model == defaults.IMAGE_DEFAULT_MODELS["mock"]
    assert defaults.vision_model("anthropic") == defaults.VISION_DEFAULT_MODELS["anthropic"]
    assert defaults.vision_model("anthropic", "other") == "other"
    assert defaults.image_model("gemini") == defaults.IMAGE_DEFAULT_MODELS["gemini"]
