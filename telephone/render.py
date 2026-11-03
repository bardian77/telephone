"""Figures from the ledger: contact sheets, drift curves, survival heatmaps, summaries.

Visual rules (from the dataviz method): one hue per variant in a fixed order, 2px lines,
recessive hairline grid, text in text tokens never series colours, a legend whenever there
are two or more series plus direct end labels up to four, sequential single-hue heatmaps.
"""

from __future__ import annotations

import contextlib
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from .imageio import fit_within  # noqa: E402
from .ledger import Ledger  # noqa: E402
from .metrics.survival import THRESHOLDS, first_failure  # noqa: E402
from .models import GenerationRecord  # noqa: E402

CATEGORICAL = [
    "#2a78d6",
    "#eb6834",
    "#1baf7a",
    "#eda100",
    "#e87ba4",
    "#008300",
    "#6250d6",
    "#e34948",
]
SEQUENTIAL = [
    "#fcfcfb",
    "#cde2fb",
    "#9ec5f4",
    "#6da7ec",
    "#3987e5",
    "#256abf",
    "#184f95",
    "#0d366b",
]
TEXT_PRIMARY, TEXT_SECONDARY, GRID = "#0b0b0b", "#52514e", "#e6e5e1"
SURFACE = "#fcfcfb"
BLUES = LinearSegmentedColormap.from_list("telephone_blue", SEQUENTIAL)

METRIC_LABELS = {
    "clip_dist_to_g0": "CLIP cosine distance to generation 0",
    "hist_dist_to_g0": "Colour histogram distance to generation 0",
    "ssim_to_g0": "SSIM against generation 0",
    "lpips_to_g0": "LPIPS distance to generation 0",
    "file_bytes": "File size (bytes)",
    "survival_fraction": "Fraction of attributes still alive",
}


def _style(ax) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.grid(True, axis="y", color=GRID, linewidth=1)
    ax.tick_params(colors=TEXT_SECONDARY, labelsize=9)
    ax.xaxis.label.set_color(TEXT_SECONDARY)
    ax.yaxis.label.set_color(TEXT_SECONDARY)
    ax.title.set_color(TEXT_PRIMARY)


def variant_of(chain_id: str) -> str:
    parts = chain_id.split("__")
    return parts[1] if len(parts) >= 3 else chain_id


def image_of(chain_id: str) -> str:
    parts = chain_id.split("__")
    return parts[2] if len(parts) >= 3 else chain_id


def type_of(chain_id: str) -> str:
    stem = image_of(chain_id)
    return stem.split("_")[0] if "_" in stem else "untyped"


def metric_value(rec: GenerationRecord, metric: str) -> float | None:
    if metric == "survival_fraction":
        return rec.survival.fraction if rec.survival else None
    return getattr(rec.metrics, metric, None)


# -- contact sheet ------------------------------------------------------------------------


def contact_sheet(
    records: list[GenerationRecord], path: Path, thumb: int = 240, max_cols: int = 13
) -> Path:
    recs = [r for r in records if r.error is None and Path(r.output_path).exists()]
    if not recs:
        raise ValueError("no images to lay out")
    if len(recs) > max_cols:
        idx = sorted({round(i * (len(recs) - 1) / (max_cols - 1)) for i in range(max_cols)})
        recs = [recs[i] for i in idx]
    use_clip = all(r.metrics.clip_dist_to_g0 is not None for r in recs)
    pad, label_h = 8, 34
    tiles = [fit_within(Image.open(r.output_path).convert("RGB"), thumb) for r in recs]
    row_h = max(t.height for t in tiles)
    w = sum(t.width for t in tiles) + pad * (len(tiles) + 1)
    h = row_h + label_h + pad * 2
    sheet = Image.new("RGB", (w, h), SURFACE)
    d = ImageDraw.Draw(sheet)
    x = pad
    for r, t in zip(recs, tiles, strict=True):
        sheet.paste(t, (x, pad + (row_h - t.height) // 2))
        if use_clip:
            dist = f"clip {r.metrics.clip_dist_to_g0:.2f}"
        else:
            dist = f"hist {r.metrics.hist_dist_to_g0 or 0:.2f}"
        alive = f"  {r.survival.alive_count}/{r.survival.total} alive" if r.survival else ""
        d.text((x, pad + row_h + 4), f"g{r.generation}", fill=TEXT_PRIMARY)
        d.text((x, pad + row_h + 18), f"{dist}{alive}", fill=TEXT_SECONDARY)
        x += t.width + pad
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path, format="PNG", optimize=True)
    return path


# -- curves -------------------------------------------------------------------------------


def _series(
    chains: dict[str, list[GenerationRecord]], metric: str
) -> dict[str, list[tuple[int, float]]]:
    out = {}
    for cid, recs in chains.items():
        pts = [
            (r.generation, v)
            for r in recs
            if r.error is None and (v := metric_value(r, metric)) is not None
        ]
        if pts:
            out[cid] = pts
    return out


def _mean_curve(curves: list[list[tuple[int, float]]]) -> list[tuple[int, float, float]]:
    by_gen: dict[int, list[float]] = defaultdict(list)
    for c in curves:
        for g, v in c:
            by_gen[g].append(v)
    out = []
    for g in sorted(by_gen):
        vals = by_gen[g]
        out.append((g, statistics.fmean(vals), statistics.pstdev(vals) if len(vals) > 1 else 0.0))
    return out


def drift_curves(
    groups: dict[str, dict[str, list[GenerationRecord]]], metric: str, path: Path, title: str
) -> Path | None:
    """groups: {group_name: {chain_id: records}}. One hue per group, faint individual chains, bold mean."""
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150, facecolor=SURFACE)
    _style(ax)
    drawn = 0
    ends = []
    for i, (name, chains) in enumerate(groups.items()):
        color = CATEGORICAL[i % len(CATEGORICAL)]
        series = _series(chains, metric)
        if not series:
            continue
        for pts in series.values():
            ax.plot(
                [g for g, _ in pts],
                [v for _, v in pts],
                color=color,
                linewidth=1,
                alpha=0.25,
                solid_capstyle="round",
            )
        mean = _mean_curve(list(series.values()))
        xs, ys = [g for g, _, _ in mean], [m for _, m, _ in mean]
        ax.plot(
            xs,
            ys,
            color=color,
            linewidth=2,
            solid_capstyle="round",
            solid_joinstyle="round",
            label=f"{name} (n={len(series)})",
            marker="o",
            markersize=4,
        )
        ends.append((xs[-1], ys[-1], name, color))
        drawn += 1
    if not drawn:
        plt.close(fig)
        return None
    ax.set_xlabel("generation")
    ax.set_ylabel(METRIC_LABELS.get(metric, metric))
    ax.set_title(title, loc="left", fontsize=11)
    ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
    if drawn >= 2:
        ax.legend(frameon=False, fontsize=8, labelcolor=TEXT_SECONDARY)
    if drawn <= 4:
        for x, y, name, _ in ends:
            ax.annotate(
                name,
                (x, y),
                xytext=(6, 0),
                textcoords="offset points",
                fontsize=8,
                color=TEXT_SECONDARY,
                va="center",
            )
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)
    return path


# -- survival heatmap ---------------------------------------------------------------------


def survival_matrix(
    chains: dict[str, list[GenerationRecord]],
) -> tuple[list[str], list[int], list[list[float | None]]]:
    fields = list(THRESHOLDS)
    gens = sorted(
        {r.generation for recs in chains.values() for r in recs if r.survival is not None}
    )
    cells: list[list[float | None]] = []
    for f in fields:
        row: list[float | None] = []
        for g in gens:
            vals = [
                r.survival.fields[f].alive
                for recs in chains.values()
                for r in recs
                if r.generation == g and r.survival is not None
            ]
            row.append(sum(vals) / len(vals) if vals else None)
        cells.append(row)
    return fields, gens, cells


def survival_heatmap(
    chains: dict[str, list[GenerationRecord]], path: Path, title: str
) -> Path | None:
    fields, gens, cells = survival_matrix(chains)
    if not gens:
        return None
    import numpy as np

    arr = np.array([[np.nan if v is None else v for v in row] for row in cells], dtype=float)
    fig, ax = plt.subplots(
        figsize=(max(5, 0.55 * len(gens) + 2.5), 4.2), dpi=150, facecolor=SURFACE
    )
    im = ax.imshow(arr, cmap=BLUES, vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(gens)), [str(g) for g in gens], fontsize=8, color=TEXT_SECONDARY)
    ax.set_yticks(
        range(len(fields)), [f.replace("_", " ") for f in fields], fontsize=8, color=TEXT_SECONDARY
    )
    ax.set_xlabel("generation", color=TEXT_SECONDARY)
    import textwrap

    ax.set_title("\n".join(textwrap.wrap(title, 70)), loc="left", fontsize=10, color=TEXT_PRIMARY)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks([x - 0.5 for x in range(1, len(gens))], minor=True)
    ax.set_yticks([y - 0.5 for y in range(1, len(fields))], minor=True)
    ax.grid(which="minor", color=SURFACE, linewidth=2)
    ax.tick_params(which="minor", length=0)
    for i in range(len(fields)):
        for j in range(len(gens)):
            v = arr[i, j]
            if not np.isnan(v):
                ax.text(
                    j,
                    i,
                    f"{v:.0%}" if len(gens) <= 14 else "",
                    ha="center",
                    va="center",
                    fontsize=7,
                    color="#ffffff" if v > 0.55 else TEXT_PRIMARY,
                )
    cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cb.ax.tick_params(labelsize=7, colors=TEXT_SECONDARY)
    cb.outline.set_visible(False)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)
    return path


# -- summaries ----------------------------------------------------------------------------


def group_chains(
    records: list[GenerationRecord], by: str = "variant"
) -> dict[str, dict[str, list[GenerationRecord]]]:
    chains: dict[str, list[GenerationRecord]] = defaultdict(list)
    for r in records:
        chains[f"{r.chain_id}/r{r.repeat}"].append(r)
    groups: dict[str, dict[str, list[GenerationRecord]]] = defaultdict(dict)
    for key, recs in chains.items():
        cid = key.split("/r")[0]
        g = variant_of(cid) if by == "variant" else type_of(cid)
        groups[g][key] = sorted(recs, key=lambda r: r.generation)
    return dict(groups)


def summarise(records: list[GenerationRecord]) -> dict[str, Any]:
    out: dict[str, Any] = {"variants": {}, "types": {}}
    for by, bucket in (("variant", "variants"), ("type", "types")):
        for name, chains in group_chains(records, by).items():
            entry: dict[str, Any] = {
                "chains": len(chains),
                "curves": {},
                "first_failure_median": {},
            }
            for metric in ("clip_dist_to_g0", "hist_dist_to_g0", "ssim_to_g0", "survival_fraction"):
                series = _series(chains, metric)
                if series:
                    entry["curves"][metric] = [
                        {"generation": g, "mean": round(m, 4), "std": round(s, 4)}
                        for g, m, s in _mean_curve(list(series.values()))
                    ]
            ffs: dict[str, list[int]] = defaultdict(list)
            for recs in chains.values():
                ff = first_failure([r.survival for r in recs])
                for f, g in ff.items():
                    ffs[f].append(g if g is not None else 10_000)
            for f, gens in ffs.items():
                med = statistics.median(gens)
                entry["first_failure_median"][f] = None if med >= 10_000 else med
            errors = [r for recs in chains.values() for r in recs if r.error]
            entry["errors"] = [
                {"chain_id": r.chain_id, "generation": r.generation, "error": r.error}
                for r in errors
            ]
            entry["cost_usd"] = round(sum(r.cost_usd for recs in chains.values() for r in recs), 4)
            entry["list_price_usd"] = round(
                sum(r.list_price_usd for recs in chains.values() for r in recs), 4
            )
            out[bucket][name] = entry
    return out


def render_experiment(exp_id: str, ledger: Ledger, out_dir: Path) -> list[Path]:
    records = ledger.experiment(exp_id)
    if not records:
        return []
    out = out_dir / exp_id
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    by_variant = group_chains(records, "variant")
    for metric in (
        "clip_dist_to_g0",
        "hist_dist_to_g0",
        "ssim_to_g0",
        "survival_fraction",
        "file_bytes",
    ):
        p = drift_curves(
            by_variant,
            metric,
            out / f"{metric}_by_variant.png",
            f"{exp_id}: {METRIC_LABELS.get(metric, metric)}",
        )
        if p:
            written.append(p)
    by_type = group_chains(records, "type")
    if len(by_type) > 1:
        for metric in ("clip_dist_to_g0", "survival_fraction"):
            p = drift_curves(
                by_type,
                metric,
                out / f"{metric}_by_type.png",
                f"{exp_id}: {METRIC_LABELS.get(metric, metric)} by photo type",
            )
            if p:
                written.append(p)
        for name, chains in by_type.items():
            p = survival_heatmap(
                chains,
                out / f"survival_type_{name}.png",
                f"{exp_id}: what survives in {name} photographs",
            )
            if p:
                written.append(p)
    for name, chains in by_variant.items():
        p = survival_heatmap(
            chains,
            out / f"survival_variant_{name}.png",
            f"{exp_id} / {name}: fraction of chains where each attribute is still alive",
        )
        if p:
            written.append(p)
        for key, recs in chains.items():
            with contextlib.suppress(ValueError):
                written.append(
                    contact_sheet(recs, out / "contact_sheets" / f"{key.replace('/', '_')}.png")
                )
    summary = summarise(records)
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    written.append(out / "summary.json")
    return written


def render_all(experiment: str | None, out_dir: Path) -> list[Path]:
    from .config import get_settings

    s = get_settings()
    ledger = Ledger(s.ledger_path, s.ledger_jsonl)
    ids = [experiment] if experiment else [row["experiment_id"] for row in ledger.experiments()]
    written: list[Path] = []
    for eid in ids:
        written.extend(render_experiment(eid, ledger, out_dir))
    return written
