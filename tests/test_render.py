from __future__ import annotations

from telephone.models import GenerationRecord, Metrics, stable_hash
from telephone.render import drift_curves


def _rec(gen: int, clip: float | None) -> GenerationRecord:
    return GenerationRecord(
        run_id="r1",
        experiment_id="e",
        chain_id="e__v__img",
        generation=gen,
        station_sequence="platform",
        output_path=f"x/{gen}.jpg",
        output_sha=stable_hash(gen),
        metrics=Metrics(clip_dist_to_g0=clip, hist_dist_to_g0=0.1 * gen),
    )


def test_drift_curves_skip_metric_with_only_generation_zero(tmp_path):
    # CLIP unavailable: g0 is hard-coded to 0.0 and every later generation is None.
    chains = {"e__v__img/r0": [_rec(0, 0.0), _rec(1, None), _rec(2, None)]}
    groups = {"v": chains}
    assert drift_curves(groups, "clip_dist_to_g0", tmp_path / "clip.png", "t") is None
    assert not (tmp_path / "clip.png").exists()
    # the histogram metric has real points and is still drawn
    p = drift_curves(groups, "hist_dist_to_g0", tmp_path / "hist.png", "t")
    assert p is not None and p.exists()
