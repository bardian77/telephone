"""Experiment definitions: YAML in experiments/ expands to a list of ChainConfigs.

Schema (see experiments/*.yaml):
  id, title, description, question      documentation, copied into the export
  images: [globs]                        generation-0 images; "fixtures" means the synthetic test
                                         images; "data/..." is relative to TELEPHONE_DATA_DIR
  generations, seed, repeats             defaults 12, 7, 1
  extractor: {provider, model} | null    attribute extraction at every generation
  variants:                              one chain per image x variant x repeat
    - name: short
      stations: [{kind, provider?, model?, params?}, ...]
  metrics: {clip: true, lpips: false}    optional
"""

from __future__ import annotations

import glob
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .models import ChainConfig, StationConfig


@dataclass
class Experiment:
    id: str
    title: str
    description: str = ""
    question: str = ""
    images: list[str] = field(default_factory=list)
    generations: int = 12
    seed: int = 7
    repeats: int = 1
    extractor: dict[str, Any] | None = None
    variants: list[dict[str, Any]] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    references: list[str] = field(default_factory=list)
    path: Path | None = None

    @classmethod
    def load(cls, path: Path) -> Experiment:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        known = {f for f in cls.__dataclass_fields__ if f != "path"}
        return cls(**{k: v for k, v in raw.items() if k in known}, path=Path(path))

    def resolve_images(self, root: Path | None = None) -> list[Path]:
        """Images matching the experiment's patterns.

        `fixtures` means the synthetic test images in the data dir. A pattern starting with
        `data/` is relative to the configured data dir (TELEPHONE_DATA_DIR), any other relative
        pattern to the project root, so this works from any folder. Sub-folders such as
        `data/originals/private/` are not searched: the patterns are not recursive.
        """
        from .config import get_settings
        from .paths import project_root

        root = root or project_root()
        data_dir = get_settings().telephone_data_dir
        out: list[Path] = []
        for pat in self.images:
            if pat == "fixtures":
                full = str(data_dir / "fixtures" / "*.png")
            elif pat.startswith("data/"):
                full = str(data_dir / pat[len("data/") :])
            elif Path(pat).is_absolute():
                full = pat
            else:
                full = str(root / pat)
            matches = sorted(glob.glob(full))
            out.extend(Path(m) for m in matches)
        # de-duplicate, keep order
        seen: set[Path] = set()
        return [p for p in out if not (p in seen or seen.add(p))]

    def extractor_config(self) -> StationConfig | None:
        if not self.extractor:
            return None
        return StationConfig(
            kind="extract",
            provider=self.extractor.get("provider"),
            model=self.extractor.get("model"),
        )

    def chains(
        self,
        root: Path | None = None,
        images: list[Path] | None = None,
        generations: int | None = None,
        repeats: int | None = None,
    ) -> list[ChainConfig]:
        imgs = images if images is not None else self.resolve_images(root)
        gens = generations or self.generations
        reps = repeats or self.repeats
        chains: list[ChainConfig] = []
        for variant in self.variants:
            for img in imgs:
                for r in range(reps):
                    fill = {
                        "image_stem": img.stem,
                        "experiment_id": self.id,
                        "variant": variant["name"],
                        "repeat": r,
                    }
                    # fresh StationConfig objects per chain: a chain must never share mutable
                    # params with another chain (the --physical-root override edits them)
                    stations = [
                        StationConfig(
                            **{
                                **s,
                                "params": {
                                    k: _fill_placeholders(v, fill)
                                    for k, v in (s.get("params") or {}).items()
                                },
                            }
                        )
                        for s in variant["stations"]
                    ]
                    chains.append(
                        ChainConfig(
                            chain_id=f"{self.id}__{variant['name']}__{img.stem}",
                            experiment_id=self.id,
                            image=str(img),
                            stations=stations,
                            generations=int(variant.get("generations", gens)),
                            seed=int(variant.get("seed", self.seed)) + r,
                            repeat=r,
                            notes=variant.get("notes"),
                        )
                    )
        return chains

    def summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "question": self.question,
            "generations": self.generations,
            "repeats": self.repeats,
            "variants": [
                {"name": v["name"], "stations": v["stations"], "notes": v.get("notes")}
                for v in self.variants
            ],
            "extractor": self.extractor,
            "references": self.references,
        }


PLACEHOLDERS = ("image_stem", "experiment_id", "variant", "repeat")


def _fill_placeholders(value: Any, fill: dict[str, Any]) -> Any:
    """Substitute the known {placeholders} in a string param; anything else is left alone."""
    if not isinstance(value, str) or "{" not in value:
        return value
    for key in PLACEHOLDERS:
        value = value.replace("{" + key + "}", str(fill[key]))
    return value


MOCK_SUFFIX = "-mock"


def mockify(chain: ChainConfig) -> ChainConfig:
    """A copy of the chain with every model station on the mock provider.

    The experiment id gets a '-mock' suffix (a hyphen: the chain id parser splits on '__'), so
    mock rows never share a chain id with real ones and can never be resumed as real results.
    An experiment that already declares mock providers everywhere keeps its id.
    """
    model_stations = [s for s in chain.stations if s.kind in ("caption", "regenerate", "extract")]
    already_mock = bool(model_stations) and all(s.provider == "mock" for s in model_stations)
    stations = [
        s.model_copy(update={"provider": "mock", "model": None})
        if s.kind in ("caption", "regenerate", "extract")
        else s.model_copy(deep=True)
        for s in chain.stations
    ]
    if already_mock or chain.experiment_id.endswith(MOCK_SUFFIX):
        return chain.model_copy(update={"stations": stations})
    new_exp = chain.experiment_id + MOCK_SUFFIX
    prefix = chain.experiment_id + "__"
    new_chain = (
        new_exp + "__" + chain.chain_id[len(prefix) :]
        if chain.chain_id.startswith(prefix)
        else new_exp + "__" + chain.chain_id
    )
    return chain.model_copy(
        update={"experiment_id": new_exp, "chain_id": new_chain, "stations": stations}
    )


def experiments_dir() -> Path:
    from .paths import project_root

    return project_root() / "experiments"


def load_all(folder: Path | None = None) -> dict[str, Experiment]:
    folder = folder or experiments_dir()
    exps = [Experiment.load(p) for p in sorted(Path(folder).glob("*.yaml"))]
    return {e.id: e for e in exps}


def find(name: str, folder: Path | None = None) -> Experiment:
    exps = load_all(folder)
    if name in exps:
        return exps[name]
    for k, e in exps.items():
        if k.startswith(name) or (e.path and e.path.stem.startswith(name)):
            return e
    raise KeyError(f"No experiment matching {name!r}. Known: {sorted(exps)}")
