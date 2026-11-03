"""Agreement between hand labels (from the website's Label page) and the automated measures.

labels.csv columns: key, generation, similarity (1-5, 0 = skipped), clip_dist_to_g0, hist_dist_to_g0,
ssim_to_g0, hand_<field> (0/1), auto_<field> (0/1 or blank), ts.

Reports: Spearman rank correlation between the hand similarity score and each distance (expected
negative: more distance, less similar), and per-field precision, recall and agreement of the
automated survival call against the hand call.
"""

from __future__ import annotations

import csv
from pathlib import Path

from .metrics.survival import THRESHOLDS


def _rank(xs: list[float]) -> list[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        r = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = r
        i = j + 1
    return ranks


def spearman(x: list[float], y: list[float]) -> float | None:
    if len(x) < 3:
        return None
    rx, ry = _rank(x), _rank(y)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry, strict=True))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / den if den else None


def agreement_report(labels_csv: Path, out_md: Path | None = None) -> str:
    with Path(labels_csv).open(encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if r.get("similarity") not in (None, "", "0")]
    if not rows:
        return "No labels found."
    lines = [
        "# Validation: hand labels vs automated measures\n",
        f"{len(rows)} labelled pairs from `{labels_csv}`.\n",
        "## Drift metrics vs 'is this still the same picture?' (1 to 5)\n",
        "| metric | n | Spearman rho |",
        "|---|---:|---:|",
    ]
    for col in ("clip_dist_to_g0", "hist_dist_to_g0", "ssim_to_g0"):
        pairs = [
            (float(r[col]), float(r["similarity"])) for r in rows if r.get(col) not in (None, "")
        ]
        rho = spearman([p[0] for p in pairs], [p[1] for p in pairs]) if pairs else None
        lines.append(f"| {col} | {len(pairs)} | {'n/a' if rho is None else f'{rho:+.2f}'} |")
    lines += [
        "",
        "Expected sign: negative for distances (more distance, lower similarity), positive for SSIM.",
        "",
        "## Survival: automated alive/dead vs hand label per attribute\n",
        "| attribute | n | agreement | precision | recall |",
        "|---|---:|---:|---:|---:|",
    ]
    for f in THRESHOLDS:
        pairs = [
            (r[f"hand_{f}"] == "1", r[f"auto_{f}"] == "1")
            for r in rows
            if r.get(f"auto_{f}") not in (None, "")
        ]
        if not pairs:
            lines.append(f"| {f} | 0 | n/a | n/a | n/a |")
            continue
        tp = sum(1 for h, a in pairs if h and a)
        fp = sum(1 for h, a in pairs if not h and a)
        fn = sum(1 for h, a in pairs if h and not a)
        agree = sum(1 for h, a in pairs if h == a) / len(pairs)
        prec = tp / (tp + fp) if tp + fp else float("nan")
        rec = tp / (tp + fn) if tp + fn else float("nan")
        lines.append(f"| {f} | {len(pairs)} | {agree:.0%} | {prec:.0%} | {rec:.0%} |")
    lines += [
        "",
        "Precision: when the pipeline says an attribute survived, how often I agreed. Recall: of the attributes I judged alive, how many the pipeline also called alive.",
    ]
    text = "\n".join(lines) + "\n"
    if out_md:
        Path(out_md).parent.mkdir(parents=True, exist_ok=True)
        Path(out_md).write_text(text, encoding="utf-8")
    return text
