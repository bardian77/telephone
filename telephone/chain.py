"""Run one chain: original image -> stations -> output, repeated for N generations, everything logged."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .cache import StationCache
from .config import Settings, get_settings
from .imageio import load_image, media_type_of, save_bytes, sha256_bytes, to_png_bytes
from .ledger import Ledger
from .metrics import (
    ClipEmbedder,
    MetricsUnavailable,
    compare_attributes,
    cosine_distance,
    face_count,
    histogram_distance,
    lpips_distance,
    ocr_stats,
    ssim_score,
)
from .models import Attributes, ChainConfig, GenerationRecord, Metrics, StationConfig, Survival
from .stations import MissingFrame, Station, build_station
from .stations.base import StationContext
from .stations.extract import ExtractStation

log = logging.getLogger("telephone")

Event = Callable[[str, dict], None]


@dataclass
class RunnerOptions:
    compute_clip: bool = True
    compute_lpips: bool = False
    compute_readability: bool = True
    stop_on_error: bool = True
    extractor: StationConfig | None = None  # None: no attribute extraction


@dataclass
class ChainRunner:
    settings: Settings = field(default_factory=get_settings)
    ledger: Ledger | None = None
    cache: StationCache | None = None
    options: RunnerOptions = field(default_factory=RunnerOptions)
    on_event: Event | None = None
    _clip: ClipEmbedder | None = field(default=None, init=False, repr=False)
    _clip_failed: bool = field(default=False, init=False)
    _lpips_failed: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if self.ledger is None:
            self.ledger = Ledger(self.settings.ledger_path, self.settings.ledger_jsonl)
        if self.cache is None:
            self.cache = StationCache(self.settings.cache_dir)

    # -- helpers -----------------------------------------------------------------------------
    def emit(self, kind: str, **data) -> None:
        if self.on_event:
            self.on_event(kind, data)

    def _clip_embed(self, image: bytes):
        if not self.options.compute_clip or self._clip_failed:
            return None
        try:
            if self._clip is None:
                self._clip = ClipEmbedder.shared()
            return self._clip.embed(image)
        except MetricsUnavailable as e:
            self._clip_failed = True
            log.warning("CLIP unavailable, recording None for clip distances: %s", e)
            self.emit("warning", message=f"CLIP unavailable: {e}")
            return None

    def _lpips(self, a: bytes, b: bytes) -> float | None:
        if not self.options.compute_lpips or self._lpips_failed:
            return None
        try:
            return lpips_distance(a, b)
        except MetricsUnavailable as e:
            self._lpips_failed = True
            log.warning("LPIPS unavailable: %s", e)
            return None

    def _out_path(self, cfg: ChainConfig, generation: int, data: bytes) -> Path:
        ext = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}.get(
            media_type_of(data), "bin"
        )
        safe_chain = cfg.chain_id.replace("/", "__")
        return (
            self.settings.runs_dir
            / cfg.experiment_id
            / safe_chain
            / f"r{cfg.repeat}"
            / f"{generation:03d}.{ext}"
        )

    def _metrics(self, data: bytes, g0: bytes, prev: bytes, g0_emb, prev_emb, emb) -> Metrics:
        from .imageio import from_bytes

        img = from_bytes(data)
        m = Metrics(width=img.width, height=img.height, file_bytes=len(data))
        m.hist_dist_to_g0 = histogram_distance(g0, data)
        m.hist_dist_to_prev = histogram_distance(prev, data)
        if emb is not None and g0_emb is not None:
            m.clip_dist_to_g0 = cosine_distance(g0_emb, emb)
        if emb is not None and prev_emb is not None:
            m.clip_dist_to_prev = cosine_distance(prev_emb, emb)
        m.ssim_to_g0 = ssim_score(g0, data)
        m.ssim_to_prev = ssim_score(prev, data)
        m.lpips_to_g0 = self._lpips(g0, data)
        if self.options.compute_readability:
            ocr = ocr_stats(data)
            if ocr is not None:
                m.ocr_chars, m.ocr_words = ocr
            m.face_count = face_count(data)
        return m

    def _extract(self, data: bytes, ctx: StationContext) -> tuple[Attributes | None, list]:
        if self.options.extractor is None:
            return None, []
        st = ExtractStation(self.options.extractor)
        res = st.run(data, sha256_bytes(data), ctx)
        return res.attributes, [res.record]

    # -- main --------------------------------------------------------------------------------
    def estimate(self, cfg: ChainConfig) -> tuple[int, float]:
        """(paid calls, estimated USD) for a full run of this chain, ignoring the cache."""
        stations = [build_station(s) for s in cfg.stations]
        per_gen = sum(s.estimated_cost_usd() for s in stations)
        calls = sum(1 for s in stations if s.kind in ("caption", "regenerate"))
        if self.options.extractor is not None:
            ex = ExtractStation(self.options.extractor)
            per_gen += ex.estimated_cost_usd()
            calls += 1
        n_extract_g0 = 1 if self.options.extractor is not None else 0
        return calls * cfg.generations + n_extract_g0, per_gen * cfg.generations + (
            ex.estimated_cost_usd() if self.options.extractor else 0
        )

    def run(self, cfg: ChainConfig, run_id: str | None = None) -> list[GenerationRecord]:
        assert self.ledger is not None and self.cache is not None
        run_id = run_id or uuid.uuid4().hex[:12]
        stations: list[Station] = [build_station(s) for s in cfg.stations]
        records: list[GenerationRecord] = []

        # generation 0 ---------------------------------------------------------------------
        g0_rec = self.ledger.get(cfg.chain_id, 0, cfg.repeat)
        if g0_rec is not None and Path(g0_rec.output_path).exists():
            g0 = Path(g0_rec.output_path).read_bytes()
            self.emit("resume", chain_id=cfg.chain_id, generation=0)
        else:
            g0 = to_png_bytes(load_image(cfg.image))
            g0_path = save_bytes(self._out_path(cfg, 0, g0), g0)
            ctx0 = StationContext(
                settings=self.settings,
                cache=self.cache,
                chain=cfg,
                generation=0,
                seed=cfg.seed,
                input_sha=None,
            )
            attrs0, ex_records = self._extract(g0, ctx0)
            g0_rec = GenerationRecord(
                run_id=run_id,
                experiment_id=cfg.experiment_id,
                chain_id=cfg.chain_id,
                repeat=cfg.repeat,
                generation=0,
                station_sequence=cfg.station_sequence(),
                stations=ex_records,
                seed=cfg.seed,
                input_sha=None,
                output_path=str(g0_path),
                output_sha=sha256_bytes(g0),
                attributes=attrs0,
                survival=compare_attributes(attrs0, attrs0) if attrs0 else None,
                metrics=Metrics(
                    width=load_image(cfg.image).width,
                    height=load_image(cfg.image).height,
                    file_bytes=len(g0),
                    clip_dist_to_g0=0.0,
                    hist_dist_to_g0=0.0,
                    ssim_to_g0=1.0,
                ),
                cost_usd=sum(r.usage.cost_usd for r in ex_records),
                list_price_usd=sum(r.usage.list_price_usd for r in ex_records),
                latency_ms=sum(r.usage.latency_ms for r in ex_records),
                error=next((r.error for r in ex_records if r.error), None),
            )
            self.ledger.append(g0_rec)
        records.append(g0_rec)
        self.emit("generation", chain_id=cfg.chain_id, generation=0, record=g0_rec)
        g0_emb = self._clip_embed(g0)
        g0_attrs = g0_rec.attributes

        prev, prev_emb = g0, g0_emb
        for gen in range(1, cfg.generations + 1):
            existing = self.ledger.get(cfg.chain_id, gen, cfg.repeat)
            if (
                existing is not None
                and existing.error is None
                and Path(existing.output_path).exists()
            ):
                prev = Path(existing.output_path).read_bytes()
                prev_emb = self._clip_embed(prev)
                records.append(existing)
                self.emit("resume", chain_id=cfg.chain_id, generation=gen)
                continue

            ctx = StationContext(
                settings=self.settings,
                cache=self.cache,
                chain=cfg,
                generation=gen,
                seed=cfg.seed,
                input_sha=sha256_bytes(prev),
            )
            image = prev
            station_records = []
            error: str | None = None
            try:
                for st in stations:
                    res = st.run(image, sha256_bytes(image), ctx)
                    station_records.append(res.record)
                    if res.caption:
                        ctx.caption = res.caption
                    if res.record.error:
                        error = f"{st.kind}: {res.record.error}"
                        break
                    if res.image is not None:
                        image = res.image
            except MissingFrame as e:
                error = str(e)
                self.emit("missing_frame", chain_id=cfg.chain_id, generation=gen, message=str(e))

            if error:
                rec = GenerationRecord(
                    run_id=run_id,
                    experiment_id=cfg.experiment_id,
                    chain_id=cfg.chain_id,
                    repeat=cfg.repeat,
                    generation=gen,
                    station_sequence=cfg.station_sequence(),
                    stations=station_records,
                    caption=ctx.caption,
                    seed=cfg.seed,
                    input_sha=ctx.input_sha,
                    output_path="",
                    output_sha="",
                    cost_usd=sum(r.usage.cost_usd for r in station_records),
                    list_price_usd=sum(r.usage.list_price_usd for r in station_records),
                    latency_ms=sum(r.usage.latency_ms for r in station_records),
                    error=error,
                )
                self.ledger.append(rec)
                records.append(rec)
                self.emit("error", chain_id=cfg.chain_id, generation=gen, message=error)
                if self.options.stop_on_error:
                    break
                continue

            out_path = save_bytes(self._out_path(cfg, gen, image), image)
            emb = self._clip_embed(image)
            metrics = self._metrics(image, g0, prev, g0_emb, prev_emb, emb)
            attrs, ex_records = self._extract(image, ctx)
            station_records.extend(ex_records)
            survival: Survival | None = (
                compare_attributes(g0_attrs, attrs) if (g0_attrs and attrs) else None
            )
            rec = GenerationRecord(
                run_id=run_id,
                experiment_id=cfg.experiment_id,
                chain_id=cfg.chain_id,
                repeat=cfg.repeat,
                generation=gen,
                station_sequence=cfg.station_sequence(),
                stations=station_records,
                caption=ctx.caption,
                seed=cfg.seed,
                input_sha=ctx.input_sha,
                output_path=str(out_path),
                output_sha=sha256_bytes(image),
                attributes=attrs,
                survival=survival,
                metrics=metrics,
                cost_usd=sum(r.usage.cost_usd for r in station_records),
                list_price_usd=sum(r.usage.list_price_usd for r in station_records),
                latency_ms=sum(r.usage.latency_ms for r in station_records),
            )
            self.ledger.append(rec)
            records.append(rec)
            self.emit("generation", chain_id=cfg.chain_id, generation=gen, record=rec)
            prev, prev_emb = image, emb
        return records
