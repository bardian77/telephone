"""Metrics: drift (CLIP cosine distance, colour-histogram distance), structure (SSIM, LPIPS),
survival (attribute comparison) and machine readability (OCR, faces)."""

from .embed import ClipEmbedder, MetricsUnavailable, cosine_distance, histogram_distance
from .readability import face_count, ocr_stats
from .structural import lpips_distance, ssim_score
from .survival import compare_attributes, first_failure

__all__ = [
    "ClipEmbedder",
    "MetricsUnavailable",
    "compare_attributes",
    "cosine_distance",
    "face_count",
    "first_failure",
    "histogram_distance",
    "lpips_distance",
    "ocr_stats",
    "ssim_score",
]
