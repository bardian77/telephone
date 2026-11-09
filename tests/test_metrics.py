from __future__ import annotations

import pytest
from PIL import ImageFilter

from telephone.imageio import load_image, to_jpeg_bytes, to_png_bytes
from telephone.metrics import (
    compare_attributes,
    face_count,
    first_failure,
    histogram_distance,
    ssim_score,
)
from telephone.models import Attributes


def test_histogram_distance(test_image):
    img = load_image(test_image)
    a = to_png_bytes(img)
    assert histogram_distance(a, a) == pytest.approx(0.0, abs=1e-6)
    b = to_png_bytes(img.filter(ImageFilter.GaussianBlur(8)))
    inverted = to_png_bytes(__import__("PIL.ImageOps", fromlist=["invert"]).invert(img))
    assert 0 < histogram_distance(a, b) < histogram_distance(a, inverted) <= 1.0


def test_ssim_monotone_with_quality(test_image):
    img = load_image(test_image)
    ref = to_png_bytes(img)
    scores = [ssim_score(ref, to_jpeg_bytes(img, quality=q)) for q in (95, 50, 10)]
    assert ssim_score(ref, ref) == pytest.approx(1.0, abs=1e-6)
    assert scores[0] > scores[1] > scores[2]


def test_face_count_runs(test_image):
    n = face_count(to_png_bytes(load_image(test_image)))
    assert n is None or n >= 0


def attrs(**kw) -> Attributes:
    base = dict(
        objects=["red car", "lamp post", "dog"],
        people_count=2,
        visible_text=["OPEN"],
        setting="busy city street at night",
        lighting="night",
        mood="hectic",
        dominant_colors=["red", "black", "grey"],
        camera_angle="eye level",
        is_photograph=True,
    )
    base.update(kw)
    return Attributes(**base)


def test_survival_identical_all_alive():
    s = compare_attributes(attrs(), attrs())
    assert s.alive_count == s.total == 9 and s.fraction == 1.0


def test_survival_rules():
    now = attrs(
        objects=["car", "dogs", "bicycle"],
        people_count=3,
        visible_text=[],
        setting="quiet harbour",
        lighting="daylight",
        mood="calm",
        dominant_colors=["blue", "white"],
        camera_angle="aerial",
        is_photograph=False,
    )
    s = compare_attributes(attrs(), now)
    f = s.fields
    assert f["objects"].alive  # car and dog survive via head nouns / singularisation
    assert not f["people_count"].alive and f["people_count"].score == pytest.approx(2 / 3, abs=1e-3)
    assert not f["visible_text"].alive and f["visible_text"].score == 0
    assert not f["setting"].alive and not f["lighting"].alive and not f["mood"].alive
    assert (
        not f["dominant_colors"].alive
        and not f["camera_angle"].alive
        and not f["is_photograph"].alive
    )
    assert s.alive_count == 1


def test_first_failure():
    g0 = attrs()
    chain = [
        compare_attributes(g0, g0),
        compare_attributes(g0, attrs(lighting="daylight")),
        None,
        compare_attributes(g0, attrs(lighting="daylight", mood="calm")),
    ]
    ff = first_failure(chain)
    assert ff["lighting"] == 1 and ff["mood"] == 3 and ff["objects"] is None


def test_face_count_survives_a_broken_cv2(monkeypatch, test_image):
    """A cv2 build without CascadeClassifier must give None, not take the chain down."""
    import sys
    import types

    from telephone.metrics import readability

    monkeypatch.setitem(sys.modules, "cv2", types.SimpleNamespace(data=types.SimpleNamespace()))
    monkeypatch.setattr(readability, "_cascade", None)
    monkeypatch.setattr(readability, "_face_failed", False)
    assert readability.face_count(to_png_bytes(load_image(test_image))) is None
    assert readability._face_failed is True
