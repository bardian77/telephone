"""Figures for the 10 November tutorial: experiment 1 (compression only) on the author's photos.

For every photograph this writes two files under docs/tutorial-10nov/figures/:

  contact_<stem>.jpg   rows = the four platform presets, columns = generations 0, 1, 2, 5, 10, 20
  drift_<stem>.png     left: SSIM against generation 0; right: CLIP distance to generation 0 when
                       it was computed, otherwise the JPEG file size

and prints a plain table (markdown) with the numbers the spoken summary quotes.

Everything is read from the run ledger; nothing is recomputed. Run from the repo root:

    .venv/bin/python analysis/tutorial_10nov.py

Design notes (scientific-visualization skill): Okabe-Ito colours plus a distinct marker per
preset, direct end labels, no dual axes, baselines disclosed in the axis labels, fonts sized for a
slide. SSIM panels do not start at zero: SSIM is a similarity in [0, 1] and all values sit above
0.8, so the axis shows the range the data occupies and says so. The four colours were run through
the skill's palette_audit.py against white: every colour clears the 3:1 graphical-contrast
threshold; four of the six pairs sit under the heuristic 10 L* grayscale separation, which is why
colour is never the only cue (markers and labels carry the same distinction).
"""

from __future__ import annotations

import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from PIL import Image  # noqa: E402

from telephone.config import get_settings  # noqa: E402
from telephone.ledger import Ledger  # noqa: E402
from telephone.models import GenerationRecord  # noqa: E402
from telephone.render import image_of, variant_of  # noqa: E402

EXPERIMENT = "exp01_compression"
OUT = Path("docs/tutorial-10nov/figures")
SHOW_GENERATIONS = [0, 1, 2, 5, 10, 20]

# one row per preset, in order of increasing severity on the first pass
VARIANTS = ["whatsapp", "instagram", "screenshot_whatsapp", "harsh"]
VARIANT_LABEL = {
    "whatsapp": "WhatsApp\n1600 px, quality 60",
    "instagram": "Instagram\n1080 px, quality 72",
    "screenshot_whatsapp": "Screenshot, then WhatsApp\n1170 px q80, then 1600 px q60",
    "harsh": "Harsh\n512 px, quality 30",
}
SHORT_LABEL = {
    "whatsapp": "WhatsApp",
    "instagram": "Instagram",
    "screenshot_whatsapp": "Screenshot + WhatsApp",
    "harsh": "Harsh",
}
# Okabe-Ito: blue, vermillion, bluish green, reddish purple. Distinct markers back the colours up.
COLOUR = {
    "whatsapp": "#0072B2",
    "instagram": "#D55E00",
    "screenshot_whatsapp": "#009E73",
    "harsh": "#CC79A7",
}
MARKER = {"whatsapp": "o", "instagram": "s", "screenshot_whatsapp": "^", "harsh": "D"}

PHOTO_TITLE = {
    "street_bologna_portici_01": "Bologna porticoes at sunset (the only vertical photo)",
    "street_barbican_lake_01": "Barbican lake, columns and reflections",
    "landscape_dolomites_larches_01": "Dolomites, golden larches",
    "portrait_dolomites_self_01": "Self-portrait with the car, Dolomites",
    "text_barbican_seddon_house_01": "Barbican, Seddon House signs (small text)",
    "abstract_barbican_reflection_01": "Abstract: a column reflected in rippled water (460 px)",
}

TEXT = "#0b0b0b"
MUTED = "#52514e"
GRID = "#e6e5e1"
SURFACE = "#ffffff"

plt.rcParams.update(
    {
        "font.size": 12,
        "axes.titlesize": 14,
        "axes.labelsize": 12,
        "xtick.labelsize": 11,
        "ytick.labelsize": 11,
        "legend.fontsize": 11,
        "axes.edgecolor": GRID,
        "axes.labelcolor": MUTED,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
    }
)


def load_chains() -> dict[str, dict[str, list[GenerationRecord]]]:
    """{image_stem: {variant: [records sorted by generation]}} for the compression experiment."""
    s = get_settings()
    led = Ledger(s.ledger_path)
    out: dict[str, dict[str, list[GenerationRecord]]] = defaultdict(dict)
    by_chain: dict[str, list[GenerationRecord]] = defaultdict(list)
    for r in led.experiment(EXPERIMENT):
        if r.repeat == 0 and r.error is None:
            by_chain[r.chain_id].append(r)
    for cid, recs in by_chain.items():
        out[image_of(cid)][variant_of(cid)] = sorted(recs, key=lambda r: r.generation)
    return dict(out)


@dataclass
class Stability:
    """How a chain settles after the first pass."""

    fixed_from: int | None  # first generation whose bytes equal the previous generation's
    byte_spread: int  # max - min file size over generations 1..N
    min_ssim_to_prev: float | None  # smallest generation-to-generation SSIM after generation 1

    def note(self) -> str:
        if self.fixed_from is not None:
            return f"byte-identical from g{self.fixed_from}"
        return f"same picture from g1 (files differ by at most {self.byte_spread} bytes)"


def stability(recs: list[GenerationRecord]) -> Stability:
    fixed = None
    for prev, cur in zip(recs, recs[1:], strict=False):
        if cur.output_sha == prev.output_sha:
            fixed = cur.generation
            break
    sizes = [r.metrics.file_bytes for r in recs[1:] if r.metrics.file_bytes is not None]
    prev = [r.metrics.ssim_to_prev for r in recs[2:] if r.metrics.ssim_to_prev is not None]
    return Stability(
        fixed_from=fixed,
        byte_spread=(max(sizes) - min(sizes)) if sizes else 0,
        min_ssim_to_prev=min(prev) if prev else None,
    )


def has_clip(chains: dict[str, list[GenerationRecord]]) -> bool:
    return any(r.metrics.clip_dist_to_g0 is not None for recs in chains.values() for r in recs[1:])


def _kb(n: int | None) -> str:
    return "" if n is None else f"{n / 1000:.0f} kB"


# -- contact sheet ----------------------------------------------------------------------------


def contact_sheet(stem: str, chains: dict[str, list[GenerationRecord]], path: Path) -> Path:
    variants = [v for v in VARIANTS if v in chains]
    rows, cols = len(variants), len(SHOW_GENERATIONS)
    fig = plt.figure(figsize=(13.33, 1.6 + 1.85 * rows), dpi=150)
    grid = fig.add_gridspec(
        rows, cols, left=0.2, right=0.99, top=0.86, bottom=0.03, wspace=0.08, hspace=0.5
    )
    use_clip = has_clip(chains)
    for i, variant in enumerate(variants):
        recs = {r.generation: r for r in chains[variant]}
        for j, g in enumerate(SHOW_GENERATIONS):
            ax = fig.add_subplot(grid[i, j])
            ax.set_axis_off()
            rec = recs.get(g)
            if rec is None or not Path(rec.output_path).exists():
                ax.text(0.5, 0.5, "missing", ha="center", va="center", color=MUTED)
                continue
            img = Image.open(rec.output_path).convert("RGB")
            img.thumbnail((360, 360))
            ax.imshow(img, interpolation="lanczos")
            m = rec.metrics
            if g == 0:
                label = f"original\n{m.width}x{m.height}"
            else:
                first = [f"SSIM {m.ssim_to_g0:.3f}" if m.ssim_to_g0 is not None else ""]
                if use_clip and m.clip_dist_to_g0 is not None:
                    first.append(f"CLIP {m.clip_dist_to_g0:.3f}")
                label = "  ".join(b for b in first if b) + "\n" + _kb(m.file_bytes)
            ax.set_title(label, fontsize=8.5, color=MUTED, pad=2, linespacing=1.3)
        pos = grid[i, 0].get_position(fig)
        st = stability(chains[variant])
        if st.fixed_from is not None:
            note = f"byte-identical from g{st.fixed_from}"
        else:
            note = f"same picture from g1\n(files differ by at most {st.byte_spread} bytes)"
        fig.text(
            0.015,
            pos.y0 + pos.height / 2,
            f"{VARIANT_LABEL[variant]}\n{note}",
            ha="left",
            va="center",
            fontsize=9.5,
            color=TEXT,
            linespacing=1.4,
        )
    for j, g in enumerate(SHOW_GENERATIONS):
        pos = grid[0, j].get_position(fig)
        fig.text(
            pos.x0 + pos.width / 2,
            0.905,
            "generation 0" if g == 0 else f"generation {g}",
            ha="center",
            va="bottom",
            fontsize=11,
            color=TEXT,
        )
    fig.suptitle(
        f"{PHOTO_TITLE.get(stem, stem)}: 20 re-uploads under four platform presets",
        x=0.015,
        ha="left",
        fontsize=14,
        color=TEXT,
        y=0.985,
    )
    sizes = (
        "SSIM: 1 = identical to the original. CLIP: cosine distance, 0 = identical. kB: JPEG size."
    )
    fig.text(0.015, 0.945, sizes, ha="left", fontsize=10, color=MUTED)
    path.parent.mkdir(parents=True, exist_ok=True)
    # JPEG: these sheets are mostly photographs, and a PNG of them is ten times the size
    fig.savefig(path, dpi=150, pil_kwargs={"quality": 88, "optimize": True})
    plt.close(fig)
    return path


# -- drift figure -----------------------------------------------------------------------------


def _original_bytes(stem: str) -> int | None:
    folder = get_settings().originals_dir
    for ext in (".jpg", ".jpeg", ".png"):
        p = folder / f"{stem}{ext}"
        if p.exists():
            return p.stat().st_size
    return None


def _style(ax) -> None:
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.grid(True, axis="y", color=GRID, linewidth=1)
    ax.set_axisbelow(True)
    ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))


def _place_end_labels(ax, x: float, items: list[tuple[float, str, str]]) -> None:
    """Direct labels at the right end of each line, pushed apart so they never overlap.

    items: (y, text, colour). Call after the y limits are final.
    """
    lo, hi = ax.get_ylim()
    gap = (hi - lo) * 0.065
    placed: list[tuple[float, str, str]] = []
    for y, text, colour in sorted(items, key=lambda t: t[0]):
        if placed and y - placed[-1][0] < gap:
            y = placed[-1][0] + gap
        placed.append((y, text, colour))
    # if the stack ran off the top, shift everything down
    overflow = placed[-1][0] - (hi - gap * 0.5) if placed else 0
    for y, text, colour in placed:
        ax.annotate(
            text,
            (x, y - max(0.0, overflow)),
            xytext=(8, 0),
            textcoords="offset points",
            va="center",
            fontsize=10.5,
            color=colour,
            annotation_clip=False,
        )


def drift_figure(stem: str, chains: dict[str, list[GenerationRecord]], path: Path) -> Path:
    variants = [v for v in VARIANTS if v in chains]
    use_clip = has_clip(chains)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.33, 6.0), dpi=150)
    fig.subplots_adjust(left=0.06, right=0.86, top=0.78, bottom=0.2, wspace=0.62)
    _style(ax1)
    _style(ax2)
    ssim_min = 1.0
    left_labels: list[tuple[float, str, str]] = []
    right_labels: list[tuple[float, str, str]] = []
    notes: list[str] = []
    for v in variants:
        recs = chains[v]
        gens = [r.generation for r in recs]
        ssim = [r.metrics.ssim_to_g0 if r.generation else 1.0 for r in recs]
        ssim_min = min(ssim_min, min(x for x in ssim if x is not None))
        marks = [g for g in SHOW_GENERATIONS if g < len(gens)]
        ax1.plot(
            gens,
            ssim,
            color=COLOUR[v],
            marker=MARKER[v],
            markersize=6,
            linewidth=2,
            markevery=marks,
        )
        left_labels.append((ssim[-1], SHORT_LABEL[v], COLOUR[v]))
        if use_clip:
            right = [r.metrics.clip_dist_to_g0 if r.generation else 0.0 for r in recs]
        else:
            right = [
                (_original_bytes(stem) if r.generation == 0 else r.metrics.file_bytes) for r in recs
            ]
            right = [x / 1000 if x is not None else None for x in right]
        pts = [(g, x) for g, x in zip(gens, right, strict=True) if x is not None]
        if pts:
            ax2.plot(
                [g for g, _ in pts],
                [x for _, x in pts],
                color=COLOUR[v],
                marker=MARKER[v],
                markersize=6,
                linewidth=2,
                markevery=[i for i, (g, _) in enumerate(pts) if g in SHOW_GENERATIONS],
            )
            right_labels.append((pts[-1][1], SHORT_LABEL[v], COLOUR[v]))
        notes.append(f"{SHORT_LABEL[v]}: {stability(recs).note()}")
    lo = max(0.0, (ssim_min // 0.05) * 0.05 - 0.05)
    ax1.set_ylim(lo, 1.005)
    ax1.set_xlim(-0.5, 20.5)
    ax1.set_xlabel("generation (re-uploads)")
    ax1.set_ylabel(f"SSIM against generation 0 (axis starts at {lo:.2f}, not 0)")
    ax1.set_title("How much structure is left", loc="left", color=TEXT)
    _place_end_labels(ax1, 20, left_labels)
    ax2.set_xlim(-0.5, 20.5)
    ax2.set_xlabel("generation (re-uploads)")
    ax2.set_ylim(bottom=0)
    if use_clip:
        ax2.set_ylabel("CLIP cosine distance to generation 0 (0 = identical)")
        ax2.set_title("How far the picture has drifted (CLIP)", loc="left", color=TEXT)
    else:
        ax2.set_ylabel("JPEG file size, kB (generation 0 = the original file)")
        ax2.set_title("How much of the file is left", loc="left", color=TEXT)
    _place_end_labels(ax2, 20, right_labels)
    fig.suptitle(
        f"{PHOTO_TITLE.get(stem, stem)}: compression only, 20 generations",
        x=0.06,
        ha="left",
        fontsize=14,
        color=TEXT,
        y=0.97,
    )
    fig.text(
        0.06,
        0.885,
        "One line per platform preset. Generation 0 is the original. Markers at the generations "
        "shown on the contact sheet.",
        ha="left",
        fontsize=10.5,
        color=MUTED,
    )
    fig.text(
        0.06,
        0.035,
        "After the first pass:  " + "   ".join(notes),
        ha="left",
        fontsize=9.5,
        color=MUTED,
        wrap=True,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


# -- table ------------------------------------------------------------------------------------


def table(chains_by_image: dict[str, dict[str, list[GenerationRecord]]]) -> str:
    lines = [
        "| photo | preset | size after g1 | SSIM g1 | SSIM g20 | CLIP g1 | CLIP g20 | LPIPS g20 "
        "| kB original -> g1 | after g1 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]

    def f(x: float | None, nd: int = 3) -> str:
        return "" if x is None else f"{x:.{nd}f}"

    for stem in PHOTO_TITLE:
        chains = chains_by_image.get(stem)
        if not chains:
            continue
        for v in VARIANTS:
            recs = chains.get(v)
            if not recs:
                continue
            by = {r.generation: r for r in recs}
            g1, gl = by.get(1), by.get(max(by))
            st = stability(recs)
            lines.append(
                f"| {stem} | {SHORT_LABEL[v]} | {g1.metrics.width}x{g1.metrics.height} | "
                f"{f(g1.metrics.ssim_to_g0)} | {f(gl.metrics.ssim_to_g0)} | "
                f"{f(g1.metrics.clip_dist_to_g0)} | {f(gl.metrics.clip_dist_to_g0)} | "
                f"{f(gl.metrics.lpips_to_g0)} | "
                f"{(_original_bytes(stem) or 0) / 1000:.0f} -> {g1.metrics.file_bytes / 1000:.0f} | "
                f"{st.note()} |"
            )
    return "\n".join(lines)


def main(out: Path = OUT) -> list[Path]:
    chains_by_image = load_chains()
    if not chains_by_image:
        sys.exit(
            f"no rows for {EXPERIMENT} in the ledger; run `telephone run-experiment exp01 --no-extract`"
        )
    written: list[Path] = []
    for stem, chains in sorted(chains_by_image.items()):
        written.append(contact_sheet(stem, chains, out / f"contact_{stem}.jpg"))
        written.append(drift_figure(stem, chains, out / f"drift_{stem}.png"))
    print(table(chains_by_image))
    print()
    for p in written:
        print("wrote", p)
    return written


if __name__ == "__main__":
    main()
