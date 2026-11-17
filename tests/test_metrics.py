from __future__ import annotations

import sys
import types
import warnings

import pytest
from PIL import ImageFilter

from telephone.imageio import load_image, to_jpeg_bytes, to_png_bytes
from telephone.metrics import (
    ClipEmbedder,
    MetricsUnavailable,
    compare_attributes,
    face_count,
    first_failure,
    histogram_distance,
    ssim_score,
)
from telephone.metrics.embed import describe_preprocessing
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


# -- CLIP is built the way its weights were trained ------------------------------------------------


class Resize:
    """Stands in for the step of the same name in CLIP's preparation of a picture."""

    def __init__(self, size):
        self.size = size


class CenterCrop(Resize):
    pass


def steps(*transforms) -> types.SimpleNamespace:
    """The steps a model applies to a picture, in the shape open_clip hands them over in."""
    return types.SimpleNamespace(transforms=list(transforms))


def use_fake_open_clip(monkeypatch) -> list[dict]:
    """Put stand-ins for open_clip and torch in place, so no weights and no network are needed.

    The stand-in copies the one thing that matters here. OpenAI's weights were trained with an
    activation called QuickGELU. open_clip builds the plain "ViT-B-32" network with GELU unless
    it is asked for QuickGELU, and when the two do not match it only warns. Returns the list
    that every request for a model is written to.
    """
    calls: list[dict] = []
    activations = {True: type("QuickGELU", (), {}), False: type("GELU", (), {})}

    class FakeModel:
        def __init__(self, quick_gelu: bool):
            self.quick_gelu = quick_gelu

        def eval(self):
            return self

        def modules(self):
            return [activations[self.quick_gelu]()]

    def get_pretrained_cfg(model: str, tag: str) -> dict:
        return {"quick_gelu": True} if tag == "openai" else {}

    def create_model_and_transforms(model_name, pretrained=None, force_quick_gelu=False):
        calls.append(
            {"model_name": model_name, "pretrained": pretrained, "quick_gelu": force_quick_gelu}
        )
        built_quick = force_quick_gelu or model_name.endswith("-quickgelu")
        trained_quick = bool(get_pretrained_cfg(model_name, pretrained).get("quick_gelu"))
        if built_quick != trained_quick:
            warnings.warn(
                f"QuickGELU mismatch between final model config (quick_gelu={built_quick}) "
                f"and pretrained tag '{pretrained}' (quick_gelu={trained_quick}).",
                UserWarning,
                stacklevel=2,
            )
        return FakeModel(built_quick), None, steps(Resize(224), CenterCrop((224, 224)))

    fake = types.SimpleNamespace(
        __version__="9.9.9",
        create_model_and_transforms=create_model_and_transforms,
        get_pretrained_cfg=get_pretrained_cfg,
    )
    monkeypatch.setitem(sys.modules, "open_clip", fake)
    monkeypatch.setitem(sys.modules, "torch", types.SimpleNamespace(set_num_threads=lambda n: None))
    monkeypatch.delenv("TELEPHONE_CLIP_MODEL", raising=False)
    monkeypatch.delenv("TELEPHONE_CLIP_PRETRAINED", raising=False)
    return calls


def test_clip_is_built_with_the_activation_its_weights_were_trained_with(monkeypatch):
    calls = use_fake_open_clip(monkeypatch)
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # the mismatch warning would fail this test
        embedder = ClipEmbedder()
    assert calls == [{"model_name": "ViT-B-32", "pretrained": "openai", "quick_gelu": True}]
    assert embedder.activation == "quickgelu"


def test_clip_refuses_a_network_whose_activation_does_not_match_its_weights(monkeypatch):
    use_fake_open_clip(monkeypatch)
    # a QuickGELU network with weights that were not trained with it: the mismatch the other way
    with pytest.raises(MetricsUnavailable, match="QuickGELU mismatch"):
        ClipEmbedder("ViT-B-32-quickgelu", "laion2b_s34b_b79k")


def test_clip_built_with_plain_gelu_for_weights_trained_that_way_says_so(monkeypatch):
    calls = use_fake_open_clip(monkeypatch)
    embedder = ClipEmbedder("ViT-B-32", "laion2b_s34b_b79k")
    assert calls[0]["quick_gelu"] is False
    assert embedder.activation == "gelu"


def test_clip_says_which_version_of_the_library_built_it(monkeypatch):
    # part of the label written into results, so two builds can never share a label
    use_fake_open_clip(monkeypatch)
    assert ClipEmbedder().library == "open_clip-9.9.9"


def test_what_clip_does_to_a_picture_first_is_read_off_its_own_steps(monkeypatch):
    """CLIP's standard preparation makes the shorter side 224 px and keeps the central 224 px
    square, so the model never sees what lies outside that square. Results record this, and
    it is read off the steps that really run, not assumed."""
    standard = steps(Resize(224), CenterCrop((224, 224)), object())
    assert describe_preprocessing(standard) == "central square at 224 px"
    assert describe_preprocessing(steps(Resize(336), CenterCrop((336, 336)))) == (
        "central square at 336 px"
    )
    # anything else is not described by guesswork: the whole picture squashed into a square,
    # a crop that is not the square the resize aimed at, or no steps at all
    assert describe_preprocessing(steps(Resize((224, 224)))) == "not known"
    assert describe_preprocessing(steps(Resize(256), CenterCrop((224, 224)))) == "not known"
    assert describe_preprocessing(None) == "not known"

    use_fake_open_clip(monkeypatch)
    assert ClipEmbedder().preprocessing == "central square at 224 px"


@pytest.mark.slow
def test_real_clip_is_built_with_quickgelu_and_without_a_mismatch_warning():
    """Needs the CLIP weights, so it is skipped by default.

    The real check behind the three tests above: with the installed open_clip, the default
    model must come out with the activation OpenAI trained it with, and open_clip must have
    nothing to warn about.
    """
    with warnings.catch_warnings():
        warnings.filterwarnings("error", message="QuickGELU mismatch")
        embedder = ClipEmbedder()
    kinds = {type(m).__name__ for m in embedder.model.modules() if "GELU" in type(m).__name__}
    assert kinds == {"QuickGELU"}
    assert embedder.activation == "quickgelu"


@pytest.mark.slow
def test_real_clip_only_sees_the_central_square_of_a_picture():
    """Needs the CLIP weights, so it is skipped by default.

    A picture twice as wide as it is tall, with noise in the middle and plain colour either
    side. What the network is given is exactly what it is given for the middle square alone.
    """
    import numpy as np
    from PIL import Image

    embedder = ClipEmbedder.shared()
    assert embedder.preprocessing == "central square at 224 px"
    noise = np.random.default_rng(0).integers(0, 256, (224, 224, 3), dtype=np.uint8)
    wide = Image.new("RGB", (448, 224), (255, 0, 0))
    wide.paste(Image.fromarray(noise, "RGB"), (112, 0))
    seen = embedder.preprocess(wide)
    assert tuple(seen.shape) == (3, 224, 224)
    assert bool((seen == embedder.preprocess(wide.crop((112, 0, 336, 224)))).all())
