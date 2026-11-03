"""Experiment definitions: YAML in experiments/ expands to a list of ChainConfigs.

Schema (see experiments/*.yaml):
  id, title, description, question      documentation, copied into the export
  images: [globs]                        generation-0 images; "fixtures" expands to data/fixtures/*.png
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

    def resolve_images(self, root: Path = Path(".")) -> list[Path]:
        out: list[Path] = []
        for pat in self.images:
            if pat == "fixtures":
                pat = "data/fixtures/*.png"
            matches = sorted(glob.glob(str(root / pat)))
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
        root: Path = Path("."),
        images: list[Path] | None = None,
        generations: int | None = None,
        repeats: int | None = None,
    ) -> list[ChainConfig]:
        imgs = images if images is not None else self.resolve_images(root)
        gens = generations or self.generations
        reps = repeats or self.repeats
        chains: list[ChainConfig] = []
        for variant in self.variants:
            stations = [StationConfig(**s) for s in variant["stations"]]
            for img in imgs:
                for r in range(reps):
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


def load_all(folder: Path = Path("experiments")) -> dict[str, Experiment]:
    exps = [Experiment.load(p) for p in sorted(Path(folder).glob("*.yaml"))]
    return {e.id: e for e in exps}


def find(name: str, folder: Path = Path("experiments")) -> Experiment:
    exps = load_all(folder)
    if name in exps:
        return exps[name]
    for k, e in exps.items():
        if k.startswith(name) or (e.path and e.path.stem.startswith(name)):
            return e
    raise KeyError(f"No experiment matching {name!r}. Known: {sorted(exps)}")
