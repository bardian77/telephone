"""The place line-up: where does the true place come in a line-up of candidate names?

Every test here uses a fake embedder whose vectors are built by hand, so the expected rank,
probability and ladder numbers can be worked out on paper. Nothing touches the network or the
real CLIP weights, except the one test marked slow.
"""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import yaml
from PIL import Image
from typer.testing import CliRunner

from telephone.cli import app
from telephone.config import get_settings
from telephone.imageio import load_image, sha256_bytes, to_png_bytes
from telephone.ledger import Ledger
from telephone.metrics.embed import ClipEmbedder, MetricsUnavailable
from telephone.metrics.place import (
    BANNED_WORDS,
    TEMPLATES,
    PlaceEntry,
    banned_words_in,
    calibrate_places,
    load_places,
    model_label,
    place_vector,
    provenance,
    registered_sha,
    round_floats,
    score_ladder,
    score_lineup,
    score_place,
)
from telephone.models import GenerationRecord

REPO = Path(__file__).resolve().parents[1]
runner = CliRunner()


def unit(deg: float) -> np.ndarray:
    """A 2-D unit vector at this angle.

    The cosine similarity of two of them is the cosine of the angle between them, so a picture at
    0 degrees and a place name at 60 degrees have similarity cos(60) = 0.5.
    """
    r = math.radians(deg)
    return np.array([math.cos(r), math.sin(r)])


def cos(deg: float) -> float:
    return math.cos(math.radians(deg))


def with_similarity(sim: float) -> np.ndarray:
    """A unit vector whose similarity to a picture at 0 degrees is exactly `sim`."""
    return np.array([sim, math.sqrt(1.0 - sim * sim)])


PICTURE = unit(0)


class FakeEmbedder:
    """Stands in for ClipEmbedder: looks vectors up in two dictionaries instead of running CLIP."""

    model_name = "fake"
    pretrained = "by-hand"
    preprocessing = "none: vectors written by hand"

    def __init__(self, texts: dict[str, np.ndarray], images: dict[bytes, np.ndarray] | None = None):
        self.texts = texts
        self.images = images or {}
        self.text_calls: list[str] = []
        self.image_calls: list[bytes] = []

    def embed(self, image: bytes) -> np.ndarray:
        self.image_calls.append(image)
        return self.images[image]

    def embed_text(self, text: str) -> np.ndarray:
        self.text_calls.append(text)
        return self.texts[text]


def texts_for(angles: dict[str, float], templates: tuple[str, ...] = TEMPLATES) -> dict:
    """Every template of a label points the same way, so the ensemble is that same vector."""
    return {t.format(place=label): unit(deg) for label, deg in angles.items() for t in templates}


# -- prompt ensembling ----------------------------------------------------------------------------


def test_templates_are_a_small_fixed_set_with_one_place_slot():
    assert 2 <= len(TEMPLATES) <= 5
    assert "{place}" in TEMPLATES  # the bare name on its own is one of the wordings
    assert all(t.count("{place}") == 1 for t in TEMPLATES)


def test_place_vector_averages_the_templates_and_renormalises():
    templates = ("in {place}", "{place}")
    fake = FakeEmbedder({"in Bologna, Italy": unit(0), "Bologna, Italy": unit(60)})
    vec = place_vector(fake, "Bologna, Italy", templates)
    # the average of two unit vectors, made unit length again, is the direction halfway between
    assert np.allclose(vec, unit(30))
    assert np.linalg.norm(vec) == pytest.approx(1.0)
    # so its similarity to a picture at 0 degrees is cos(30) = 0.866. Averaging the two
    # similarities instead (1.0 and 0.5), or forgetting to renormalise, would both give 0.75.
    assert float(np.dot(vec, unit(0))) == pytest.approx(0.8660, abs=1e-4)


def test_text_embeddings_are_remembered_for_the_life_of_the_process():
    fake = FakeEmbedder(texts_for({"Bologna, Italy": 10}))
    first = place_vector(fake, "Bologna, Italy")
    second = place_vector(fake, "Bologna, Italy")
    assert np.allclose(first, second)
    assert sorted(fake.text_calls) == sorted(t.format(place="Bologna, Italy") for t in TEMPLATES)
    # a second embedder is a different model: it gets its own answers, not the remembered ones
    other = FakeEmbedder(texts_for({"Bologna, Italy": 50}))
    assert np.allclose(place_vector(other, "Bologna, Italy"), unit(50))


# -- the line-up: rank, probability, top candidate ------------------------------------------------

A, B, C = "Aville, Testland", "Beeton, Testland", "Ceeham, Testland"
BARE = ("{place}",)  # one wording only, so the numbers below are plain similarities


def lineup_fake(sim_a: float, sim_b: float, sim_c: float) -> FakeEmbedder:
    return FakeEmbedder(
        {A: with_similarity(sim_a), B: with_similarity(sim_b), C: with_similarity(sim_c)}
    )


def test_lineup_rank_prob_and_top_in_a_clear_case():
    # similarities 0.30, 0.29, 0.28 become logits 30, 29, 28 (CLIP's scale of 100). The softmax
    # of those is e^0 : e^-1 : e^-2, which is 0.6652, 0.2447, 0.0900.
    fake = lineup_fake(0.30, 0.29, 0.28)
    first = score_lineup(PICTURE, (A, B, C), A, fake, BARE)
    assert first["rank"] == 1
    assert first["top"] == A
    assert first["prob"] == pytest.approx(0.6652, abs=1e-4)
    second = score_lineup(PICTURE, (A, B, C), B, fake, BARE)
    assert second["rank"] == 2 and second["top"] == A
    assert second["prob"] == pytest.approx(0.2447, abs=1e-4)
    last = score_lineup(PICTURE, (A, B, C), C, fake, BARE)
    assert last["rank"] == 3 and last["top"] == A
    assert last["prob"] == pytest.approx(0.0900, abs=1e-4)


def test_lineup_names_the_rival_and_the_margin_over_it():
    # The rival is the best candidate other than the true place. The margin is the true place's
    # similarity minus the rival's: positive when the true place is ahead, negative when behind.
    fake = lineup_fake(0.30, 0.29, 0.28)
    ahead = score_lineup(PICTURE, (A, B, C), A, fake, BARE)
    assert ahead["rival"] == B  # rank 1: the rival is the runner-up
    assert ahead["margin"] == pytest.approx(0.01)
    behind = score_lineup(PICTURE, (A, B, C), B, fake, BARE)
    assert behind["rival"] == A  # rank 2: the rival is the candidate ranked first
    assert behind["margin"] == pytest.approx(-0.01)
    last = score_lineup(PICTURE, (A, B, C), C, fake, BARE)
    assert last["rival"] == A and last["margin"] == pytest.approx(-0.02)
    # an exact tie is a margin of nothing, and the true place is not ranked first
    tie = score_lineup(PICTURE, (A, B, C), A, lineup_fake(0.30, 0.30, 0.28), BARE)
    assert (tie["rank"], tie["rival"], tie["margin"]) == (2, B, pytest.approx(0.0))


def test_lineup_order_in_the_file_does_not_decide_the_rank():
    fake = lineup_fake(0.10, 0.20, 0.30)
    res = score_lineup(PICTURE, (A, B, C), C, fake, BARE)
    assert res["rank"] == 1 and res["top"] == C
    # logits 10, 20, 30: the winner has 1 / (1 + e^-10 + e^-20) = 0.99995
    assert res["prob"] == pytest.approx(0.99995, abs=1e-5)


def test_an_exact_tie_counts_against_the_true_place():
    # A and B match the picture equally well. Rank 1 must mean the true place beat every other
    # candidate outright, so a tie is rank 2 and the other candidate is reported as top.
    fake = lineup_fake(0.30, 0.30, 0.28)
    for true, other in ((A, B), (B, A)):
        res = score_lineup(PICTURE, (A, B, C), true, fake, BARE)
        assert res["rank"] == 2
        assert res["top"] == other
        assert res["prob"] == pytest.approx(1 / (2 + math.exp(-2)), abs=1e-6)  # 0.4683


def test_a_near_tie_gives_rank_two_and_almost_half_the_probability():
    # the true place is 0.001 behind: logits 29.9 against 30 and 28
    fake = lineup_fake(0.299, 0.300, 0.280)
    res = score_lineup(PICTURE, (A, B, C), A, fake, BARE)
    assert res["rank"] == 2 and res["top"] == B
    expected = math.exp(-0.1) / (math.exp(-0.1) + 1 + math.exp(-2))  # 0.4435
    assert res["prob"] == pytest.approx(expected, abs=1e-6)
    assert res["prob"] == pytest.approx(0.4435, abs=1e-4)


def test_per_template_ranks_show_when_the_wording_decides():
    # angles from the picture, per wording:   "in {place}"   "{place}"   ensemble (halfway)
    #   A (the true place)                        10            70           40
    #   B                                         30            30           30
    #   C                                         50            50           50
    templates = ("in {place}", "{place}")
    fake = FakeEmbedder(
        {
            f"in {A}": unit(10),
            A: unit(70),
            f"in {B}": unit(30),
            B: unit(30),
            f"in {C}": unit(50),
            C: unit(50),
        }
    )
    res = score_lineup(PICTURE, (A, B, C), A, fake, templates)
    assert res["per_template_rank"] == {"in {place}": 1, "{place}": 3}
    assert res["rank"] == 2 and res["top"] == B  # the ensemble sits between the two wordings


def test_lineup_refuses_a_true_place_that_is_not_a_candidate():
    fake = lineup_fake(0.3, 0.2, 0.1)
    with pytest.raises(ValueError, match="not in the line-up"):
        score_lineup(PICTURE, (A, B), C, fake, BARE)


def test_lineup_refuses_a_lineup_with_nothing_to_compare_the_true_place_with():
    with pytest.raises(ValueError, match="at least one other candidate"):
        score_lineup(PICTURE, (A,), A, lineup_fake(0.3, 0.2, 0.1), BARE)


# -- the ladder: from the specific place to a generic kind of place -------------------------------

LADDER = ("Aville, Testland", "Testland", "Europe", "a city")


def ladder_fake(*sims: float) -> FakeEmbedder:
    return FakeEmbedder(
        {label: with_similarity(sim) for label, sim in zip(LADDER, sims, strict=True)}
    )


def test_ladder_gives_a_similarity_per_rung_the_best_rung_and_the_margin():
    res = score_ladder(PICTURE, LADDER, ladder_fake(0.30, 0.26, 0.24, 0.27), BARE)
    assert [r["label"] for r in res["ladder"]] == list(LADDER)  # specific first, generic last
    assert [r["sim"] for r in res["ladder"]] == pytest.approx([0.30, 0.26, 0.24, 0.27])
    assert res["best_rung"] == "Aville, Testland"
    # first rung minus last rung: 0.30 - 0.27
    assert res["specific_minus_generic"] == pytest.approx(0.03)


def test_ladder_margin_is_negative_when_the_generic_rung_matches_best():
    # a picture that the generic phrase fits better than the name of the place
    res = score_ladder(PICTURE, LADDER, ladder_fake(0.20, 0.22, 0.21, 0.28), BARE)
    assert res["best_rung"] == "a city"
    assert res["specific_minus_generic"] == pytest.approx(-0.08)


def test_ladder_rungs_are_ensembled_like_the_lineup():
    templates = ("in {place}", "{place}")
    fake = FakeEmbedder(
        {
            "in Aville, Testland": unit(0),
            "Aville, Testland": unit(60),
            "in a city": unit(40),
            "a city": unit(40),
        }
    )
    res = score_ladder(PICTURE, ("Aville, Testland", "a city"), fake, templates)
    assert [r["sim"] for r in res["ladder"]] == pytest.approx([cos(30), cos(40)])
    assert res["specific_minus_generic"] == pytest.approx(cos(30) - cos(40))  # 0.866 - 0.766


# -- data/places.yaml: loading and the rules it must obey -----------------------------------------

TOWNS = [
    f"{name}, Testland"
    for name in (
        "Aville",
        "Beeton",
        "Ceeham",
        "Deeford",
        "Eeby",
        "Effton",
        "Geewick",
        "Aitchley",
        "Eyeburn",
        "Jayborough",
    )
]
GOOD_FILE = {
    "lineups": {"towns": TOWNS},
    "photographs": {
        "street_test_01": {
            "place": "Aville, Testland",
            "lineup": "towns",
            "ladder": ["Aville, Testland", "Testland", "a city"],
        }
    },
    "changes": [],
}


def write_places(path: Path, doc: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    return path


def test_load_places_gives_one_entry_per_photograph(tmp_path):
    places = load_places(write_places(tmp_path / "places.yaml", GOOD_FILE))
    assert list(places) == ["street_test_01"]
    assert places["street_test_01"] == PlaceEntry(
        image="street_test_01",
        place="Aville, Testland",
        lineup_name="towns",
        lineup=tuple(TOWNS),
        ladder=("Aville, Testland", "Testland", "a city"),
        negative_control=False,
    )


def test_load_places_reads_the_negative_control_flag(tmp_path):
    doc = copy.deepcopy(GOOD_FILE)
    doc["photographs"]["street_test_01"]["negative_control"] = True
    places = load_places(write_places(tmp_path / "places.yaml", doc))
    assert places["street_test_01"].negative_control is True


def _towns_with(index: int, label: str) -> list[str]:
    return [label if i == index else t for i, t in enumerate(TOWNS)]


BAD_FILES = {
    "true place missing from its line-up": (
        {"photographs": {"street_test_01": {"place": "Zedville, Testland"}}},
        "not in line-up",
    ),
    "nine candidates": ({"lineups": {"towns": TOWNS[:9]}}, "10 to 12"),
    "thirteen candidates": (
        {"lineups": {"towns": [*TOWNS, "Kayham, Testland", "Elby, Testland", "Emton, Testland"]}},
        "10 to 12",
    ),
    "a candidate listed twice": (
        {"lineups": {"towns": _towns_with(9, "aville, testland")}},
        "twice",
    ),
    "template text in a candidate": (
        {"lineups": {"towns": _towns_with(9, "a photo taken in Jayborough, Testland")}},
        "bare place name",
    ),
    "a template slot in a candidate": (
        {"lineups": {"towns": _towns_with(9, "{place}, Testland")}},
        "bare place name",
    ),
    "a descriptive word in a candidate": (
        {"lineups": {"towns": _towns_with(9, "Jayborough Tower, Testland")}},
        "tower",
    ),
    "a descriptive phrase in a candidate": (
        {"lineups": {"towns": _towns_with(9, "the porticoes of Jayborough, Testland")}},
        "porticoes",
    ),
    "a candidate that is not Name, Region": (
        {"lineups": {"towns": _towns_with(9, "Jayborough")}},
        "Name, Region",
    ),
    "only one candidate takes 'the'": (
        {"lineups": {"towns": _towns_with(9, "the Jayborough, Testland")}},
        "same form",
    ),
    "an unknown line-up": (
        {"photographs": {"street_test_01": {"lineup": "villages"}}},
        "unknown line-up",
    ),
    "a ladder that does not start at the true place": (
        {"photographs": {"street_test_01": {"ladder": ["Testland", "a city"]}}},
        "first rung",
    ),
    "a ladder with one rung": (
        {"photographs": {"street_test_01": {"ladder": ["Aville, Testland"]}}},
        "at least two",
    ),
    "a ladder that repeats a rung": (
        {
            "photographs": {
                "street_test_01": {"ladder": ["Aville, Testland", "Testland", "Testland"]}
            }
        },
        "two different rungs",
    ),
    "template text in a ladder rung": (
        {"photographs": {"street_test_01": {"ladder": ["Aville, Testland", "a photo of a city"]}}},
        "bare place name",
    ),
    "a photograph with nothing under it": (
        {"photographs": {"street_test_01": None}},
        "place, a lineup and a ladder",
    ),
}


@pytest.mark.parametrize("case", BAD_FILES)
def test_load_places_refuses(tmp_path, case):
    change, message = BAD_FILES[case]
    doc = copy.deepcopy(GOOD_FILE)
    for section, items in change.items():
        for key, value in items.items():
            if isinstance(value, dict):
                doc[section][key].update(value)
            else:
                doc[section][key] = value
    with pytest.raises(ValueError, match=message):
        load_places(write_places(tmp_path / "places.yaml", doc))


@pytest.mark.parametrize(
    "text, message",
    [("lineups: [unclosed", "not valid YAML"), ("just: some text", "'lineups' section")],
)
def test_load_places_refuses_a_file_it_cannot_read_as_places(tmp_path, text, message):
    path = tmp_path / "places.yaml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        load_places(path)


# -- the fairness rule ----------------------------------------------------------------------------


def test_banned_words_include_the_ones_the_brief_names():
    for word in ("street", "arcade", "portico", "tower", "lake", "larch", "concrete"):
        assert word in BANNED_WORDS


def test_banned_words_are_found_whole_singular_or_plural_in_any_case():
    assert banned_words_in("the porticoes of Bologna") == ["porticoes"]
    assert banned_words_in("Trellick Tower, London") == ["tower"]
    assert banned_words_in("Golden Larches and Arches, Italy") == ["larches", "arches"]
    assert banned_words_in("Twin Cities, Minnesota") == ["cities"]  # city, cities
    # whole words only: a name that merely contains a banned word is still a bare name
    assert banned_words_in("Newcastle, England") == []
    assert banned_words_in("the Rockies, Canada") == []
    assert banned_words_in("Bologna, Italy") == []


# -- the real data/places.yaml --------------------------------------------------------------------

REAL_PLACES = REPO / "data" / "places.yaml"


SIX_PHOTOGRAPHS = {
    "street_bologna_portici_01",
    "street_barbican_lake_01",
    "landscape_dolomites_larches_01",
    "portrait_dolomites_self_01",
    "text_barbican_seddon_house_01",
    "abstract_barbican_reflection_01",
}


def test_the_real_places_file_lists_the_six_photographs_and_only_public_ones():
    places = load_places(REAL_PLACES)
    assert set(places) >= SIX_PHOTOGRAPHS
    # every entry is a file directly in data/originals: a typo or a private photograph fails here
    public = {p.stem for p in (REPO / "data" / "originals").glob("*.jpg")}
    assert set(places) <= public


def test_the_real_lineups_obey_the_fairness_rule():
    raw = yaml.safe_load(REAL_PLACES.read_text(encoding="utf-8"))
    assert raw["lineups"]
    for name, candidates in raw["lineups"].items():
        assert 10 <= len(candidates) <= 12, name
        assert len({c.casefold() for c in candidates}) == len(candidates), name
        for label in candidates:
            assert banned_words_in(label) == [], f"{name}: {label}"
            assert label.count(",") == 1, f"{name}: {label} is not written as 'Name, Region'"
            assert "{" not in label and "photo" not in label.lower(), f"{name}: {label}"
        # the same form throughout: either every candidate takes "the" or none does
        assert len({c.lower().startswith("the ") for c in candidates}) == 1, name


def test_the_real_ladders_have_four_rungs_and_start_at_the_true_place():
    # The same length, not the same levels: the second rung is a country for Bologna and a
    # city for the Barbican. Ladder numbers are followed within one photograph only.
    places = load_places(REAL_PLACES)
    assert {len(e.ladder) for e in places.values()} == {4}
    for entry in places.values():
        assert entry.ladder[0] == entry.place
        assert entry.place in entry.lineup


def test_the_abstract_crop_is_the_only_negative_control():
    places = load_places(REAL_PLACES)
    flagged = [stem for stem, entry in places.items() if entry.negative_control]
    assert flagged == ["abstract_barbican_reflection_01"]


def test_the_real_file_opens_with_its_rules_and_keeps_a_list_of_changes():
    text = REAL_PLACES.read_text(encoding="utf-8")
    header = text.split("lineups:")[0]
    assert header.startswith("#") and "before" in header and "Bardia" in header
    assert isinstance(yaml.safe_load(text)["changes"], list)


# -- the fingerprint of what was registered --------------------------------------------------------


def sha_of(tmp_path: Path, doc: dict, templates: tuple[str, ...] = TEMPLATES) -> str:
    return registered_sha(load_places(write_places(tmp_path / "places.yaml", doc)), templates)


def test_registered_sha_is_the_same_for_the_same_lineups_ladders_and_wordings(tmp_path):
    first = sha_of(tmp_path, GOOD_FILE)
    assert len(first) == 64  # a sha256
    assert sha_of(tmp_path, copy.deepcopy(GOOD_FILE)) == first
    # logging a correction does not change it: the `changes` list is not what is scored
    logged = copy.deepcopy(GOOD_FILE)
    logged["changes"] = [{"date": "2026-11-17", "what": "a note", "why": "a reason"}]
    assert sha_of(tmp_path, logged) == first


def test_registered_sha_changes_with_anything_the_scoring_reads(tmp_path):
    first = sha_of(tmp_path, GOOD_FILE)

    easier = copy.deepcopy(GOOD_FILE)  # one distractor swapped for another
    easier["lineups"]["towns"][9] = "Kayham, Testland"
    assert sha_of(tmp_path, easier) != first

    other_ladder = copy.deepcopy(GOOD_FILE)
    other_ladder["photographs"]["street_test_01"]["ladder"][2] = "a town"
    assert sha_of(tmp_path, other_ladder) != first

    control = copy.deepcopy(GOOD_FILE)
    control["photographs"]["street_test_01"]["negative_control"] = True
    assert sha_of(tmp_path, control) != first

    # the wordings are registered too, although they live in the code
    assert sha_of(tmp_path, GOOD_FILE, ("{place}",)) != first


# What was registered on 2026-11-17, before any picture was scored: the line-ups, the places and
# ladders in data/places.yaml, and TEMPLATES and LOGIT_SCALE in telephone/metrics/place.py.
REGISTERED = "9a738792a0c428849a2343af2365ed3030255f9d0d898f8992fc5ccaeb554f5e"


def test_the_registered_lineups_ladders_and_wordings_have_not_changed():
    assert registered_sha(load_places(REAL_PLACES)) == REGISTERED, (
        "data/places.yaml, TEMPLATES or LOGIT_SCALE no longer match what was registered. A "
        "line-up, a ladder or a wording is never changed because of a score. If this is a "
        "genuine correction: add a dated entry to the `changes` list in data/places.yaml saying "
        "what changed and why, re-run `telephone place-test --calibrate`, and only then put the "
        "new fingerprint in REGISTERED."
    )


# -- one image against one entry ------------------------------------------------------------------

ENTRY = PlaceEntry(
    image="street_test_01",
    place=A,
    lineup_name="towns",
    lineup=(A, B, C),
    ladder=(A, "Testland", "a city"),
)


def entry_fake(images: dict[bytes, np.ndarray]) -> FakeEmbedder:
    """Place names by angle: a perfect picture of A is at 0 degrees."""
    return FakeEmbedder(texts_for({A: 0, B: 30, C: 60, "Testland": 20, "a city": 45}), images)


def test_score_place_puts_the_lineup_and_the_ladder_together_for_one_image():
    fake = entry_fake({b"sharp": unit(0)})
    res = score_place(b"sharp", ENTRY, fake)
    assert (res["place"], res["lineup"], res["lineup_size"]) == (A, "towns", 3)
    assert res["rank"] == 1 and res["top"] == A
    assert res["prob"] == pytest.approx(1.0, abs=1e-5)  # logits 100, 86.6 and 50
    assert res["per_template_rank"] == {t: 1 for t in TEMPLATES}
    assert [r["label"] for r in res["ladder"]] == [A, "Testland", "a city"]
    assert [r["sim"] for r in res["ladder"]] == pytest.approx([1.0, cos(20), cos(45)])
    assert res["best_rung"] == A
    assert res["specific_minus_generic"] == pytest.approx(1.0 - cos(45))  # 0.2929
    assert fake.image_calls == [b"sharp"]  # the picture is embedded once, not once per candidate


def test_score_place_follows_a_picture_that_has_drifted_towards_the_generic():
    # the picture is now at 40 degrees: 40 from A, 10 from B, 20 from C, 5 from "a city"
    fake = entry_fake({b"drifted": unit(40)})
    res = score_place(b"drifted", ENTRY, fake)
    assert res["rank"] == 3 and res["top"] == B
    assert res["best_rung"] == "a city"
    assert res["specific_minus_generic"] == pytest.approx(cos(40) - cos(5))  # -0.2302


def test_model_label_names_the_model_that_did_the_scoring():
    assert model_label(FakeEmbedder({})) == "fake/by-hand"
    assert model_label(object()) == "object"  # anything without a model name: its class


def test_model_label_says_how_the_network_was_built_and_by_which_library():
    # The same network and weights give different numbers when built with a different
    # activation, so "ViT-B-32/openai" alone could stand for two sets of results. The label
    # names the network, the weights, the activation and the version of the library.
    clip_like = SimpleNamespace(
        model_name="ViT-B-32",
        pretrained="openai",
        activation="quickgelu",
        library="open_clip-4.2.2",
    )
    assert model_label(clip_like) == "ViT-B-32/openai/quickgelu/open_clip-4.2.2"


# -- provenance: what a set of scores was made with ------------------------------------------------

PROVENANCE_KEYS = {
    "clip_model",
    "preprocessing",
    "templates",
    "logit_scale",
    "places_file_sha256",
    "registered_sha",
}


def test_provenance_says_what_a_set_of_scores_was_made_with(tmp_path):
    path = write_places(tmp_path / "places.yaml", GOOD_FILE)
    places = load_places(path)
    assert provenance(FakeEmbedder({}), places, path) == {
        "clip_model": "fake/by-hand",
        "preprocessing": "none: vectors written by hand",
        "templates": list(TEMPLATES),
        "logit_scale": 100.0,
        "places_file_sha256": sha256_bytes(path.read_bytes()),  # the file, byte for byte
        "registered_sha": registered_sha(places),  # the line-ups, ladders and wordings in it
    }


def test_provenance_tells_a_note_in_the_file_from_a_change_to_what_is_scored(tmp_path):
    fake = FakeEmbedder({})
    path = write_places(tmp_path / "places.yaml", GOOD_FILE)
    before = provenance(fake, load_places(path), path)

    logged = copy.deepcopy(GOOD_FILE)
    logged["changes"] = [{"date": "2026-11-17", "what": "a note", "why": "a reason"}]
    write_places(path, logged)
    noted = provenance(fake, load_places(path), path)
    assert noted["places_file_sha256"] != before["places_file_sha256"]  # the file did change
    assert noted["registered_sha"] == before["registered_sha"]  # what is scored did not

    easier = copy.deepcopy(GOOD_FILE)
    easier["lineups"]["towns"][9] = "Kayham, Testland"
    write_places(path, easier)
    assert provenance(fake, load_places(path), path)["registered_sha"] != before["registered_sha"]


def test_provenance_does_not_invent_a_preprocessing_the_embedder_did_not_state(tmp_path):
    path = write_places(tmp_path / "places.yaml", GOOD_FILE)
    silent = SimpleNamespace(model_name="fake")
    assert provenance(silent, load_places(path), path)["preprocessing"] == "not known"


# -- calibration: where the true place comes in its line-up before any loop has run ---------------

D, E, F = "the Dees, Testland", "the Ees, Testland", "the Effs, Testland"


def calibration_case() -> tuple[dict[str, bytes], dict[str, PlaceEntry], FakeEmbedder]:
    """Three photographs, two places. Angles: A 0, B 30, C 60 (towns); D 90, E 120, F 150 (ranges)."""
    towns, ranges = (A, B, C), (D, E, F)
    places = {
        "street_a_01": PlaceEntry("street_a_01", A, "towns", towns, (A, "a city")),
        "street_a_02": PlaceEntry("street_a_02", A, "towns", towns, (A, "a city"), True),
        "landscape_d_01": PlaceEntry("landscape_d_01", D, "ranges", ranges, (D, "the mountains")),
    }
    images = {"street_a_01": b"a1", "street_a_02": b"a2", "landscape_d_01": b"d1"}
    fake = FakeEmbedder(
        texts_for({A: 0, B: 30, C: 60, D: 90, E: 120, F: 150, "a city": 20, "the mountains": 100}),
        # a clear picture of A, an unclear one (nearer to C and B than to A), a clear picture of D
        {b"a1": unit(0), b"a2": unit(50), b"d1": unit(90)},
    )
    return images, places, fake


def test_calibration_scores_every_photograph_in_its_own_lineup():
    images, places, fake = calibration_case()
    cal = calibrate_places(images, places, fake)
    assert set(cal) == {"photographs", "cross"}
    own = {row["image"]: row for row in cal["photographs"]}
    assert list(own) == ["landscape_d_01", "street_a_01", "street_a_02"]  # sorted by name
    assert (own["street_a_01"]["rank"], own["street_a_01"]["top"]) == (1, A)
    assert (own["landscape_d_01"]["rank"], own["landscape_d_01"]["top"]) == (1, D)
    # the unclear picture is 50 degrees from A, 20 from B and 10 from C: last of three
    assert (own["street_a_02"]["rank"], own["street_a_02"]["top"]) == (3, C)
    assert own["street_a_02"]["negative_control"] is True
    assert own["street_a_01"]["negative_control"] is False
    assert own["street_a_01"]["place"] == A and own["street_a_01"]["lineup_size"] == 3
    assert own["street_a_01"]["specific_minus_generic"] == pytest.approx(1.0 - cos(20))
    assert sorted(fake.image_calls) == [b"a1", b"a2", b"d1"]  # each picture embedded once


def test_calibration_cross_table_scores_each_photograph_against_the_other_places():
    images, places, fake = calibration_case()
    cross = calibrate_places(images, places, fake)["cross"]
    # three photographs, two places, minus each photograph's own place: three rows
    assert [(row["image"], row["place"]) for row in cross] == [
        ("landscape_d_01", A),
        ("street_a_01", D),
        ("street_a_02", D),
    ]
    by_image = {row["image"]: row for row in cross}
    # the picture of D is 90 degrees from A, 60 from B, 30 from C: A comes last among the towns
    assert by_image["landscape_d_01"]["rank"] == 3 and by_image["landscape_d_01"]["top"] == C
    assert by_image["landscape_d_01"]["lineup"] == "towns"
    assert by_image["landscape_d_01"]["lineup_size"] == 3
    assert 0.0 <= by_image["landscape_d_01"]["prob"] < 0.01
    # the picture of A is 90 from D, 120 from E, 150 from F: D is the least bad of the ranges,
    # so it ranks first. A line-up always ranks something first, which is why this table exists.
    assert by_image["street_a_01"]["rank"] == 1 and by_image["street_a_01"]["top"] == D


def test_calibration_cross_table_is_scored_with_the_same_wordings_as_the_lineup():
    # The wordings disagree about A, as in the per-wording test above: "in A" is 10 degrees
    # from the picture, "A" alone is 70, so their average is at 40. B is at 30 and C at 50.
    templates = ("in {place}", "{place}")
    places = {
        "street_a_01": PlaceEntry("street_a_01", A, "towns", (A, B, C), (A, "a city")),
        "landscape_d_01": PlaceEntry("landscape_d_01", D, "ranges", (D, E, F), (D, "a city")),
    }
    same_both_ways = {B: 30, C: 50, D: 90, E: 120, F: 150, "a city": 20}
    texts = {**texts_for(same_both_ways, templates), f"in {A}": unit(10), A: unit(70)}
    fake = FakeEmbedder(texts, {b"d1": unit(0)})
    cal = calibrate_places({"landscape_d_01": b"d1"}, places, fake, templates)
    (row,) = cal["cross"]
    # all the wordings together put A second, behind B. The first wording alone would put it first.
    assert (row["image"], row["place"], row["rank"], row["top"]) == ("landscape_d_01", A, 2, B)


def test_calibration_leaves_out_photographs_without_a_file_or_without_an_entry():
    images, places, fake = calibration_case()
    del images["street_a_02"]  # in places.yaml, but the file is not there
    images["street_unlisted_01"] = b"zz"  # a file, but no entry
    cal = calibrate_places(images, places, fake)
    assert [row["image"] for row in cal["photographs"]] == ["landscape_d_01", "street_a_01"]
    assert {row["image"] for row in cal["cross"]} == {"landscape_d_01", "street_a_01"}


def test_round_floats_rounds_every_number_in_a_result_and_nothing_else():
    result = {
        "rank": 2,
        "prob": 0.123456789,
        "top": "Aville, Testland",
        "flag": True,
        "ladder": [{"label": "a city", "sim": 0.28765432}],
    }
    assert round_floats(result) == {
        "rank": 2,
        "prob": 0.1235,
        "top": "Aville, Testland",
        "flag": True,
        "ladder": [{"label": "a city", "sim": 0.2877}],
    }
    assert round_floats(result, digits=2)["prob"] == 0.12


def test_the_public_names_are_exported_from_telephone_metrics():
    import telephone.metrics as metrics
    from telephone.metrics import place

    for name in (
        "PlaceEntry",
        "calibrate_places",
        "load_places",
        "place_vector",
        "score_ladder",
        "score_lineup",
        "score_place",
    ):
        assert name in metrics.__all__
        assert getattr(metrics, name) is getattr(place, name)


# -- the command: telephone place-test EXPERIMENT -------------------------------------------------

EXP = "exp01_compression"
HARSH = f"{EXP}__harsh__street_test_01"
GENTLE = f"{EXP}__gentle__street_test_01"
# Town names by angle. A perfect picture of Aville is at 0 degrees; the other seven are far away.
TOWN_ANGLES = dict(zip(TOWNS, (0, 30, 60, 100, 110, 120, 130, 140, 150, 160), strict=True))
ROW_KEYS = {
    "experiment_id",
    "chain_id",
    "image",
    "variant",
    "repeat",
    "generation",
    "output_sha",
    "config_sha",
    "place",
    "lineup",
    "lineup_size",
    "rank",
    "prob",
    "top",
    "rival",
    "margin",
    "per_template_rank",
    "ladder",
    "best_rung",
    "specific_minus_generic",
    *PROVENANCE_KEYS,
}


def tiny_png(shade: int) -> bytes:
    """An 8 x 8 picture of one grey. A different shade gives different bytes."""
    return to_png_bytes(Image.new("RGB", (8, 8), (shade, shade, shade)))


def use_fake_clip(monkeypatch, fake: FakeEmbedder) -> None:
    monkeypatch.setattr(ClipEmbedder, "shared", classmethod(lambda cls: fake))


def add_row(
    led: Ledger,
    chain: str,
    repeat: int,
    gen: int,
    image: bytes | None,
    exp: str = EXP,
    error: str | None = None,
    config_sha: str = "config-1",
):
    """One ledger row, written the way a chain writes it.

    With an image, the file is written where the row says it is and the row carries the
    sha256 of its bytes. Without one, the row still names a path but no file is there (results
    loaded from a saved file on a machine that does not have the pictures). A pass that failed
    (an error and no image) has no path and no sha at all.
    """
    path = get_settings().runs_dir / exp / chain / f"r{repeat}" / f"{gen:03d}.png"
    if image is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(image)
    failed_pass = image is None and error is not None
    led.append(
        GenerationRecord(
            run_id="r1",
            experiment_id=exp,
            chain_id=chain,
            repeat=repeat,
            generation=gen,
            station_sequence="platform",
            config_sha=config_sha,
            output_path="" if failed_pass else str(path),
            output_sha=sha256_bytes(image) if image is not None else "",
            error=error,
        )
    )


def place_test_case(monkeypatch) -> FakeEmbedder:
    """A temporary ledger, places file and private folder, and the fake CLIP that reads them.

    The picture of street_test_01 turns 20 degrees away from Aville at every generation of the
    harsh chain, and stays put in the gentle chain (generation 1 is the same file as 0).
    """
    s = get_settings()
    doc = copy.deepcopy(GOOD_FILE)
    doc["photographs"]["portrait_secret_01"] = dict(doc["photographs"]["street_test_01"])
    write_places(s.telephone_data_dir / "places.yaml", doc)
    s.private_dir.mkdir(parents=True)
    (s.private_dir / "portrait_secret_01.jpg").write_bytes(b"not for publication")

    images: dict[bytes, np.ndarray] = {}

    def picture(shade: int, angle: float) -> bytes:
        data = tiny_png(shade)
        images[data] = unit(angle)
        return data

    led = Ledger(s.ledger_path)
    add_row(led, HARSH, 1, 1, picture(41, 20))
    add_row(led, HARSH, 1, 0, picture(40, 0))
    add_row(led, HARSH, 0, 2, picture(12, 40))
    add_row(led, HARSH, 0, 0, picture(10, 0))
    add_row(led, HARSH, 0, 1, picture(11, 20))
    add_row(led, GENTLE, 0, 1, picture(20, 0))
    add_row(led, GENTLE, 0, 0, picture(20, 0))
    # rows that must be skipped: no image file, a photograph with no entry, a private photograph
    add_row(led, HARSH, 0, 3, None)
    add_row(led, HARSH, 0, 4, None)
    for gen in (0, 1):
        add_row(led, f"{EXP}__harsh__street_other_01", 0, gen, tiny_png(100 + gen))
        add_row(led, f"{EXP}__harsh__portrait_secret_01", 0, gen, tiny_png(200 + gen))
    add_row(led, "exp00_smoke__compression__street_test_01", 0, 0, tiny_png(250), exp="exp00_smoke")
    led.close()

    fake = FakeEmbedder(texts_for({**TOWN_ANGLES, "Testland": 20, "a city": 45}), images)
    use_fake_clip(monkeypatch, fake)
    return fake


def read_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_place_test_writes_one_sorted_row_per_scored_generation(monkeypatch):
    fake = place_test_case(monkeypatch)
    result = runner.invoke(app, ["place-test", EXP])
    assert result.exit_code == 0, result.output
    out = get_settings().results_dir / f"{EXP}_place.jsonl"
    rows = read_rows(out)
    keys = [(r["chain_id"], r["repeat"], r["generation"]) for r in rows]
    assert keys == [
        (GENTLE, 0, 0),
        (GENTLE, 0, 1),
        (HARSH, 0, 0),
        (HARSH, 0, 1),
        (HARSH, 0, 2),
        (HARSH, 1, 0),
        (HARSH, 1, 1),
    ]  # sorted by chain, repeat, generation; complete; nothing from another experiment
    assert all(set(r) == ROW_KEYS for r in rows)
    assert all(r["experiment_id"] == EXP and r["image"] == "street_test_01" for r in rows)
    assert [r["variant"] for r in rows] == ["gentle"] * 2 + ["harsh"] * 5
    assert all(r["place"] == "Aville, Testland" and r["lineup"] == "towns" for r in rows)
    assert all(r["lineup_size"] == 10 for r in rows)
    # each row says which file it scored and which configuration of the chain produced it
    assert rows[2]["output_sha"] == sha256_bytes(tiny_png(10))
    assert all(r["config_sha"] == "config-1" for r in rows)
    # and what it was scored with: the model, what the model was shown, the wordings, the
    # scale, the places file byte for byte and the line-ups and ladders registered in it
    places_file = get_settings().telephone_data_dir / "places.yaml"
    made_with = provenance(fake, load_places(places_file), places_file)
    assert made_with["clip_model"] == "fake/by-hand"
    assert all({key: r[key] for key in PROVENANCE_KEYS} == made_with for r in rows)

    # the harsh chain, repeat 0: 0, 20 and 40 degrees away from Aville
    g0, g1, g2 = rows[2], rows[3], rows[4]
    assert (g0["rank"], g0["top"], g0["best_rung"]) == (1, "Aville, Testland", "Aville, Testland")
    assert (g1["rank"], g1["top"], g1["best_rung"]) == (2, "Beeton, Testland", "Testland")
    assert (g2["rank"], g2["top"], g2["best_rung"]) == (3, "Beeton, Testland", "a city")
    assert g0["per_template_rank"] == {t: 1 for t in TEMPLATES}
    assert g2["per_template_rank"] == {t: 3 for t in TEMPLATES}
    # Aville is at 0 degrees and Beeton, its nearest rival, at 30
    assert (g0["rival"], g0["margin"]) == ("Beeton, Testland", 0.134)  # 1 - cos(30)
    assert (g1["rival"], g1["margin"]) == ("Beeton, Testland", -0.0451)  # cos(20) - cos(10)
    assert [rung["label"] for rung in g1["ladder"]] == ["Aville, Testland", "Testland", "a city"]
    assert [rung["sim"] for rung in g1["ladder"]] == [0.9397, 1.0, 0.9063]  # cos 20, 0, 25
    assert g0["specific_minus_generic"] == 0.2929  # 1 - cos(45), rounded to four places
    assert g2["specific_minus_generic"] == -0.2302  # cos(40) - cos(5) = -0.23015
    weights = [math.exp(100 * cos(angle - 20)) for angle in TOWN_ANGLES.values()]
    assert g1["prob"] == pytest.approx(weights[0] / sum(weights), abs=1e-4)  # 0.0109
    assert g0["prob"] == 1.0

    # the file that did not change between generations is only looked at once
    assert fake.image_calls.count(tiny_png(20)) == 1
    assert rows[0]["rank"] == rows[1]["rank"] == 1
    assert "7 rows" in result.output


def test_place_test_sorts_the_rows_whatever_order_the_ledger_gives_them_in(monkeypatch):
    place_test_case(monkeypatch)
    in_ledger_order = Ledger.experiment
    # the ledger happens to hand rows back sorted; the results file must not depend on that
    monkeypatch.setattr(
        Ledger, "experiment", lambda self, exp: list(reversed(in_ledger_order(self, exp)))
    )
    result = runner.invoke(app, ["place-test", EXP])
    assert result.exit_code == 0, result.output
    rows = read_rows(get_settings().results_dir / f"{EXP}_place.jsonl")
    keys = [(r["chain_id"], r["repeat"], r["generation"]) for r in rows]
    assert len(keys) == 7 and keys == sorted(keys)


def test_place_test_scores_the_same_bytes_once_for_each_photograph_they_belong_to(monkeypatch):
    """A result is remembered so that a file that did not change is looked at once. It is
    remembered for one photograph: the same bytes under another photograph are scored against
    that photograph's own place."""
    s = get_settings()
    doc = copy.deepcopy(GOOD_FILE)
    doc["photographs"]["street_twin_01"] = {
        "place": "Beeton, Testland",
        "lineup": "towns",
        "ladder": ["Beeton, Testland", "Testland", "a city"],
    }
    write_places(s.telephone_data_dir / "places.yaml", doc)
    same = tiny_png(10)
    led = Ledger(s.ledger_path)
    add_row(led, HARSH, 0, 0, same)
    add_row(led, f"{EXP}__harsh__street_twin_01", 0, 0, same)
    led.close()
    fake = FakeEmbedder(texts_for({**TOWN_ANGLES, "Testland": 20, "a city": 45}), {same: unit(0)})
    use_fake_clip(monkeypatch, fake)

    result = runner.invoke(app, ["place-test", EXP])
    assert result.exit_code == 0, result.output
    rows = {r["image"]: r for r in read_rows(s.results_dir / f"{EXP}_place.jsonl")}
    # the picture is a perfect match for Aville, so Beeton (30 degrees away) comes second
    assert (rows["street_test_01"]["place"], rows["street_test_01"]["rank"]) == (TOWNS[0], 1)
    assert (rows["street_twin_01"]["place"], rows["street_twin_01"]["rank"]) == (TOWNS[1], 2)


def test_place_test_never_writes_or_even_looks_at_a_private_photograph(monkeypatch):
    fake = place_test_case(monkeypatch)
    result = runner.invoke(app, ["place-test", EXP])
    assert result.exit_code == 0, result.output
    text = (get_settings().results_dir / f"{EXP}_place.jsonl").read_text(encoding="utf-8")
    assert "secret" not in text
    assert tiny_png(200) not in fake.image_calls and tiny_png(201) not in fake.image_calls
    assert "2 private" in result.output


def test_place_test_counts_what_it_skipped(monkeypatch):
    fake = place_test_case(monkeypatch)
    result = runner.invoke(app, ["place-test", EXP])
    assert result.exit_code == 0, result.output
    assert "2 without an image" in result.output
    assert "2 without an entry" in result.output
    assert tiny_png(100) not in fake.image_calls  # no entry, so never scored


def test_place_test_scores_generation_0_when_the_survival_form_was_refused(monkeypatch):
    """A chain writes generation 0 with its image AND an error when the vision model refuses to
    fill in the survival form, and then carries on. The picture is there, so it is scored: the
    place test must not lose the chain's starting point over an error that is not about the
    picture."""
    s = get_settings()
    write_places(s.telephone_data_dir / "places.yaml", GOOD_FILE)
    led = Ledger(s.ledger_path)
    add_row(led, HARSH, 0, 0, tiny_png(10), error="extract: the model refused")
    add_row(led, HARSH, 0, 1, tiny_png(11))
    add_row(led, HARSH, 0, 2, None, error="platform: something broke")  # a failed pass: no file
    led.close()
    images = {tiny_png(10): unit(0), tiny_png(11): unit(20)}
    fake = FakeEmbedder(texts_for({**TOWN_ANGLES, "Testland": 20, "a city": 45}), images)
    use_fake_clip(monkeypatch, fake)

    result = runner.invoke(app, ["place-test", EXP])
    assert result.exit_code == 0, result.output
    rows = read_rows(s.results_dir / f"{EXP}_place.jsonl")
    assert [(r["generation"], r["rank"]) for r in rows] == [(0, 1), (1, 2)]
    assert "1 without an image" in result.output  # only the pass that really has no file


def test_place_test_skips_a_file_that_is_not_the_one_its_ledger_row_describes(monkeypatch):
    """A chain saves the picture first and writes its ledger row afterwards. If a re-run with
    other settings is stopped in between, the file on disk belongs to the new run and the row
    to the old one. Scoring that file under the old row's name would be a wrong result, so the
    row is skipped and counted."""
    s = get_settings()
    write_places(s.telephone_data_dir / "places.yaml", GOOD_FILE)
    led = Ledger(s.ledger_path)
    add_row(led, HARSH, 0, 0, tiny_png(10))
    add_row(led, HARSH, 0, 1, tiny_png(11))
    led.close()
    # the stopped re-run: a new file where generation 1 was, and no new row for it
    (s.runs_dir / EXP / HARSH / "r0" / "001.png").write_bytes(tiny_png(99))
    images = {tiny_png(10): unit(0), tiny_png(11): unit(20), tiny_png(99): unit(40)}
    fake = FakeEmbedder(texts_for({**TOWN_ANGLES, "Testland": 20, "a city": 45}), images)
    use_fake_clip(monkeypatch, fake)

    result = runner.invoke(app, ["place-test", EXP])
    assert result.exit_code == 0, result.output
    rows = read_rows(s.results_dir / f"{EXP}_place.jsonl")
    assert [r["generation"] for r in rows] == [0]
    assert rows[0]["output_sha"] == sha256_bytes(tiny_png(10))
    assert tiny_png(99) not in fake.image_calls  # never scored, so never mislabelled
    assert "1 whose file does not match its ledger row" in result.output


def test_place_test_rows_show_when_a_chain_mixes_two_configurations(monkeypatch):
    """The other half of a stopped re-run: the first rows belong to the new settings and the
    later rows to the old ones. Each place row carries its ledger row's config_sha, so a chain
    that mixes two configurations can be seen in the results file."""
    s = get_settings()
    write_places(s.telephone_data_dir / "places.yaml", GOOD_FILE)
    led = Ledger(s.ledger_path)
    add_row(led, HARSH, 0, 0, tiny_png(10), config_sha="new-settings")
    add_row(led, HARSH, 0, 1, tiny_png(11), config_sha="old-settings")
    led.close()
    images = {tiny_png(10): unit(0), tiny_png(11): unit(20)}
    fake = FakeEmbedder(texts_for({**TOWN_ANGLES, "Testland": 20, "a city": 45}), images)
    use_fake_clip(monkeypatch, fake)

    result = runner.invoke(app, ["place-test", EXP])
    assert result.exit_code == 0, result.output
    rows = read_rows(s.results_dir / f"{EXP}_place.jsonl")
    assert [r["config_sha"] for r in rows] == ["new-settings", "old-settings"]


def test_place_test_accepts_an_experiment_prefix_and_an_output_path(monkeypatch, tmp_path):
    place_test_case(monkeypatch)
    out = tmp_path / "elsewhere" / "rows.jsonl"
    result = runner.invoke(app, ["place-test", "exp01", "--out", str(out)])
    assert result.exit_code == 0, result.output
    assert len(read_rows(out)) == 7


def one_error_line(result) -> str:
    """The command failed with exactly one line on stderr and no traceback anywhere."""
    assert result.exit_code != 0
    assert "Traceback" not in result.output
    lines = [line for line in result.stderr.splitlines() if line.strip()]
    assert len(lines) == 1, result.stderr
    return lines[0]


def test_place_test_without_clip_is_one_line_on_stderr_and_writes_nothing(monkeypatch):
    place_test_case(monkeypatch)

    def no_clip(cls):
        raise MetricsUnavailable(
            "Could not load CLIP ViT-B-32/openai: connection refused\n  (a second line of detail)"
        )

    monkeypatch.setattr(ClipEmbedder, "shared", classmethod(no_clip))
    result = runner.invoke(app, ["place-test", EXP])
    line = one_error_line(result)
    assert "CLIP" in line and "connection refused" in line
    assert not (get_settings().results_dir / f"{EXP}_place.jsonl").exists()


def test_place_test_errors_are_one_clean_line(monkeypatch):
    # no ledger yet
    s = get_settings()
    write_places(s.telephone_data_dir / "places.yaml", GOOD_FILE)
    assert "ledger" in one_error_line(runner.invoke(app, ["place-test", EXP]))
    # neither an experiment nor --calibrate, and both at once
    assert "--calibrate" in one_error_line(runner.invoke(app, ["place-test"]))
    assert "--calibrate" in one_error_line(runner.invoke(app, ["place-test", EXP, "--calibrate"]))
    # an experiment the ledger does not have
    place_test_case(monkeypatch)
    line = one_error_line(runner.invoke(app, ["place-test", "exp99"]))
    assert "exp99" in line and EXP in line
    # a places file that breaks the fairness rule, and no places file at all
    doc = copy.deepcopy(GOOD_FILE)
    doc["lineups"]["towns"][9] = "Jayborough Tower, Testland"
    write_places(s.telephone_data_dir / "places.yaml", doc)
    assert "tower" in one_error_line(runner.invoke(app, ["place-test", EXP]))
    (s.telephone_data_dir / "places.yaml").unlink()
    assert "places.yaml" in one_error_line(runner.invoke(app, ["place-test", EXP]))


def test_place_test_with_nothing_to_score_says_so_and_writes_nothing(monkeypatch):
    s = get_settings()
    write_places(s.telephone_data_dir / "places.yaml", GOOD_FILE)
    led = Ledger(s.ledger_path)
    add_row(led, f"{EXP}__harsh__street_other_01", 0, 0, tiny_png(1))
    led.close()
    use_fake_clip(monkeypatch, FakeEmbedder({}))
    line = one_error_line(runner.invoke(app, ["place-test", EXP]))
    assert "Nothing to score" in line and "1 without an entry" in line
    assert not (s.results_dir / f"{EXP}_place.jsonl").exists()


# -- the command: telephone place-test --calibrate ------------------------------------------------

RANGES = [
    f"the {name}, Testland"
    for name in ("Dees", "Ees", "Effs", "Gees", "Aitches", "Eyes", "Jays", "Kays", "Els", "Ems")
]
RANGE_ANGLES = dict(zip(RANGES, (90, 120, 150, 170, 180, 190, 200, 210, 220, 230), strict=True))


def calibrate_case(monkeypatch) -> tuple[FakeEmbedder, dict[str, bytes]]:
    """Two public originals with entries, plus everything that must be left out."""
    s = get_settings()
    doc = copy.deepcopy(GOOD_FILE)
    street = doc["photographs"]["street_test_01"]
    doc["lineups"]["ranges"] = RANGES
    doc["photographs"]["landscape_test_01"] = {
        "place": RANGES[0],
        "lineup": "ranges",
        "ladder": [RANGES[0], "the mountains"],
    }
    doc["photographs"]["street_missing_01"] = dict(street)  # listed, but there is no file
    doc["photographs"]["street_secret_01"] = dict(street)  # listed by mistake: the file is private
    write_places(s.telephone_data_dir / "places.yaml", doc)

    s.private_dir.mkdir(parents=True)
    Image.new("RGB", (8, 8), (10, 10, 10)).save(s.originals_dir / "street_test_01.jpg")
    Image.new("RGB", (8, 8), (20, 20, 20)).save(s.originals_dir / "landscape_test_01.png")
    Image.new("RGB", (8, 8), (30, 30, 30)).save(s.private_dir / "street_secret_01.jpg")
    Image.new("RGB", (8, 8), (40, 40, 40)).save(s.originals_dir / "street_unlisted_01.jpg")
    (s.originals_dir / "README.md").write_text("not a picture")

    # the calibration looks at the same bytes a chain stores as generation 0
    g0 = {
        stem: to_png_bytes(load_image(s.originals_dir / name))
        for stem, name in (
            ("street_test_01", "street_test_01.jpg"),
            ("landscape_test_01", "landscape_test_01.png"),
        )
    }
    fake = FakeEmbedder(
        texts_for(
            {**TOWN_ANGLES, **RANGE_ANGLES, "Testland": 20, "a city": 45, "the mountains": 100}
        ),
        {g0["street_test_01"]: unit(0), g0["landscape_test_01"]: unit(90)},
    )
    use_fake_clip(monkeypatch, fake)
    return fake, g0


def test_calibrate_scores_the_originals_and_writes_the_calibration_file(monkeypatch):
    fake, g0 = calibrate_case(monkeypatch)
    result = runner.invoke(app, ["place-test", "--calibrate"])
    assert result.exit_code == 0, result.output
    out = get_settings().results_dir / "place_calibration.json"
    cal = json.loads(out.read_text(encoding="utf-8"))
    assert set(cal) == PROVENANCE_KEYS | {"photographs", "cross"}
    places_file = get_settings().telephone_data_dir / "places.yaml"
    made_with = provenance(fake, load_places(places_file), places_file)
    assert {key: cal[key] for key in PROVENANCE_KEYS} == made_with
    assert cal["places_file_sha256"] == sha256_bytes(places_file.read_bytes())
    # the summary says what did the scoring and what part of each picture it was shown
    assert "fake/by-hand" in result.output and "none: vectors written by hand" in result.output

    # (a) each photograph in its own line-up
    assert [row["image"] for row in cal["photographs"]] == ["landscape_test_01", "street_test_01"]
    landscape, street = cal["photographs"]
    assert (street["rank"], street["prob"], street["top"]) == (1, 1.0, "Aville, Testland")
    assert street["lineup_size"] == 10 and street["specific_minus_generic"] == 0.2929
    assert (landscape["rank"], landscape["top"]) == (1, "the Dees, Testland")
    assert landscape["best_rung"] == "the Dees, Testland"
    # a rank is never printed alone: the nearest other candidate and the margin over it go with it
    assert (street["rival"], street["margin"]) == ("Beeton, Testland", 0.134)  # 1 - cos(30)
    assert "margin +0.1340 over Beeton, Testland" in result.output
    # what a rank does and does not show, and that line-ups differ in how hard they are
    assert "It is a result about those names and nothing more" in result.output
    assert "not equally hard" in result.output
    # a rank is always printed with its prob: two rows in each of the two tables
    table_rows = [line for line in result.output.splitlines() if line.startswith("  ")]
    assert len(table_rows) == 4
    assert all(" rank " in line and " prob " in line for line in table_rows)

    # (b) each photograph against the place it was not taken in
    cross = {(row["image"], row["place"]): row for row in cal["cross"]}
    assert set(cross) == {
        ("landscape_test_01", "Aville, Testland"),
        ("street_test_01", "the Dees, Testland"),
    }
    # the landscape is 90 degrees from Aville, further than from any other town: last of ten
    wrong_town = cross[("landscape_test_01", "Aville, Testland")]
    assert (wrong_town["rank"], wrong_town["top"]) == (10, "Deeford, Testland")
    assert wrong_town["prob"] == 0.0

    # only the two public originals with an entry were looked at
    assert sorted(fake.image_calls) == sorted(g0.values())
    assert "secret" not in out.read_text(encoding="utf-8")
    # the printed summary names every photograph it scored and every one it could not find
    for stem in ("street_test_01", "landscape_test_01", "street_missing_01", "street_secret_01"):
        assert stem in result.output
    assert "unlisted" not in result.output


def test_calibrate_without_clip_is_one_line_on_stderr_and_writes_nothing(monkeypatch):
    calibrate_case(monkeypatch)

    def no_clip(cls):
        raise MetricsUnavailable("CLIP needs torch and open_clip_torch")

    monkeypatch.setattr(ClipEmbedder, "shared", classmethod(no_clip))
    line = one_error_line(runner.invoke(app, ["place-test", "--calibrate"]))
    assert "CLIP" in line
    assert not (get_settings().results_dir / "place_calibration.json").exists()


def test_calibrate_with_no_originals_says_where_it_looked(monkeypatch):
    s = get_settings()
    write_places(s.telephone_data_dir / "places.yaml", GOOD_FILE)
    use_fake_clip(monkeypatch, FakeEmbedder({}))
    line = one_error_line(runner.invoke(app, ["place-test", "--calibrate"]))
    assert str(s.originals_dir) in line


# -- wording: a rank in a line-up, and nothing more ------------------------------------------------

# Words that claim more than a rank in a chosen line-up can show.
OVERCLAIMS = ("recognis", "knows", "picks the right place", "pick the right place", "see the place")


def test_the_place_test_is_described_as_a_rank_in_a_lineup_and_nothing_more(monkeypatch):
    """What is measured is where the true place comes in a line-up of candidate names. None of
    the texts a reader meets may say that the machine recognises or knows a place."""
    import telephone.metrics as metrics
    from telephone.metrics import place

    calibrate_case(monkeypatch)
    texts = {
        "the place module": place.__doc__,
        "telephone.metrics": metrics.__doc__,
        "score_lineup": place.score_lineup.__doc__,
        "score_ladder": place.score_ladder.__doc__,
        "calibrate_places": place.calibrate_places.__doc__,
        "place-test --help": runner.invoke(app, ["place-test", "--help"]).output,
        "place-test --calibrate": runner.invoke(app, ["place-test", "--calibrate"]).output,
    }
    for where, text in texts.items():
        for claim in OVERCLAIMS:
            assert claim not in text.lower(), f"{where} says {claim!r}"
    # the measurement in the project's own words, and the two cautions that go with it
    module = " ".join(place.__doc__.split())
    assert "first, or Nth, in a line-up of 12 candidates" in module
    assert "Rank and prob are always quoted together" in module
    assert "not equally hard" in module
    assert "line-up" in " ".join(texts["place-test --help"].split())


def test_the_place_module_says_which_part_of_a_picture_the_model_is_shown():
    from telephone.metrics import place

    module = " ".join(place.__doc__.split())
    assert "central 224 x 224 square" in module and "QuickGELU" in module


# -- the real model -------------------------------------------------------------------------------


@pytest.mark.slow
def test_real_clip_fits_the_same_interface_as_the_fake(test_image):
    """Needs the CLIP weights, so it is skipped by default.

    It scores a synthetic picture, not one of the photographs: it checks that the real model
    plugs into the same functions as the fake, and says nothing about any place.
    """
    embedder = ClipEmbedder.shared()
    entry = load_places(REAL_PLACES)["street_bologna_portici_01"]
    res = score_place(test_image.read_bytes(), entry, embedder)
    assert 1 <= res["rank"] <= len(entry.lineup)
    assert 0.0 <= res["prob"] <= 1.0
    assert res["top"] in entry.lineup
    assert set(res["per_template_rank"]) == set(TEMPLATES)
    assert all(1 <= rank <= len(entry.lineup) for rank in res["per_template_rank"].values())
    assert [rung["label"] for rung in res["ladder"]] == list(entry.ladder)
    assert all(-1.0 <= rung["sim"] <= 1.0 for rung in res["ladder"])
    assert np.linalg.norm(place_vector(embedder, entry.place)) == pytest.approx(1.0, abs=1e-6)
    import open_clip

    assert model_label(embedder) == f"ViT-B-32/openai/quickgelu/open_clip-{open_clip.__version__}"
