"""The place line-up: where does the true place come in a line-up of candidate names?

CLIP turns a picture and a piece of text into two lists of numbers that can be compared. Here the
texts are place names. Each photograph has a line-up, a fixed list of candidate places that
includes the true one (12 in data/places.yaml; the loader accepts 10 to 12). The measurement is
where the true place comes when the candidates are sorted by how well they match the picture:
first, or Nth, in a line-up of 12 candidates.

Two measurements come out of it, both read across the generations of a chain:

- the line-up: the rank of the true place among the candidates, its probability (prob), the
  candidate that came first, the nearest other candidate and the margin over it;
- the ladder: how well the picture matches the place, then wider and more generic descriptions
  ("Bologna, Italy" > "Italy" > "Europe" > "a city").

How to read them. Rank 1 means that, of the names in the line-up, the true one matched the
picture best. It is a result about those names and nothing more. Rank and prob are always quoted
together, because a rank of 1 can be won by a wide margin or by a hair. The line-ups are not
equally hard: how many candidates come close to the true place differs from one line-up to the
next. So ranks, probs and ladder numbers are followed across the generations of one photograph
and are not compared between photographs that use different line-ups.

What is fixed, and when. The places, line-ups and ladders in data/places.yaml, and TEMPLATES and
LOGIT_SCALE below, were fixed before any picture was scored. The model is CLIP ViT-B/32 with
OpenAI's weights, built with the activation those weights were trained with (QuickGELU). The
first calibration was scored on a network built with the wrong activation; the build was
corrected on 2026-11-17 and is registered from then on (see `changes` in data/places.yaml). The
preprocessing is CLIP's standard one and was the same throughout: the picture is shrunk until
its shorter side is 224 px and the central 224 x 224 square is kept. So the model is only ever
shown the central square of a picture, a little over half of a 16:9 photograph and three
quarters of a 4:3 one. Every results file records all of this (see `provenance`).

Everything here takes an `embedder`: any object with `embed(image_bytes)` and
`embed_text(text)` that return unit vectors, as `telephone.metrics.embed.ClipEmbedder` does.
Tests pass a fake one, so nothing in this module needs the CLIP weights.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from functools import cache
from pathlib import Path
from typing import Protocol

import numpy as np
import yaml

from ..imageio import sha256_bytes
from ..models import stable_hash


class Embedder(Protocol):
    """What the scoring needs from a model: a unit vector for a picture and for a text."""

    def embed(self, image: bytes) -> np.ndarray: ...

    def embed_text(self, text: str) -> np.ndarray: ...


# The wordings a place name is put into. A place is scored on the average of all of them, so one
# lucky or unlucky wording does not decide the result. Fixed before any score was seen.
TEMPLATES: tuple[str, ...] = ("a photo taken in {place}", "a photograph of {place}", "{place}")

# CLIP multiplies similarities by 100 before turning them into probabilities when it is used to
# choose between labels. The same scale is used here, so `prob` is CLIP's own probability for
# the true place among the candidates of the line-up. Fixed before any score was seen.
LOGIT_SCALE = 100.0

# The fairness rule. Every candidate in a line-up is a bare place name, all written the same way.
# A word that describes what a picture shows would let CLIP match the word to the pixels without
# knowing the place: "the porticoes of Bologna" beats "Paris" on any picture with arches in it.
# So no candidate may contain one of these words, singular or plural.
_SHOWN_IN_THE_PHOTOGRAPHS = """
    portico portici arcade arch street square sunset lake water fountain reflection column
    concrete brutalist larch tree mountain rock road car sky sign
"""  # from the table of the six photographs in docs/BRIEF.md
_KINDS_OF_PLACE = """
    city town village building estate tower house church bridge river sea beach forest valley
    hill peak park garden centre center old
"""
BANNED_WORDS = frozenset((_SHOWN_IN_THE_PHOTOGRAPHS + _KINDS_OF_PLACE).split())
# Words that belong to the templates, not to a place name.
TEMPLATE_WORDS = frozenset({"photo", "photograph", "picture", "image", "taken"})
LINEUP_MIN, LINEUP_MAX = 10, 12


@dataclass(frozen=True)
class PlaceEntry:
    """What data/places.yaml says about one photograph."""

    image: str  # the photograph's file name without its extension
    place: str  # the true place, one of the line-up's candidates
    lineup_name: str
    lineup: tuple[str, ...]  # the candidates, the true place among them
    ladder: tuple[str, ...]  # from the true place to a generic kind of place
    # True when the photograph was put in as a negative control: a picture predicted, before
    # any scoring, not to have its true place come first
    negative_control: bool = False


def _words(label: str) -> list[str]:
    return re.findall(r"[^\W\d_]+", label.lower())


def banned_words_in(label: str) -> list[str]:
    """The descriptive words in a label, as written. Whole words only, singular or plural."""
    found = []
    for word in _words(label):
        forms = {word, word.removesuffix("s"), word.removesuffix("es")}
        if word.endswith("ies"):
            forms.add(word[:-3] + "y")
        if forms & BANNED_WORDS:
            found.append(word)
    return found


def _check_bare(where: str, label) -> None:
    """A label is a name and nothing else: the templates add the words around it."""
    if (
        not isinstance(label, str)
        or "{" in label
        or "}" in label
        or TEMPLATE_WORDS & set(_words(label))
    ):
        raise ValueError(f"{where} must be a bare place name with no template text around it")


def _check_lineup(name: str, candidates) -> None:
    if not isinstance(candidates, list) or not LINEUP_MIN <= len(candidates) <= LINEUP_MAX:
        n = len(candidates) if isinstance(candidates, list) else 0
        raise ValueError(
            f"line-up {name!r} has {n} candidates; a line-up has {LINEUP_MIN} to {LINEUP_MAX}"
        )
    seen: set[str] = set()
    for label in candidates:
        where = f"line-up {name!r}: candidate {label!r}"
        _check_bare(where, label)
        place_name, _, region = label.partition(",")
        if label.count(",") != 1 or not place_name.strip() or not region.strip():
            raise ValueError(f"{where} must be written as 'Name, Region' like every candidate")
        bad = banned_words_in(label)
        if bad:
            raise ValueError(
                f"{where} contains {', '.join(bad)}: a word that describes what a picture shows. "
                "Candidates must be bare names (the fairness rule)."
            )
        if label.casefold() in seen:
            raise ValueError(f"line-up {name!r} lists {label!r} twice")
        seen.add(label.casefold())
    if len({label.lower().startswith("the ") for label in candidates}) > 1:
        raise ValueError(
            f"line-up {name!r} mixes names with and without 'the'; every candidate must be "
            "written in the same form"
        )


def load_places(path: str | Path) -> dict[str, PlaceEntry]:
    """Read and check data/places.yaml. Returns one PlaceEntry per photograph, keyed by its stem.

    Raises ValueError, naming the entry, when the file breaks a rule: a line-up has 10 to 12
    different candidates, every candidate is a bare 'Name, Region' with no descriptive word and
    no template text, the true place is one of the candidates, and the ladder starts at the true
    place and has at least two rungs.
    """
    try:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise ValueError(f"{path} is not valid YAML: {' '.join(str(e).split())}") from e
    if not isinstance(raw, dict) or not isinstance(raw.get("lineups"), dict):
        raise ValueError(f"{path} needs a 'lineups' section and a 'photographs' section")
    lineups = raw["lineups"]
    for name, candidates in lineups.items():
        _check_lineup(name, candidates)
    places: dict[str, PlaceEntry] = {}
    for stem, item in (raw.get("photographs") or {}).items():
        if not isinstance(item, dict):
            raise ValueError(f"{stem}: a photograph needs a place, a lineup and a ladder")
        lineup_name, place = item.get("lineup"), item.get("place")
        ladder = item.get("ladder")
        if lineup_name not in lineups:
            raise ValueError(
                f"{stem}: unknown line-up {lineup_name!r}; the file defines {sorted(lineups)}"
            )
        if place not in lineups[lineup_name]:
            raise ValueError(f"{stem}: the true place {place!r} is not in line-up {lineup_name!r}")
        for rung in ladder if isinstance(ladder, list) else []:
            _check_bare(f"{stem}: ladder rung {rung!r}", rung)
        if not isinstance(ladder, list) or len(ladder) < 2 or len(set(ladder)) != len(ladder):
            raise ValueError(
                f"{stem}: a ladder needs at least two different rungs, the true place first and "
                "a generic kind of place last"
            )
        if ladder[0] != place:
            raise ValueError(
                f"{stem}: the first rung of the ladder must be the true place {place!r}, "
                f"not {ladder[0]!r}"
            )
        places[stem] = PlaceEntry(
            image=stem,
            place=place,
            lineup_name=lineup_name,
            lineup=tuple(lineups[lineup_name]),
            ladder=tuple(ladder),
            negative_control=bool(item.get("negative_control", False)),
        )
    return places


def registered_sha(places: dict[str, PlaceEntry], templates: tuple[str, ...] = TEMPLATES) -> str:
    """A fingerprint of everything that was registered before any score was seen: each
    photograph's place, line-up and ladder, the wordings, and the scale.

    It is written into every results file, and a test holds the registered value. So if a
    candidate, a rung or a wording is changed later, the test fails, and results made before
    and after the change can be told apart. Comments and the `changes` list in the places file
    are not part of it, so a correction can be logged without changing the fingerprint.
    """
    return stable_hash(
        {
            "photographs": {stem: asdict(entry) for stem, entry in places.items()},
            "templates": list(templates),
            "logit_scale": LOGIT_SCALE,
        }
    )


@cache
def text_vector(embedder: Embedder, text: str) -> np.ndarray:
    """The embedder's unit vector for one text, remembered for the life of the process.

    The same place names are asked for at every generation of every chain, so each is embedded
    once per embedder. Callers must not change the returned array.
    """
    vec = np.asarray(embedder.embed_text(text), dtype=np.float64)
    return vec / (np.linalg.norm(vec) + 1e-12)


def place_vector(
    embedder: Embedder, place: str, templates: tuple[str, ...] = TEMPLATES
) -> np.ndarray:
    """One unit vector for a place: the average of its templates, made unit length again.

    This is prompt ensembling. The average of unit vectors is shorter than 1, so it is
    renormalised; otherwise a place whose wordings disagree would score lower for that alone.
    """
    mean = np.mean([text_vector(embedder, t.format(place=place)) for t in templates], axis=0)
    return mean / (np.linalg.norm(mean) + 1e-12)


def _unit(vec: np.ndarray) -> np.ndarray:
    vec = np.asarray(vec, dtype=np.float64)
    return vec / (np.linalg.norm(vec) + 1e-12)


def _rank(sims: list[float], true_index: int) -> tuple[int, int]:
    """(rank of the true candidate counted from 1, index of the candidate ranked first).

    Candidates are sorted by similarity, highest first. In an exact tie the true place goes
    last, so rank 1 always means it beat every other candidate outright.
    """
    order = sorted(range(len(sims)), key=lambda i: (-sims[i], i == true_index))
    return order.index(true_index) + 1, order[0]


def score_lineup(
    image_vec: np.ndarray,
    lineup: tuple[str, ...],
    place: str,
    embedder: Embedder,
    templates: tuple[str, ...] = TEMPLATES,
) -> dict:
    """Where the true `place` comes among the candidates of a line-up, for one picture.

    Returns
      rank               1 means that, of these names, the true one matched the picture best;
                         len(lineup) is last
      prob               softmax probability of the true place over the line-up
      top                the candidate ranked first
      rival              the best candidate other than the true place: the runner-up when the
                         true place is first, otherwise the same as `top`
      margin             similarity of the true place minus similarity of the rival. Positive:
                         the true place is ahead by this much. Negative: behind by this much
      per_template_rank  the rank under each wording on its own, to show wording sensitivity

    A rank is only as hard to earn as the line-up makes it, and line-ups are not equally hard.
    Rank 1 is a result about the names in this line-up and nothing more, so quote it with prob,
    rival and margin beside it, and do not compare ranks between photographs that use
    different line-ups.
    """
    lineup = tuple(lineup)
    if place not in lineup:
        raise ValueError(f"{place!r} is not in the line-up {list(lineup)}")
    if len(lineup) < 2:
        raise ValueError("a line-up needs the true place and at least one other candidate")
    true_index = lineup.index(place)
    image_vec = _unit(image_vec)
    sims = [float(np.dot(image_vec, place_vector(embedder, c, templates))) for c in lineup]
    rank, top_index = _rank(sims, true_index)
    rival_index = max((i for i in range(len(lineup)) if i != true_index), key=lambda i: sims[i])
    logits = LOGIT_SCALE * np.array(sims)
    weights = np.exp(logits - logits.max())  # subtracting the largest keeps exp() in range
    per_template_rank = {}
    for t in templates:
        t_sims = [
            float(np.dot(image_vec, text_vector(embedder, t.format(place=c)))) for c in lineup
        ]
        per_template_rank[t] = _rank(t_sims, true_index)[0]
    return {
        "rank": rank,
        "prob": float(weights[true_index] / weights.sum()),
        "top": lineup[top_index],
        "rival": lineup[rival_index],
        "margin": sims[true_index] - sims[rival_index],
        "per_template_rank": per_template_rank,
    }


def score_ladder(
    image_vec: np.ndarray,
    ladder: tuple[str, ...],
    embedder: Embedder,
    templates: tuple[str, ...] = TEMPLATES,
) -> dict:
    """How well one picture matches each rung of a ladder that runs from specific to generic,
    for example "Bologna, Italy" > "Italy" > "Europe" > "a city".

    Returns
      ladder                  [{"label", "sim"}] in the ladder's own order
      best_rung               the label with the highest similarity
      specific_minus_generic  sim(first rung) - sim(last rung)

    Neither the size nor the sign of that margin means much on its own: how well a generic
    phrase such as "a city" matches depends on the photograph and on the phrase. The rungs are
    also not the same kind of thing for every photograph (the second rung is a country for
    Bologna and a city for the Barbican). So ladder numbers are not compared between
    photographs. Only the CHANGE of one photograph's margin from one generation to the next
    is read: a falling margin means the picture now matches the name of the place less well,
    next to the generic phrase, than it did.
    """
    image_vec = _unit(image_vec)
    rungs = [
        {"label": label, "sim": float(np.dot(image_vec, place_vector(embedder, label, templates)))}
        for label in ladder
    ]
    return {
        "ladder": rungs,
        "best_rung": max(rungs, key=lambda r: r["sim"])["label"],
        "specific_minus_generic": rungs[0]["sim"] - rungs[-1]["sim"],
    }


def _score_vector(
    image_vec: np.ndarray, entry: PlaceEntry, embedder: Embedder, templates: tuple[str, ...]
) -> dict:
    return {
        "place": entry.place,
        "lineup": entry.lineup_name,
        "lineup_size": len(entry.lineup),
        **score_lineup(image_vec, entry.lineup, entry.place, embedder, templates),
        **score_ladder(image_vec, entry.ladder, embedder, templates),
    }


def score_place(
    image: bytes, entry: PlaceEntry, embedder: Embedder, templates: tuple[str, ...] = TEMPLATES
) -> dict:
    """Everything the place test says about one image: the line-up result (rank, prob, top,
    per_template_rank) and the ladder result (ladder, best_rung, specific_minus_generic), with
    the true place and the line-up's name and size. See score_lineup and score_ladder."""
    return _score_vector(embedder.embed(image), entry, embedder, templates)


def model_label(embedder: object) -> str:
    """The model that did the scoring, written into every result: the network, the weights,
    the activation the network was built with and the library that built it, for example
    'ViT-B-32/openai/quickgelu/open_clip-4.2.2'. An embedder that does not know one of these
    leaves it out.

    The activation and the library are part of the label because the same network and weights
    gave different numbers when a version of the library built them with the wrong activation.
    Two builds must never share a label.
    """
    name = getattr(embedder, "model_name", None)
    if not name:
        return type(embedder).__name__
    parts = [name] + [getattr(embedder, a, "") for a in ("pretrained", "activation", "library")]
    return "/".join(part for part in parts if part)


def provenance(
    embedder: object,
    places: dict[str, PlaceEntry],
    places_file: str | Path,
    templates: tuple[str, ...] = TEMPLATES,
) -> dict:
    """What a set of scores was made with. Written into every results file, so a number can
    always be traced to the model, the wordings and the line-ups behind it.

      clip_model          the model as it really ran (see model_label)
      preprocessing       what the model is shown of a picture, as the embedder states it
      templates           the wordings each place name was put into
      logit_scale         the scale that turns similarities into prob
      places_file_sha256  sha256 of the places file as it was when the scores were made
      registered_sha      fingerprint of the line-ups, ladders and wordings alone (see
                          registered_sha): unchanged when only a note is added to the file
    """
    return {
        "clip_model": model_label(embedder),
        "preprocessing": getattr(embedder, "preprocessing", None) or "not known",
        "templates": list(templates),
        "logit_scale": LOGIT_SCALE,
        "places_file_sha256": sha256_bytes(Path(places_file).read_bytes()),
        "registered_sha": registered_sha(places, templates),
    }


def calibrate_places(
    images: dict[str, bytes],
    places: dict[str, PlaceEntry],
    embedder: Embedder,
    templates: tuple[str, ...] = TEMPLATES,
) -> dict:
    """Where does the true place come in its line-up before any loop has run?

    `images` maps a photograph's stem to its generation-0 bytes. Returns
      photographs  each photograph scored in its own line-up (as score_place)
      cross        each photograph scored against every place it was NOT taken in, inside that
                   place's own line-up: a check that, say, the Dolomites picture does not put
                   Bologna first among the cities
    Photographs without an entry in `places` are left out. A line-up always ranks something
    first, so a rank of 1 in the cross table is a warning, not a result. What the scores were
    made with is not in here: whoever saves them adds it (see provenance).
    """
    targets: dict[tuple[str, str], PlaceEntry] = {}  # one entry for each different place
    for entry in places.values():
        targets.setdefault((entry.lineup_name, entry.place), entry)
    photographs, cross = [], []
    for stem in sorted(images):
        if stem not in places:
            continue
        entry = places[stem]
        vec = embedder.embed(images[stem])
        photographs.append(
            {
                "image": stem,
                "negative_control": entry.negative_control,
                **_score_vector(vec, entry, embedder, templates),
            }
        )
        for (lineup_name, place), other in targets.items():
            if (lineup_name, place) == (entry.lineup_name, entry.place):
                continue
            res = score_lineup(vec, other.lineup, place, embedder, templates)
            cross.append(
                {
                    "image": stem,
                    "place": place,
                    "lineup": lineup_name,
                    "lineup_size": len(other.lineup),
                    "rank": res["rank"],
                    "prob": res["prob"],
                    "top": res["top"],
                }
            )
    return {"photographs": photographs, "cross": cross}


def round_floats(value, digits: int = 4):
    """A copy of a result with every float rounded, so a saved file is the same on any machine
    (CLIP's last decimals differ slightly between computers)."""
    if isinstance(value, float):
        return round(value, digits)
    if isinstance(value, dict):
        return {k: round_floats(v, digits) for k, v in value.items()}
    if isinstance(value, list):
        return [round_floats(v, digits) for v in value]
    return value
