"""Provider registry. Names are what experiment YAML files use."""

from __future__ import annotations

from .base import ImageGenProvider, ProviderRefusal, ProviderUnavailable, VisionProvider

VISION_DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-5-5",
    "gemini": "gemini-2.5-flash",
    "openai": "gpt-5-mini",
    "mock": "mock-vision",
}
IMAGE_DEFAULT_MODELS = {
    "gemini": "gemini-2.5-flash-image",
    "cloudflare": "@cf/black-forest-labs/flux-1-schnell",
    "replicate": "black-forest-labs/flux-schnell",
    "openai": "gpt-image-1-mini",
    "mock": "mock-gen",
}

_vision_cache: dict[tuple[str, str], VisionProvider] = {}
_image_cache: dict[tuple[str, str], ImageGenProvider] = {}


def get_vision_provider(name: str, model: str | None = None) -> VisionProvider:
    model = model or VISION_DEFAULT_MODELS.get(name) or name
    key = (name, model)
    if key in _vision_cache:
        return _vision_cache[key]
    if name == "anthropic":
        from .anthropic_vision import AnthropicVision

        p: VisionProvider = AnthropicVision(model=model)
    elif name == "gemini":
        from .gemini import GeminiVision

        p = GeminiVision(model=model)
    elif name == "openai":
        from .openai_provider import OpenAIVision

        p = OpenAIVision(model=model)
    elif name == "mock":
        from .mock import MockVision

        p = MockVision(model=model)
    else:
        raise ProviderUnavailable(
            f"Unknown vision provider '{name}'. Known: {sorted(VISION_DEFAULT_MODELS)}"
        )
    _vision_cache[key] = p
    return p


def get_image_provider(name: str, model: str | None = None) -> ImageGenProvider:
    model = model or IMAGE_DEFAULT_MODELS.get(name) or name
    key = (name, model)
    if key in _image_cache:
        return _image_cache[key]
    if name == "gemini":
        from .gemini import GeminiImageGen

        p: ImageGenProvider = GeminiImageGen(model=model)
    elif name == "cloudflare":
        from .cloudflare_gen import CloudflareFluxGen

        p = CloudflareFluxGen(model=model)
    elif name == "replicate":
        from .replicate_gen import ReplicateFluxGen

        p = ReplicateFluxGen(model=model)
    elif name == "openai":
        from .openai_provider import OpenAIImageGen

        p = OpenAIImageGen(model=model)
    elif name == "mock":
        from .mock import MockImageGen

        p = MockImageGen(model=model)
    else:
        raise ProviderUnavailable(
            f"Unknown image provider '{name}'. Known: {sorted(IMAGE_DEFAULT_MODELS)}"
        )
    _image_cache[key] = p
    return p


def clear_provider_cache() -> None:
    _vision_cache.clear()
    _image_cache.clear()


__all__ = [
    "ImageGenProvider",
    "ProviderRefusal",
    "ProviderUnavailable",
    "VisionProvider",
    "clear_provider_cache",
    "get_image_provider",
    "get_vision_provider",
]
