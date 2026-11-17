"""Metrics: drift (CLIP cosine distance, colour-histogram distance), structure (SSIM, LPIPS),
survival (attribute comparison), machine readability (OCR, faces) and place (whether CLIP still
picks the true place out of a line-up of candidates)."""

from .embed import ClipEmbedder, MetricsUnavailable, cosine_distance, histogram_distance
from .place import (
    PlaceEntry,
    calibrate_places,
    load_places,
    place_vector,
    score_ladder,
    score_lineup,
    score_place,
)
from .readability import face_count, ocr_stats
from .structural import lpips_distance, ssim_score
from .survival import compare_attributes, first_failure

__all__ = [
    "ClipEmbedder",
    "MetricsUnavailable",
    "PlaceEntry",
    "calibrate_places",
    "compare_attributes",
    "cosine_distance",
    "face_count",
    "first_failure",
    "histogram_distance",
    "load_places",
    "lpips_distance",
    "ocr_stats",
    "place_vector",
    "score_ladder",
    "score_lineup",
    "score_place",
    "ssim_score",
]
