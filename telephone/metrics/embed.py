"""Image embeddings for drift.

CLIP ViT-B/32 on CPU is the headline measure. It needs torch + open_clip and a one-off weight
download (about 350 MB). When that is unavailable the pipeline records None for CLIP and
keeps going; the histogram distance below needs nothing and is always recorded, so every chain
has at least one drift curve. Both are proxies and are validated against hand labels.
"""

from __future__ import annotations

import os
import threading

import numpy as np

from ..imageio import from_bytes


class MetricsUnavailable(RuntimeError):
    pass


def cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
    a = a / (np.linalg.norm(a) + 1e-12)
    b = b / (np.linalg.norm(b) + 1e-12)
    return float(1.0 - np.dot(a, b))


def hsv_histogram(image: bytes, bins: tuple[int, int, int] = (16, 8, 8)) -> np.ndarray:
    img = from_bytes(image).convert("HSV").resize((256, 256))
    arr = np.asarray(img, dtype=np.float32).reshape(-1, 3)
    h, _ = np.histogramdd(arr, bins=bins, range=((0, 256), (0, 256), (0, 256)))
    h = h.flatten()
    return h / (h.sum() + 1e-12)


def histogram_distance(image_a: bytes, image_b: bytes) -> float:
    """Hellinger distance between HSV histograms, 0 identical to 1 disjoint. Cheap, dependency free."""
    pa, pb = hsv_histogram(image_a), hsv_histogram(image_b)
    return float(np.sqrt(max(0.0, 1.0 - np.sum(np.sqrt(pa * pb)))))


class ClipEmbedder:
    """Lazy CLIP wrapper. Construct once, call `embed` many times."""

    _instance: ClipEmbedder | None = None
    _lock = threading.Lock()

    def __init__(self, model_name: str | None = None, pretrained: str | None = None):
        # the OpenAI weights were trained with QuickGELU; the plain ViT-B-32 config silently
        # mismatches them (open_clip warns), so the quickgelu variant is the correct default
        self.model_name = model_name or os.environ.get("TELEPHONE_CLIP_MODEL", "ViT-B-32-quickgelu")
        self.pretrained = pretrained or os.environ.get("TELEPHONE_CLIP_PRETRAINED", "openai")
        try:
            import open_clip
            import torch
        except ImportError as e:
            raise MetricsUnavailable(
                "CLIP needs torch and open_clip_torch: pip install 'telephone[metrics]'"
            ) from e
        torch.set_num_threads(max(1, (os.cpu_count() or 2) // 2))
        try:
            model, _, preprocess = open_clip.create_model_and_transforms(
                self.model_name, pretrained=self.pretrained
            )
        except Exception as e:  # noqa: BLE001  (network, missing weights, bad name)
            raise MetricsUnavailable(
                f"Could not load CLIP {self.model_name}/{self.pretrained}: {e}"
            ) from e
        self.model = model.eval()
        self.preprocess = preprocess
        self.torch = torch

    @classmethod
    def shared(cls) -> ClipEmbedder:
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def embed(self, image: bytes) -> np.ndarray:
        img = from_bytes(image)
        with self.torch.no_grad():
            x = self.preprocess(img).unsqueeze(0)
            feats = self.model.encode_image(x)
            feats = feats / feats.norm(dim=-1, keepdim=True)
        return feats[0].cpu().numpy().astype(np.float32)

    def embed_text(self, text: str) -> np.ndarray:
        import open_clip

        tok = open_clip.get_tokenizer(self.model_name)
        with self.torch.no_grad():
            feats = self.model.encode_text(tok([text]))
            feats = feats / feats.norm(dim=-1, keepdim=True)
        return feats[0].cpu().numpy().astype(np.float32)
