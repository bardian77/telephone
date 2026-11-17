"""Figures and numbers for 17 November: the screenshot-and-forward loop (experiment 7), the
fine-detail comparison, the place line-up and the corrected CLIP build.

Writes to docs/tutorial-17nov/figures/:

  detail_by_journey.png      fine detail left, pass by pass, one panel per photograph
  settled_at.png             the pass at which each journey stopped changing
  two_measures.png           the first SSIM (512 px copies) against the measures made at full size
  place_calibration.png      the true place's probability, on the mis-built and corrected model
  place_over_passes.png      the true place's probability over the passes
  exp01_clip_before_after.png  experiment 1's CLIP distances before and after the correction
  closeup_<stem>.jpg         the same spot of each photograph, at every journey and pass
  six_photographs.jpg        the six starting photographs, named
  figures.json               for each figure: what it shows, where the numbers come from, alt text

and prints the table the written summary quotes. Run from anywhere:

    .venv/bin/python analysis/tutorial_17nov.py

Where the numbers come from. Everything except the close-ups is read from committed files in
data/results/ (and docs/evidence/ for the "before" values), so the charts can be redrawn from a
clean clone. The close-ups need the pictures themselves, which are local (data/runs/); they are
skipped with a message when the runs are not on this machine.

Design notes (scientific-visualization skill). Position on a common scale throughout. Five
journeys use the five colours of the skill's Okabe-Ito subset for white backgrounds, and each
also has its own marker and a direct label, so colour is never the only cue. Shares (fine detail,
probability) are drawn from 0. No dual axes: measures with different meanings get their own
panels. Missing values are left as gaps, never joined. The 460 px reflection crop is left out of
the fine-detail panels and said to be, because the app enlarges it and nothing fair exists to
compare it with. Close-ups are unprocessed pixels: each cell is cut from the pipeline's own
output file, and the "original" cell is the same region of the original resized once.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from telephone import paths  # noqa: E402
from telephone.metrics import settled_at as settled  # noqa: E402

ROOT = paths.project_root()
SKILL = ROOT / ".claude" / "skills" / "scientific-visualization"
sys.path[:0] = [str(SKILL / "scripts"), str(SKILL / "assets")]
from figure_export import export_figure  # noqa: E402
from style_presets import style_context  # noqa: E402

RESULTS = ROOT / "data" / "results"
EVIDENCE = ROOT / "docs" / "evidence"
OUT = ROOT / "docs" / "tutorial-17nov" / "figures"
EXP = "exp07_screenshot_loop"

# photograph -> (name on the figure, where the close-up looks: fractions of width and height)
PHOTOS = {
    "street_bologna_portici_01": ("Bologna, the porticoes", (0.78, 0.52)),
    "street_barbican_lake_01": ("The Barbican lake", (0.56, 0.76)),
    "text_barbican_seddon_house_01": ("Seddon House sign", (0.07, 0.955)),
    "landscape_dolomites_larches_01": ("Larches, Dolomites", (0.30, 0.50)),
    "portrait_dolomites_self_01": ("Self-portrait, Dolomites", (0.555, 0.62)),
    "abstract_barbican_reflection_01": ("Reflection (460 px crop)", (0.5, 0.5)),
}
ENLARGED = {"abstract_barbican_reflection_01"}  # smaller than the app's size: not comparable

# journey -> (label, colour, marker, line style). Colours: Okabe-Ito subset for white grounds.
JOURNEYS = {
    "reupload": ("Upload again (control)", "#000000", "o", "-"),
    "screenshot": ("Screenshot, one phone", "#0072B2", "s", "-"),
    "screenshot_bilinear": ("Screenshot, other resampling", "#009E73", "^", "--"),
    "screenshot_many_phones": ("Different phone each pass", "#D55E00", "D", "-"),
    "screenshot_loose_crop": ("Careless crop each pass", "#CC79A7", "v", "-"),
}
SHOWN_PASSES = [0, 1, 5, 10, 20, 40]
DESCRIPTIONS: dict[str, dict] = {}


def read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def by_chain(rows: list[dict]) -> dict[tuple[str, str], dict[int, dict]]:
    """{(photograph, journey): {generation: row}} for repeat 0."""
    out: dict[tuple[str, str], dict[int, dict]] = defaultdict(dict)
    for r in rows:
        if int(r.get("repeat", 0)) != 0:
            continue
        parts = r["chain_id"].split("__")
        out[(parts[2], parts[1])][int(r["generation"])] = r
    return out


def series(chain: dict[int, dict], pick) -> tuple[list[int], list[float]]:
    """x and y for one chain, with NaN where a value is missing so the line shows a gap."""
    gens = sorted(chain)
    ys = []
    for g in gens:
        v = pick(chain[g])
        ys.append(float("nan") if v is None else float(v))
    return gens, ys


def settled_at(chain: dict[int, dict]) -> int | None:
    """The pass from which no later pass changed the picture (telephone.metrics.settled_at)."""
    last = max(chain)
    prev = [(chain.get(g, {}).get("metrics") or {}).get("ssim_to_prev") for g in range(last + 1)]
    return settled(prev)


def save(fig, name: str, what: str, sources: list[str], alt: str, kind: str = "png") -> None:
    """Charts are saved as PNG. Grids of photographs are saved as JPEG (`kind="jpg"`): as PNG
    they are several megabytes each, and nothing is measured from them."""
    export_figure(
        fig,
        OUT / name,
        formats=[kind],
        dpi=160 if kind == "png" else 130,
        overwrite=True,
        mkdir=True,
        provenance={"raw_data": ", ".join(sources), "transformations": ["none: values as saved"]},
    )
    plt.close(fig)
    long_name = OUT / f"{name}.jpeg"  # the exporter writes JPEGs with the long extension
    if kind == "jpg" and long_name.exists():
        long_name.replace(OUT / f"{name}.jpg")
    DESCRIPTIONS[f"{name}.{kind}"] = {"shows": what, "sources": sources, "alt": alt}
    print(f"wrote {OUT / name}.{kind}")


def legend_handles(journeys: list[str]):
    from matplotlib.lines import Line2D

    return [
        Line2D([0], [0], color=JOURNEYS[j][1], marker=JOURNEYS[j][2], linestyle=JOURNEYS[j][3])
        for j in journeys
    ], [JOURNEYS[j][0] for j in journeys]


def fig_detail(detail) -> None:
    stems = [s for s in PHOTOS if s not in ENLARGED]
    journeys = [j for j in JOURNEYS if any((s, j) in detail for s in stems)]
    fig, axes = plt.subplots(
        2, 3, figsize=(15, 8.4), layout="constrained", sharex=True, sharey=True
    )
    flat = list(axes.flat)
    for ax, stem in zip(flat, stems, strict=False):
        for j in journeys:
            chain = detail.get((stem, j))
            if not chain:
                continue
            x, y = series(chain, lambda r: r.get("detail_kept"))
            label, colour, marker, style = JOURNEYS[j]
            ax.plot(x, y, color=colour, marker=marker, linestyle=style, markevery=5, label=label)
        ax.set_title(PHOTOS[stem][0])
        ax.set_ylim(0, 1.15)
        ax.axhline(1.0, color="#888888", linewidth=0.8, linestyle=":")
        ax.grid(axis="y", color="#dddddd", linewidth=0.8)
    note = flat[len(stems)]
    note.axis("off")
    handles, labels = legend_handles(journeys)
    note.legend(handles, labels, loc="upper left", frameon=False, title="What happens each pass")
    note.text(
        0.0,
        0.02,
        "1.0 = all the fine detail of the same part of the\noriginal, resized once, is still in place.\n"
        "Fine detail: what a slight blur would remove.\nThe 460 px reflection crop is left out: the app\n"
        "enlarges it, so nothing fair exists to compare\nit with.",
        transform=note.transAxes,
        fontsize=11,
        va="bottom",
    )
    fig.supxlabel("Pass")
    fig.supylabel("Share of the original's fine detail still in place")
    save(
        fig,
        "detail_by_journey",
        "Fine detail left after each pass, for five photographs and five journeys.",
        [f"data/results/{EXP}_detail.jsonl"],
        "Five line charts, one per photograph. In each, the control and the two one-phone "
        "screenshot journeys level off within the first passes, while the different-phone and "
        "careless-crop journeys keep falling.",
    )


def fig_settled(ledger) -> None:
    stems = list(PHOTOS)
    journeys = [j for j in JOURNEYS if any((s, j) in ledger for s in stems)]
    last = max((max(c) for c in ledger.values()), default=40)
    never_x = last + 5
    fig, ax = plt.subplots(figsize=(13, 6.2), layout="constrained")
    for row, stem in enumerate(stems):
        for k, j in enumerate(journeys):
            chain = ledger.get((stem, j))
            if not chain:
                continue
            s = settled_at(chain)
            y = row + (k - (len(journeys) - 1) / 2) * 0.14
            label, colour, marker, _ = JOURNEYS[j]
            ax.plot([never_x if s is None else s], [y], color=colour, marker=marker, linestyle="")
    ax.axvline(last + 1.5, color="#888888", linestyle="--", linewidth=1)
    ax.set_yticks(range(len(stems)), [PHOTOS[s][0] for s in stems])
    ax.invert_yaxis()
    ticks = [1, 5, 10, 15, 20, 25, 30, 35, 40]
    ax.set_xticks(
        [t for t in ticks if t <= last] + [never_x],
        [str(t) for t in ticks if t <= last] + [f"not in\n{last} passes"],
    )
    ax.set_xlim(0, never_x + 3)
    ax.set_xlabel("Pass from which nothing changed again (SSIM to the pass before = 1.000000)")
    ax.grid(axis="x", color="#dddddd", linewidth=0.8)
    handles, labels = legend_handles(journeys)
    for h in handles:
        h.set_linestyle("")
    fig.legend(handles, labels, loc="outside right center", frameon=False)
    save(
        fig,
        "settled_at",
        "The pass at which each journey stopped changing, for six photographs. "
        "This test reads change at the scale of a 512 px copy; for the careless-crop journey it "
        "only shows that the crop differs every pass.",
        [f"data/results/{EXP}.jsonl"],
        "A dot chart with one row per photograph. Dots for the control sit at low pass numbers, "
        "dots for the one-phone screenshot journeys sit later, and dots for the different-phone "
        "and careless-crop journeys sit in the 'not in 40 passes' column.",
    )


def fig_two_measures(ledger, detail) -> None:
    stems = [s for s in PHOTOS if s not in ENLARGED]
    pair = ["reupload", "screenshot"]
    last = max((max(c) for c in ledger.values()), default=40)
    panels = [
        (
            "SSIM on 512 px copies\n(the first measure)",
            lambda s, j: (ledger[(s, j)][last].get("metrics") or {}).get("ssim_to_g0"),
        ),
        ("SSIM at the picture's own size", lambda s, j: detail[(s, j)][last].get("ssim_native")),
        (
            "Original's fine detail still in place",
            lambda s, j: detail[(s, j)][last].get("detail_kept"),
        ),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(15, 5.6), layout="constrained", sharey=True)
    for ax, (title, pick) in zip(axes, panels, strict=True):
        for row, stem in enumerate(stems):
            vals = []
            for j in pair:
                if (stem, j) not in ledger or (stem, j) not in detail:
                    continue
                v = pick(stem, j)
                if v is None:
                    continue
                vals.append(v)
                _, colour, marker, _ = JOURNEYS[j]
                ax.plot([v], [row], color=colour, marker=marker, linestyle="")
            if len(vals) == 2:
                ax.plot(vals, [row, row], color="#888888", linewidth=1, zorder=0)
        ax.set_title(title)
        ax.set_xlim(0, 1.05)
        ax.grid(axis="x", color="#dddddd", linewidth=0.8)
    axes[0].set_yticks(range(len(stems)), [PHOTOS[s][0] for s in stems])
    axes[0].invert_yaxis()
    handles, labels = legend_handles(pair)
    for h in handles:
        h.set_linestyle("")
    fig.legend(handles, labels, loc="outside lower center", ncols=2, frameon=False)
    fig.suptitle(f"The same files after {last} passes, measured three ways")
    save(
        fig,
        "two_measures",
        f"After {last} passes, the control and the one-phone screenshot journey compared by the "
        "first SSIM (on 512 px copies) and by the two measures made at the picture's own size.",
        [f"data/results/{EXP}.jsonl", f"data/results/{EXP}_detail.jsonl"],
        "Three panels of paired dots for five photographs. In the first panel the two journeys "
        "are almost on top of each other near 1. In the second and third the screenshot journey "
        "sits clearly lower than the control.",
    )


def fig_place_calibration() -> None:
    new = json.loads((RESULTS / "place_calibration.json").read_text(encoding="utf-8"))
    old_path = EVIDENCE / "2026-11-17_place_calibration_wrong_clip_build.json"
    old = json.loads(old_path.read_text(encoding="utf-8")) if old_path.is_file() else None
    stems = list(PHOTOS)
    new_by = {r["image"]: r for r in new["photographs"]}
    old_by = {r["image"]: r for r in old["photographs"]} if old else {}
    fig, ax = plt.subplots(figsize=(13, 5.8), layout="constrained")
    for row, stem in enumerate(stems):
        n, o = new_by.get(stem), old_by.get(stem)
        if n is None:
            continue
        if o is not None:
            ax.plot([o["prob"], n["prob"]], [row, row], color="#888888", linewidth=1.2, zorder=0)
            ax.plot(
                [o["prob"]],
                [row],
                marker="o",
                markerfacecolor="white",
                color="#000000",
                linestyle="",
            )
            ax.annotate(
                f"rank {o['rank']}",
                (o["prob"], row),
                textcoords="offset points",
                xytext=(0, 10),
                ha="center",
                fontsize=10,
                color="#555555",
            )
        ax.plot([n["prob"]], [row], marker="o", color="#000000", linestyle="")
        ax.annotate(
            f"rank {n['rank']}",
            (n["prob"], row),
            textcoords="offset points",
            xytext=(0, -18),
            ha="center",
            fontsize=10,
        )
    chance = 1 / new["photographs"][0]["lineup_size"]
    ax.axvline(chance, color="#D55E00", linestyle="--", linewidth=1.2)
    ax.annotate(
        "chance:\n1 in 12",
        (chance, len(stems) - 0.45),
        xytext=(6, 0),
        textcoords="offset points",
        color="#D55E00",
        fontsize=10,
        va="center",
    )
    ax.set_yticks(range(len(stems)), [PHOTOS[s][0] for s in stems])
    ax.set_ylim(len(stems) - 0.2, -0.6)
    ax.set_xlim(0, 1.02)
    ax.set_xlabel("Probability given to the true place among 12 candidate names")
    ax.grid(axis="x", color="#dddddd", linewidth=0.8)
    from matplotlib.lines import Line2D

    fig.legend(
        [
            Line2D([0], [0], marker="o", markerfacecolor="white", color="#000000", linestyle=""),
            Line2D([0], [0], marker="o", color="#000000", linestyle=""),
        ],
        [
            "Model built with the wrong activation (first calibration)",
            "Model built as trained (corrected)",
        ],
        loc="outside lower center",
        ncols=2,
        frameon=False,
    )
    save(
        fig,
        "place_calibration",
        "Where the true place comes in its line-up of 12 for the six originals, on the mis-built "
        "CLIP model and on the corrected one. The three line-ups are not equally hard.",
        [
            "data/results/place_calibration.json",
            "docs/evidence/2026-11-17_place_calibration_wrong_clip_build.json",
        ],
        "Six rows of paired dots. On the corrected model every true place ranks first. The "
        "reflection crop, registered as a control that should not be placeable, moves from "
        "about chance on the mis-built model to about 0.6 on the corrected one.",
    )


def fig_place_passes(place) -> None:
    stems = list(PHOTOS)
    journeys = [j for j in JOURNEYS if any((s, j) in place for s in stems)]
    if not journeys:
        print("no place results for the experiment yet; skipping place_over_passes")
        return
    fig, axes = plt.subplots(
        2, 3, figsize=(15, 8.4), layout="constrained", sharex=True, sharey=True
    )
    for ax, stem in zip(axes.flat, stems, strict=True):
        for j in journeys:
            chain = place.get((stem, j))
            if not chain:
                continue
            x, y = series(chain, lambda r: r.get("prob"))
            label, colour, marker, style = JOURNEYS[j]
            ax.plot(x, y, color=colour, marker=marker, linestyle=style, markevery=5, label=label)
            lost = [
                (g, chain[g]["prob"])
                for g in sorted(chain)
                if chain[g].get("rank") not in (None, 1)
            ]
            if lost:  # passes where the true place was not first: marked, never hidden
                ax.plot(
                    [g for g, _ in lost],
                    [p for _, p in lost],
                    color=colour,
                    marker="x",
                    linestyle="",
                    markersize=9,
                )
        ax.set_title(PHOTOS[stem][0])
        ax.set_ylim(0, 1.05)
        ax.axhline(1 / 12, color="#888888", linewidth=0.8, linestyle=":")
        ax.grid(axis="y", color="#dddddd", linewidth=0.8)
    handles, labels = legend_handles(journeys)
    fig.legend(handles, labels, loc="outside lower center", ncols=3, frameon=False)
    for ax in axes[-1]:
        ax.set_xlabel("Pass")
    fig.supylabel("Probability of the true place among 12 names")
    save(
        fig,
        "place_over_passes",
        "The probability CLIP gives the true place, pass by pass. A cross marks any pass where "
        "the true place was not ranked first. The dotted line is chance (1 in 12).",
        [f"data/results/{EXP}_place.jsonl"],
        "Six line charts, one per photograph, showing the probability of the true place over "
        "the passes for each journey.",
    )


def fig_exp01_clip() -> None:
    new = by_chain(read_jsonl(RESULTS / "exp01_compression.jsonl"))
    old = by_chain(read_jsonl(EVIDENCE / "2026-11-09_exp01_results_wrong_clip_build.jsonl"))
    if not new or not old:
        print("experiment 1 before/after files not both present; skipping exp01_clip_before_after")
        return
    presets = {
        "whatsapp": ("WhatsApp", "#0072B2", "o"),
        "instagram": ("Instagram", "#009E73", "s"),
        "screenshot_whatsapp": ("Screenshot + WhatsApp", "#CC79A7", "^"),
        "harsh": ("Harsh (512 px, q30)", "#D55E00", "D"),
    }
    fig, ax = plt.subplots(figsize=(7.6, 7), layout="constrained")
    top = 0.0
    for (stem, variant), chain in new.items():
        if (stem, variant) not in old or variant not in presets:
            continue
        g = max(chain)
        a = (old[(stem, variant)].get(g, {}).get("metrics") or {}).get("clip_dist_to_g0")
        b = (chain[g].get("metrics") or {}).get("clip_dist_to_g0")
        if a is None or b is None:
            continue
        label, colour, marker = presets[variant]
        ax.plot([a], [b], color=colour, marker=marker, linestyle="")
        top = max(top, a, b)
    lim = top * 1.1 or 0.2
    ax.plot([0, lim], [0, lim], color="#888888", linewidth=1, linestyle="--")
    ax.annotate(
        "same value",
        (lim * 0.78, lim * 0.78),
        rotation=45,
        xytext=(4, -14),
        textcoords="offset points",
        color="#555555",
        fontsize=10,
    )
    ax.set_xlim(0, lim)
    ax.set_ylim(0, lim)
    ax.set_aspect("equal")
    ax.set_xlabel("CLIP distance, model built with the wrong activation")
    ax.set_ylabel("CLIP distance, model built as trained")
    ax.grid(color="#dddddd", linewidth=0.8)
    from matplotlib.lines import Line2D

    ax.legend(
        [Line2D([0], [0], color=c, marker=m, linestyle="") for _, c, m in presets.values()],
        [name for name, _, _ in presets.values()],
        frameon=False,
        loc="upper left",
    )
    save(
        fig,
        "exp01_clip_before_after",
        "Experiment 1's CLIP distance to the original at the last pass, for each of the 24 "
        "chains, as first measured and as measured again on the corrected model.",
        [
            "data/results/exp01_compression.jsonl",
            "docs/evidence/2026-11-09_exp01_results_wrong_clip_build.jsonl",
        ],
        "A scatter chart with a diagonal 'same value' line. Each dot is one chain.",
    )


def closeups(ledger, detail) -> None:
    """One figure per photograph: rows are journeys, columns are passes, each cell the same
    spot of the scene cut straight from the pipeline's output file."""
    size = 260  # pixels of the pass-1 file shown in a cell
    for stem, (name, (fx, fy)) in PHOTOS.items():
        journeys = [j for j in JOURNEYS if (stem, j) in ledger and (stem, j) in detail]
        if not journeys:
            continue
        first = ledger[(stem, journeys[0])][0]
        g0_path = paths.resolve(first["output_path"])
        if not g0_path.is_file():
            print(f"pictures for {stem} are not on this machine; skipping its close-up")
            continue
        original = Image.open(g0_path).convert("RGB")
        W0, H0 = original.size
        passes = [p for p in SHOWN_PASSES if p in ledger[(stem, journeys[0])]]
        fig, axes = plt.subplots(
            len(journeys),
            len(passes),
            figsize=(2.3 * len(passes) + 2.6, 2.3 * len(journeys) + 0.8),
            layout="constrained",
            squeeze=False,
        )
        for r, j in enumerate(journeys):
            ref_w = ledger[(stem, j)][1]["metrics"]["width"] if 1 in ledger[(stem, j)] else 1080
            for c, p in enumerate(passes):
                ax = axes[r][c]
                ax.set_xticks([])
                ax.set_yticks([])
                row, drow = ledger[(stem, j)].get(p), detail[(stem, j)].get(p)
                if row is None or drow is None:
                    ax.text(0.5, 0.5, "no data", ha="center", va="center", transform=ax.transAxes)
                    continue
                x0, y0, x1, y1 = drow["box"]
                u, v = (fx * W0 - x0) / (x1 - x0), (fy * H0 - y0) / (y1 - y0)
                if not (0 <= u <= 1 and 0 <= v <= 1):
                    ax.set_facecolor("#eeeeee")
                    ax.text(
                        0.5,
                        0.5,
                        "cropped\nout of frame",
                        ha="center",
                        va="center",
                        transform=ax.transAxes,
                        fontsize=11,
                    )
                    continue
                if p == 0:
                    # the same region of the original, resized once to the pass-1 scale
                    k = ref_w / W0
                    img = original.resize((round(W0 * k), round(H0 * k)), Image.Resampling.LANCZOS)
                else:
                    img = Image.open(paths.resolve(row["output_path"])).convert("RGB")
                w, h = img.size
                # how many of this file's pixels cover the piece of scene a cell shows
                span = size * (W0 / (x1 - x0)) * (w / ref_w) if p else size
                cx, cy = u * w, v * h
                left = min(max(0, cx - span / 2), max(0, w - span))
                top = min(max(0, cy - span / 2), max(0, h - span))
                cell = img.crop((round(left), round(top), round(left + span), round(top + span)))
                ax.imshow(np.asarray(cell), interpolation="nearest")
                if r == 0:
                    ax.set_title("original" if p == 0 else f"pass {p}", fontsize=13)
            axes[r][0].set_ylabel(
                JOURNEYS[j][0].replace(" (control)", "\n(control)").replace(", ", ",\n"),
                fontsize=11,
                rotation=0,
                ha="right",
                va="center",
                labelpad=8,
            )
        fig.suptitle(f"{name}: the same spot at every pass", fontsize=15)
        save(
            fig,
            f"closeup_{stem}",
            f"The same spot of '{name}' for each journey and pass. Each cell is cut from the "
            "pipeline's output file with no processing; the 'original' cell is that region of "
            "the original resized once to the size of pass 1. Where the spot is near the edge of "
            "what is left of the frame, the cell shows the nearest part of the frame.",
            [f"data/runs/{EXP}/ (local pictures)", f"data/results/{EXP}_detail.jsonl"],
            f"A grid of close-ups of {name}: one row per journey, one column per pass.",
            kind="jpg",
        )


def six_photographs() -> None:
    """The six starting photographs side by side, named, for the log."""
    files = {s: ROOT / "data" / "originals" / f"{s}.jpg" for s in PHOTOS}
    if not all(f.is_file() for f in files.values()):
        print("the six originals are not all here; skipping six_photographs")
        return
    fig, axes = plt.subplots(1, 6, figsize=(15, 4.2), layout="constrained")
    for ax, (stem, (name, _)) in zip(axes, PHOTOS.items(), strict=True):
        img = Image.open(files[stem]).convert("RGB")
        img.thumbnail((700, 700))  # small copies for the slide; nothing is measured from them
        ax.imshow(np.asarray(img))
        ax.set_title(name.replace(", ", ",\n"), fontsize=12)
        ax.axis("off")
    save(
        fig,
        "six_photographs",
        "The six starting photographs, all taken by the author, shown small.",
        ["data/originals/"],
        "Six photographs in a row: a street of porticoes in Bologna at sunset, the lake at the "
        "Barbican, a low view of the Barbican with a small sign, golden larches in the "
        "Dolomites, the author standing by a car in the Dolomites, and a column reflected in "
        "rippled water.",
        kind="jpg",
    )


def fmt(v, n: int = 4) -> str:
    return "-" if v is None else f"{v:.{n}f}"


def pr(row: dict) -> str:
    return "-" if not row else f"{row.get('rank')}, {fmt(row.get('prob'))}"


def table(ledger, detail, place) -> None:
    last = max((max(c) for c in ledger.values()), default=40)
    print(
        f"\n| photograph | journey | settled at | SSIM 512 px @ {last} | SSIM own size @ {last} | detail kept @ {last} | detail energy @ {last} | frame @ {last} | place rank, prob @ 0 | place rank, prob @ {last} | CLIP dist @ {last} | kB @ 1 |"
    )
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for stem, (name, _) in PHOTOS.items():
        for j, (label, *_rest) in JOURNEYS.items():
            chain = ledger.get((stem, j))
            if not chain:
                continue
            m = chain[last].get("metrics") or {}
            d = (detail.get((stem, j)) or {}).get(last, {})
            pl = place.get((stem, j)) or {}
            p0, pn = pl.get(0, {}), pl.get(last, {})
            kb1 = (chain.get(1, {}).get("metrics") or {}).get("file_bytes")
            print(
                f"| {name} | {label} | {settled_at(chain) or 'never'} | {fmt(m.get('ssim_to_g0'))} | {fmt(d.get('ssim_native'))} | "
                f"{fmt(d.get('detail_kept'))} | {fmt(d.get('detail_energy'))} | {fmt(d.get('frame_kept'))} | {pr(p0)} | {pr(pn)} | "
                f"{fmt(m.get('clip_dist_to_g0'))} | "
                f"{'-' if kb1 is None else round(kb1 / 1000)} |"
            )


def main() -> None:
    ledger = by_chain(read_jsonl(RESULTS / f"{EXP}.jsonl"))
    detail = by_chain(read_jsonl(RESULTS / f"{EXP}_detail.jsonl"))
    place = by_chain(read_jsonl(RESULTS / f"{EXP}_place.jsonl"))
    if not ledger or not detail:
        sys.exit(
            f"Run the experiment first: data/results/{EXP}.jsonl and {EXP}_detail.jsonl are needed."
        )
    with style_context("presentation", palette_name="okabe_ito_on_white"):
        fig_detail(detail)
        fig_settled(ledger)
        fig_two_measures(ledger, detail)
        fig_place_calibration()
        fig_place_passes(place)
        fig_exp01_clip()
        closeups(ledger, detail)
        six_photographs()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "figures.json").write_text(
        json.dumps(DESCRIPTIONS, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    table(ledger, detail, place)


if __name__ == "__main__":
    main()
