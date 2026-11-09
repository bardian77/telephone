"""The one place that says which provider and model is used when nothing else does.

Experiment files may name a model explicitly; everything that does not (settings, the CLI, the
provider constructors, the cost estimates, the chain fingerprint) comes here. Prices for these
ids live in telephone/cost.py.
"""

from __future__ import annotations

DEFAULT_CAPTIONER = "anthropic"  # also the default attribute extractor
DEFAULT_GENERATOR = "gemini"

VISION_DEFAULT_MODELS: dict[str, str] = {
    "anthropic": "claude-sonnet-5-5",
    "gemini": "gemini-2.5-flash",
    "openai": "gpt-5-mini",
    "mock": "mock-vision",
}
IMAGE_DEFAULT_MODELS: dict[str, str] = {
    "gemini": "gemini-2.5-flash-image",
    "cloudflare": "@cf/black-forest-labs/flux-1-schnell",
    "replicate": "black-forest-labs/flux-schnell",
    "openai": "gpt-image-1-mini",
    "mock": "mock-gen",
}


def vision_model(provider: str, model: str | None = None) -> str:
    """The model a vision (caption / extract) call will use for this provider."""
    return model or VISION_DEFAULT_MODELS.get(provider, provider)


def image_model(provider: str, model: str | None = None) -> str:
    """The model an image-generation call will use for this provider."""
    return model or IMAGE_DEFAULT_MODELS.get(provider, provider)
