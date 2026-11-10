"""Numbers into plain words.

The pipeline records metrics; this module says what they mean, in sentences a first-time visitor
can read. Everything here is a pure function of ledger rows, so it is tested without a server.

The drift scale. CLIP distance to the original is 0 for an identical picture. Two different
photographs from this project are about 0.43 apart (README, glossary). The dashboard draws drift
as a position between those two anchors. The four named bands are a rule of thumb for reading
that position, chosen by hand; they are not measured thresholds and the interface says so.
"""

from __future__ import annotations

from typing import Any

from ..experiments import MOCK_SUFFIX
from ..metrics.survival import THRESHOLDS, first_failure
from ..models import GenerationRecord

DIFFERENT_PHOTO_CLIP = 0.43

# (key, upper bound as a fraction of the way to a different photograph, label, meaning)
BANDS: list[tuple[str, float, str, str]] = [
    ("same", 0.10, "Same picture", "A machine can barely tell it from the original."),
    ("worn", 0.40, "Same picture, worn", "Clearly the same photograph, with visible damage."),
    (
        "drifting",
        0.75,
        "Drifting",
        "Related to the original, but no longer the same picture.",
    ),
    (
        "different",
        float("inf"),
        "A different picture",
        "About as far from the original as an unrelated photograph.",
    ),
]

FIELD_LABELS: dict[str, str] = {
    "objects": "Objects in the picture",
    "people_count": "Number of people",
    "visible_text": "Readable text",
    "setting": "Where it is",
    "lighting": "Lighting",
    "mood": "Mood",
    "dominant_colors": "Main colours",
    "camera_angle": "Camera angle",
    "is_photograph": "Still looks like a photograph",
}

ROLE_OF_KIND = {
    "platform": "Platform",
    "caption": "Reader",
    "regenerate": "Painter",
    "physical": "Camera",
    "extract": "Survival form",
}

CAPTION_MODES = {
    "short": "one sentence of about 20 words",
    "detailed": "about 150 words",
    "literal": "a plain list of the things in it",
}


# -- drift ----------------------------------------------------------------------------------


def drift_position(clip: float | None) -> float | None:
    """How far along the scale from the original (0) to a different photograph (1)."""
    if clip is None:
        return None
    return max(0.0, min(1.0, clip / DIFFERENT_PHOTO_CLIP))


def drift_band(clip: float | None) -> dict[str, str]:
    pos = drift_position(clip)
    if pos is None:
        return {
            "key": "unknown",
            "label": "Not measured",
            "meaning": "The comparison model was not available for this run.",
        }
    for key, upper, label, meaning in BANDS:
        if pos < upper:
            return {"key": key, "label": label, "meaning": meaning}
    key, _, label, meaning = BANDS[-1]
    return {"key": key, "label": label, "meaning": meaning}


def settled_generation(values: list[float | None], tol: float = 0.005) -> int | None:
    """The first generation after which the series stays within `tol` of where it ends.

    None when the series is too short to tell or is still moving at its last step.
    """
    pts = [(i, v) for i, v in enumerate(values) if v is not None]
    if len(pts) < 3:
        return None
    final = pts[-1][1]
    settled: int | None = None
    for i, v in reversed(pts):
        if abs(v - final) > tol:
            break
        settled = i
    if settled is None or settled == 0 or settled >= pts[-1][0]:
        return None
    return settled


# -- names ----------------------------------------------------------------------------------


def photo_label(stem: str) -> dict[str, str]:
    """'street_bologna_portici_01' -> {'name': 'Bologna portici 01', 'type': 'street'}."""
    if "_" not in stem:
        return {"name": stem, "type": "untyped"}
    kind, _, rest = stem.partition("_")
    name = rest.replace("_", " ").strip()
    return {"name": name[:1].upper() + name[1:], "type": kind}


def variant_label(name: str) -> str:
    text = name.replace("_", " ").strip()
    return text[:1].upper() + text[1:]


def describe_station(st: dict[str, Any]) -> dict[str, str]:
    """One station of a chain, as a role and a sentence. `st` is a StationConfig as a dict."""
    kind = st.get("kind", "")
    params = st.get("params") or {}
    role = ROLE_OF_KIND.get(kind, kind.capitalize())
    if kind == "platform":
        from ..stations.platform import resolve_params

        p = resolve_params(params)
        preset = params.get("preset") or "instagram"
        text = (
            f"{variant_label(preset)} preset: shrink to at most {p['max_side']} px, re-save as "
            f"JPEG at quality {p['quality']}, strip the metadata"
        )
    elif kind == "caption":
        mode = params.get("mode", "detailed")
        text = f"describes the picture in {CAPTION_MODES.get(mode, mode)}"
    elif kind == "regenerate":
        text = "draws a new picture from the description alone"
    elif kind == "physical":
        text = "a phone photograph of a screen showing the previous generation"
    else:
        text = kind
    model = st.get("model") or st.get("provider")
    return {"kind": kind, "role": role, "text": text, "model": model or ""}


# -- one chain ------------------------------------------------------------------------------


def _kb(n: int | None) -> str:
    if n is None:
        return "?"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f} MB"
    return f"{round(n / 1000)} kB"


def _chain_kind(recs: list[GenerationRecord]) -> str:
    seq = recs[0].station_sequence
    if "physical" in seq:
        return "physical"
    if "caption" in seq or "regenerate" in seq:
        return "ai"
    return "compression"


def is_simulation(recs: list[GenerationRecord]) -> bool:
    if recs and recs[0].experiment_id.endswith(MOCK_SUFFIX):
        return True
    return any(s.provider == "mock" for r in recs for s in r.stations)


def survival_summary(recs: list[GenerationRecord]) -> dict[str, Any] | None:
    ok = [r for r in recs if r.error is None]
    last = next((r for r in reversed(ok) if r.survival is not None), None)
    if last is None or last.survival is None:
        return None
    by_gen = {r.generation: r.survival for r in ok}
    top = max(by_gen)
    failures = first_failure([by_gen.get(g) for g in range(top + 1)])
    lost = sorted(
        (
            {"field": k, "label": FIELD_LABELS.get(k, k), "generation": g}
            for k, g in failures.items()
            if g is not None
        ),
        key=lambda f: (f["generation"], list(THRESHOLDS).index(f["field"])),
    )
    kept = [FIELD_LABELS.get(k, k) for k, g in failures.items() if g is None]
    return {
        "alive": last.survival.alive_count,
        "total": last.survival.total,
        "lost": lost,
        "kept": kept,
    }


def chain_reading(recs: list[GenerationRecord]) -> dict[str, Any]:
    """What one chain shows, as a headline, a few facts and the position on the drift scale."""
    recs = sorted(recs, key=lambda r: r.generation)
    ok = [r for r in recs if r.error is None]
    first, last = ok[0], ok[-1]
    kind = _chain_kind(recs)
    trips = last.generation
    clip = last.metrics.clip_dist_to_g0 if trips else None
    band = drift_band(clip)
    pos = drift_position(clip)
    series = [r.metrics.clip_dist_to_g0 for r in ok]
    if all(v is None for v in series[1:]):
        series = [None if r.metrics.ssim_to_g0 is None else 1 - r.metrics.ssim_to_g0 for r in ok]
    settled = settled_generation(series)
    survival = survival_summary(recs)
    failed = next((r for r in recs if r.error is not None), None)

    noun = {"compression": "upload", "ai": "round", "physical": "re-photographing"}[kind]
    plural = noun + ("s" if trips != 1 else "")
    where = {
        "same": "this is still the same picture",
        "worn": "this is the same picture with visible damage",
        "drifting": "the picture has drifted away from the original",
        "different": "this is a different picture",
        "unknown": "the picture was not compared with the original",
    }[band["key"]]
    if trips == 0:
        headline = "Only the original is here. Nothing has been through the loop yet."
    else:
        headline = f"After {trips} {plural}, {where}."
        if settled == 1 and trips > 1:
            headline += (
                f" All of the change happened on the first {noun}; the {trips - 1} after it "
                "changed nothing you can measure."
            )
        elif settled is not None and trips > 1:
            headline += f" It stopped changing after {noun} {settled}."
        elif trips > 2:
            headline += f" It was still changing at the last {noun}."
    if failed is not None:
        headline += f" The run stopped at generation {failed.generation}: {failed.error}"

    facts: list[dict[str, str]] = []
    if clip is not None and pos is not None:
        facts.append(
            {
                "label": "Drift",
                "value": f"{clip:.3f}",
                "meaning": f"{round(pos * 100)}% of the way from the original to a different "
                f"photograph. {band['label']}.",
            }
        )
    ssim = last.metrics.ssim_to_g0
    if ssim is not None and trips:
        meaning = (
            "1.000 means the pixel patterns match exactly. One Instagram-style upload scores "
            "about 0.99."
            if kind == "compression"
            else "For a redrawn picture this only confirms that the pixels are different."
        )
        facts.append({"label": "Pixel structure", "value": f"{ssim:.3f}", "meaning": meaning})
    b0, b1 = first.metrics.file_bytes, last.metrics.file_bytes
    if b0 and b1 and trips:
        facts.append(
            {
                "label": "File size",
                "value": f"{_kb(b0)} to {_kb(b1)}",
                "meaning": f"{round(100 * b1 / b0)}% of the original file.",
            }
        )
    w0, w1 = first.metrics.width, last.metrics.width
    if w0 and w1 and trips:
        h0, h1 = first.metrics.height, last.metrics.height
        facts.append(
            {
                "label": "Pixel size",
                "value": f"{w0} × {h0} to {w1} × {h1}",
                "meaning": "Not resized."
                if (w0, h0) == (w1, h1)
                else f"{round(100 * w1 / w0)}% of the original width.",
            }
        )
    if survival is not None and trips:
        if survival["lost"]:
            f0 = survival["lost"][0]
            meaning = f"First to go: {f0['label'].lower()}, at generation {f0['generation']}."
        else:
            meaning = "Every fact on the survival form still matches the original."
        facts.append(
            {
                "label": "Facts kept",
                "value": f"{survival['alive']} of {survival['total']}",
                "meaning": meaning,
            }
        )

    return {
        "kind": kind,
        "simulation": is_simulation(recs),
        "headline": headline,
        "facts": facts,
        "trips": trips,
        "drift": clip,
        "position": pos,
        "band": band,
        "settled_at": settled,
        "survival": survival,
    }


# -- one experiment -------------------------------------------------------------------------


def experiment_findings(chains: list[dict[str, Any]]) -> list[str]:
    """A few sentences about a set of chain summaries (see service.chain_summary)."""
    done = [c for c in chains if c["reading"]["trips"] > 0]
    if not done:
        return []
    out: list[str] = []
    measured = [c for c in done if c["reading"]["drift"] is not None]
    by_variant: dict[str, list[dict[str, Any]]] = {}
    for c in measured:
        by_variant.setdefault(c["variant_label"], []).append(c)
    for label, group in by_variant.items():
        lo = min(c["reading"]["drift"] for c in group)
        hi = max(c["reading"]["drift"] for c in group)
        plo, phi = round(100 * drift_position(lo)), round(100 * drift_position(hi))  # type: ignore[operator]
        span = f"{plo}%" if plo == phi else f"{plo}% to {phi}%"
        out.append(
            f"{label}: the pictures ended {span} of the way to a different photograph "
            f"(drift {lo:.2f} to {hi:.2f})."
            if len(group) > 1
            else f"{label}: the picture ended {span} of the way to a different photograph "
            f"(drift {hi:.2f})."
        )
    first_trip = [c for c in done if c["reading"]["settled_at"] == 1]
    if len(first_trip) == len(done) and len(done) > 1:
        out.append(
            f"All {len(done)} chains did their changing on the first trip round the loop and "
            "then stood still."
        )
    elif first_trip:
        out.append(
            f"{len(first_trip)} of {len(done)} chains did all of their changing on the first "
            "trip round the loop."
        )
    if measured:
        worst = max(measured, key=lambda c: c["reading"]["drift"])
        out.append(
            f"The photograph that moved furthest was {worst['photo_label']['name']} under "
            f"{worst['variant_label']} (drift {worst['reading']['drift']:.2f})."
        )
    with_form = [c for c in done if c["reading"]["survival"]]
    if with_form:
        counts: dict[str, int] = {}
        for c in with_form:
            lost = c["reading"]["survival"]["lost"]
            if lost:
                counts[lost[0]["label"]] = counts.get(lost[0]["label"], 0) + 1
        if counts:
            top, n = max(counts.items(), key=lambda kv: kv[1])
            out.append(
                f"The fact that died first most often was {top.lower()}, in {n} of "
                f"{len(with_form)} chains."
            )
    return out
