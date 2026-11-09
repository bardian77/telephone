"""Regenerate every figure the log and README use, from the ledger. Run: python analysis/figures.py"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from telephone.config import get_settings  # noqa: E402
from telephone.ledger import Ledger  # noqa: E402
from telephone.render import (  # noqa: E402
    CATEGORICAL,
    SURFACE,
    TEXT_SECONDARY,
    _mean_curve,
    _series,
    _style,
    group_chains,
    render_all,
)

OUT = Path("data/figures")


def cross_experiment(ledger: Ledger, out: Path) -> Path | None:
    """One chart: mean CLIP drift per experiment, so compression vs AI vs physical sit on one axis."""
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150, facecolor=SURFACE)
    _style(ax)
    drawn = 0
    for i, row in enumerate(ledger.experiments()):
        eid = row["experiment_id"]
        if eid.startswith("exp00") or eid == "adhoc":
            continue
        chains = {
            k: v
            for g in group_chains(ledger.experiment(eid), "variant").values()
            for k, v in g.items()
        }
        series = _series(chains, "clip_dist_to_g0") or _series(chains, "hist_dist_to_g0")
        if not series:
            continue
        mean = _mean_curve(list(series.values()))
        ax.plot(
            [g for g, _, _ in mean],
            [m for _, m, _ in mean],
            color=CATEGORICAL[i % 8],
            linewidth=2,
            marker="o",
            markersize=4,
            label=f"{eid} (n={len(series)})",
        )
        drawn += 1
    if not drawn:
        plt.close(fig)
        return None
    ax.set_xlabel("generation")
    ax.set_ylabel("mean distance to generation 0")
    ax.set_title("Drift across experiments", loc="left", fontsize=11)
    ax.legend(frameon=False, fontsize=8, labelcolor=TEXT_SECONDARY)
    fig.tight_layout()
    p = out / "cross_experiment_drift.png"
    fig.savefig(p, facecolor=SURFACE)
    plt.close(fig)
    return p


if __name__ == "__main__":
    s = get_settings()
    written = render_all(None, OUT)
    led = Ledger(s.ledger_path)
    p = cross_experiment(led, OUT)
    if p:
        written.append(p)
    print(json.dumps({"figures": len(written), "folder": str(OUT)}))
