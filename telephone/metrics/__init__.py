"""Metrics: drift (CLIP cosine distance, colour-histogram distance), structure (SSIM, LPIPS),
survival (attribute comparison), machine readability (OCR, faces), place (where the true place
comes when CLIP sorts a line-up of candidate names by how well they match the picture) and
detail (fine detail at a picture's own size, against the same part of the original)."""

from .detail import CropBox, box_after, detail_scores, reference_for, registration_shift, whole
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
from .structural import lpips_distance, settled_at, ssim_score
from .survival import compare_attributes, first_failure

__all__ = [
    "ClipEmbedder",
    "CropBox",
    "MetricsUnavailable",
    "PlaceEntry",
    "box_after",
    "calibrate_places",
    "compare_attributes",
    "cosine_distance",
    "detail_scores",
    "face_count",
    "first_failure",
    "histogram_distance",
    "load_places",
    "lpips_distance",
    "ocr_stats",
    "place_vector",
    "reference_for",
    "registration_shift",
    "score_ladder",
    "score_lineup",
    "score_place",
    "settled_at",
    "ssim_score",
    "whole",
]
