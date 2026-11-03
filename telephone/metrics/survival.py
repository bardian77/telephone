"""Survival: which readings of the image persist across generations.

Each Attributes field gets a score in [0, 1] against generation 0 and an alive/dead call.
Rules are simple and stated so they can be argued with (and validated against hand labels).
"""

from __future__ import annotations

import difflib
import re

from ..models import Attributes, FieldSurvival, Survival

STOP = {
    "a",
    "an",
    "the",
    "of",
    "in",
    "on",
    "at",
    "and",
    "with",
    "to",
    "by",
    "near",
    "some",
    "street",
}

THRESHOLDS: dict[str, float] = {
    "objects": 0.3,
    "people_count": 1.0,
    "visible_text": 0.5,
    "setting": 0.5,
    "lighting": 1.0,
    "mood": 0.6,
    "dominant_colors": 0.34,
    "camera_angle": 1.0,
    "is_photograph": 1.0,
}


def norm_token(s: str) -> str:
    s = re.sub(r"[^a-z0-9 ]", " ", s.lower()).strip()
    s = re.sub(r"\s+", " ", s)
    # crude singular
    return " ".join(
        w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w for w in s.split()
    )


def norm_set(items: list[str]) -> set[str]:
    out: set[str] = set()
    for it in items:
        t = norm_token(it)
        if t:
            out.add(t)
            # also add head noun so 'red car' matches 'car'
            head = t.split()[-1]
            if head not in STOP:
                out.add(head)
    return out


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def fuzzy(a: str, b: str) -> float:
    a, b = norm_token(a), norm_token(b)
    if not a and not b:
        return 1.0
    ta = {w for w in a.split() if w not in STOP}
    tb = {w for w in b.split() if w not in STOP}
    overlap = jaccard(ta, tb) if (ta or tb) else 0.0
    seq = difflib.SequenceMatcher(None, a, b).ratio()
    return max(overlap, seq)


def text_score(a: list[str], b: list[str]) -> float:
    ta = {w for s in a for w in norm_token(s).split()}
    tb = {w for s in b for w in norm_token(s).split()}
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    # partial credit for shared characters when words differ slightly (OCR-like drift)
    j = jaccard(ta, tb)
    seq = difflib.SequenceMatcher(None, " ".join(sorted(ta)), " ".join(sorted(tb))).ratio()
    return max(j, seq * 0.8)


def compare_attributes(g0: Attributes, now: Attributes) -> Survival:
    scores: dict[str, tuple[float, object, object]] = {
        "objects": (jaccard(norm_set(g0.objects), norm_set(now.objects)), g0.objects, now.objects),
        "people_count": (
            1.0
            if g0.people_count == now.people_count
            else max(
                0.0,
                1
                - abs(g0.people_count - now.people_count)
                / max(1, g0.people_count, now.people_count),
            ),
            g0.people_count,
            now.people_count,
        ),
        "visible_text": (
            text_score(g0.visible_text, now.visible_text),
            g0.visible_text,
            now.visible_text,
        ),
        "setting": (fuzzy(g0.setting, now.setting), g0.setting, now.setting),
        "lighting": (
            1.0 if norm_token(g0.lighting) == norm_token(now.lighting) else 0.0,
            g0.lighting,
            now.lighting,
        ),
        "mood": (fuzzy(g0.mood, now.mood), g0.mood, now.mood),
        "dominant_colors": (
            jaccard(norm_set(g0.dominant_colors), norm_set(now.dominant_colors)),
            g0.dominant_colors,
            now.dominant_colors,
        ),
        "camera_angle": (
            1.0 if norm_token(g0.camera_angle) == norm_token(now.camera_angle) else 0.0,
            g0.camera_angle,
            now.camera_angle,
        ),
        "is_photograph": (
            1.0 if g0.is_photograph == now.is_photograph else 0.0,
            g0.is_photograph,
            now.is_photograph,
        ),
    }
    fields = {
        k: FieldSurvival(alive=s >= THRESHOLDS[k], score=round(s, 4), g0=a, now=b)
        for k, (s, a, b) in scores.items()
    }
    alive = sum(1 for f in fields.values() if f.alive)
    return Survival(fields=fields, alive_count=alive, total=len(fields))


def first_failure(survivals: list[Survival | None]) -> dict[str, int | None]:
    """Per field, the first generation index where it is dead (None if it never dies)."""
    out: dict[str, int | None] = {k: None for k in THRESHOLDS}
    for gen, s in enumerate(survivals):
        if s is None:
            continue
        for k, f in s.fields.items():
            if out[k] is None and not f.alive:
                out[k] = gen
    return out
