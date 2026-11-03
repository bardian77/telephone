from __future__ import annotations

import csv

from telephone.metrics.survival import THRESHOLDS
from telephone.validate import agreement_report, spearman


def test_spearman():
    assert spearman([1, 2, 3, 4], [10, 20, 30, 40]) == 1.0
    assert spearman([1, 2, 3, 4], [4, 3, 2, 1]) == -1.0
    assert spearman([1, 2], [2, 1]) is None


def test_agreement_report(tmp_path):
    p = tmp_path / "labels.csv"
    fields = list(THRESHOLDS)
    head = [
        "key",
        "generation",
        "similarity",
        "clip_dist_to_g0",
        "hist_dist_to_g0",
        "ssim_to_g0",
        *[f"hand_{f}" for f in fields],
        *[f"auto_{f}" for f in fields],
        "ts",
    ]
    with p.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(head)
        for i in range(6):
            sim = 5 - i % 5
            w.writerow(
                [
                    f"c{i}",
                    i + 1,
                    sim,
                    0.1 * i,
                    0.15 * i,
                    1 - 0.1 * i,
                    *[1 if sim > 2 else 0 for _ in fields],
                    *[1 if sim > 3 else 0 for _ in fields],
                    "t",
                ]
            )
        w.writerow(["skip", 1, 0, "", "", "", *["" for _ in fields], *["" for _ in fields], "t"])
    out = tmp_path / "report.md"
    text = agreement_report(p, out)
    assert out.exists() and "6 labelled pairs" in text
    assert "| clip_dist_to_g0 | 6 | -0." in text
    assert "| objects | 6 |" in text
