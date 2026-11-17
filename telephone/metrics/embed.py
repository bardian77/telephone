"""Image embeddings for drift.

CLIP ViT-B/32 on CPU is the headline measure. It needs torch + open_clip and a one-off weight
download (about 350 MB). When that is unavailable the pipeline records None for CLIP and
keeps going; the histogram distance below needs nothing and is always recorded, so every chain
has at least one drift curve. Both are proxies and are validated against hand labels.
"""

from __future__ import annotations

import os
import threading
import warnings

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


def describe_preprocessing(preprocess) -> str:
    """What a model does to a picture before the network sees it, read off the steps themselves.

    CLIP's standard preparation makes the picture's shorter side 224 px and then keeps the
    central 224 x 224 square, so the network never sees what lies outside that square. That
    comes out as "central square at 224 px". Steps that do not have this shape are "not
    known", so a result never claims a preparation that did not run.
    """
    steps = {type(step).__name__: step for step in getattr(preprocess, "transforms", [])}
    resize, crop = steps.get("Resize"), steps.get("CenterCrop")
    if resize is None or crop is None or not isinstance(resize.size, int):
        return "not known"
    if tuple(crop.size) != (resize.size, resize.size):
        return "not known"
    return f"central square at {resize.size} px"


class ClipEmbedder:
    """Lazy CLIP wrapper. Construct once, call `embed` many times.

    After loading it says what really ran, for the label written into results: `activation`
    (how the network was built), `library` (which open_clip built it) and `preprocessing`
    (what is done to a picture before the network sees it).
    """

    _instance: ClipEmbedder | None = None
    _lock = threading.Lock()

    def __init__(self, model_name: str | None = None, pretrained: str | None = None):
        self.model_name = model_name or os.environ.get("TELEPHONE_CLIP_MODEL", "ViT-B-32")
        self.pretrained = pretrained or os.environ.get("TELEPHONE_CLIP_PRETRAINED", "openai")
        try:
            import open_clip
            import torch
        except ImportError as e:
            raise MetricsUnavailable(
                "CLIP needs torch and open_clip_torch: pip install 'telephone[metrics]'"
            ) from e
        torch.set_num_threads(max(1, (os.cpu_count() or 2) // 2))
        # A network has to be built with the activation its weights were trained with. OpenAI's
        # weights were trained with one called QuickGELU. open_clip builds plain "ViT-B-32" with
        # GELU instead and only warns, and the mis-built network gives different numbers. So
        # QuickGELU is asked for whenever the weights call for it, and a mismatch that is still
        # there counts as a failure to load, not as a warning.
        weights = open_clip.get_pretrained_cfg(self.model_name, self.pretrained)
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings("error", message="QuickGELU mismatch")
                model, _, preprocess = open_clip.create_model_and_transforms(
                    self.model_name,
                    pretrained=self.pretrained,
                    force_quick_gelu=bool(weights.get("quick_gelu")),
                )
        except Exception as e:  # noqa: BLE001  (network, missing weights, bad name)
            raise MetricsUnavailable(
                f"Could not load CLIP {self.model_name}/{self.pretrained}: {e}"
            ) from e
        # Read off the network that was built, so result labels say what really ran.
        built_with = {type(m).__name__ for m in model.modules()}
        self.activation = "quickgelu" if "QuickGELU" in built_with else "gelu"
        self.library = f"open_clip-{getattr(open_clip, '__version__', 'unknown')}"
        self.preprocessing = describe_preprocessing(preprocess)
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
