"""FastAPI service.

Static results come from the web export (so the site needs no server at all). The optional
/live endpoints run a short chain on one of the author's photographs, behind a per-IP rate
limit, a daily spend cap and the station cache. They are off unless TELEPHONE_LIVE=1.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from collections import deque
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from telephone.config import get_settings
from telephone.export import _private_stems, export_chain
from telephone.ledger import Ledger
from telephone.models import ChainConfig, StationConfig
from telephone.paths import project_root

settings = get_settings()
EXPORT_DIR = project_root() / "web" / "public" / "data"
app = FastAPI(title="Telephone API", version="0.1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"]
)

PRESETS: dict[str, tuple[str, list[StationConfig]]] = {
    "telephone": (
        "platform → caption → regenerate",
        [
            StationConfig(kind="platform", params={"preset": "instagram"}),
            StationConfig(kind="caption", params={"mode": "detailed"}),
            StationConfig(kind="regenerate"),
        ],
    ),
    "short_caption": (
        "platform → one-sentence caption → regenerate",
        [
            StationConfig(kind="platform", params={"preset": "instagram"}),
            StationConfig(kind="caption", params={"mode": "short"}),
            StationConfig(kind="regenerate"),
        ],
    ),
    "compression": (
        "harsh platform recompression only",
        [StationConfig(kind="platform", params={"preset": "harsh"})],
    ),
}
MAX_GENERATIONS = 6


def _data_root() -> Path:
    return EXPORT_DIR if (EXPORT_DIR / "index.json").exists() else EXPORT_DIR / "sample"


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"ok": True, "live": settings.telephone_live, "data": str(_data_root())}


@app.get("/api/index")
def index() -> Any:
    p = _data_root() / "index.json"
    if not p.exists():
        raise HTTPException(404, "No export yet. Run `telephone export`.")
    return JSONResponse(json.loads(p.read_text()))


@app.get("/api/chains/{key}")
def chain(key: str) -> Any:
    p = _data_root() / "chains" / f"{key}.json"
    if not p.exists():
        raise HTTPException(404, "unknown chain")
    return JSONResponse(json.loads(p.read_text()))


@app.get("/api/img/{key}/{name}")
def image(key: str, name: str) -> Any:
    p = _data_root() / "img" / key / name
    if not p.exists() or ".." in key or ".." in name:
        raise HTTPException(404)
    return FileResponse(p)


# -- live runs ----------------------------------------------------------------------------


class LiveRequest(BaseModel):
    image: str = Field(description="Stem of one of the author's originals, as listed in the export")
    preset: str = "telephone"
    generations: int = Field(4, ge=1, le=MAX_GENERATIONS)


class _Limiter:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.per_ip: dict[str, deque[float]] = {}
        self.day = time.strftime("%Y-%m-%d")
        self.spent_today = 0.0

    def check(self, ip: str) -> None:
        with self.lock:
            today = time.strftime("%Y-%m-%d")
            if today != self.day:
                self.day, self.spent_today = today, 0.0
            if self.spent_today >= settings.telephone_live_daily_cap_usd:
                raise HTTPException(
                    429,
                    "Daily spend cap for live runs reached. Come back tomorrow, or browse the recorded chains.",
                )
            q = self.per_ip.setdefault(ip, deque())
            now = time.time()
            while q and now - q[0] > 60:
                q.popleft()
            if len(q) >= settings.telephone_live_rpm_per_ip:
                raise HTTPException(429, "Too many live runs from this address. Wait a minute.")
            q.append(now)

    def add(self, usd: float) -> None:
        with self.lock:
            self.spent_today += usd

    def remaining(self) -> float:
        return max(0.0, settings.telephone_live_daily_cap_usd - self.spent_today)


limiter = _Limiter()
jobs: dict[str, dict[str, Any]] = {}
jobs_lock = threading.Lock()
queue: deque[str] = deque()
worker_started = False


def _find_original(stem: str) -> Path:
    if stem in _private_stems():
        raise HTTPException(404, f"No original named {stem}")  # private photos are never served
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        p = settings.originals_dir / f"{stem}{ext}"
        if p.exists():
            return p
    for ext in (".png", ".jpg"):
        p = settings.fixtures_dir / f"{stem}{ext}"
        if p.exists():
            return p
    raise HTTPException(404, f"No original named {stem}")


def _worker() -> None:
    from telephone.chain import ChainRunner, RunnerOptions

    ledger = Ledger(settings.ledger_path)
    while True:
        with jobs_lock:
            job_id = queue.popleft() if queue else None
        if job_id is None:
            time.sleep(0.5)
            continue
        job = jobs[job_id]
        job["status"] = "running"
        cfg: ChainConfig = job["cfg"]
        out_dir = EXPORT_DIR / "live"
        before, _ = ledger.total_cost()

        def on_event(kind: str, data: dict, _job=job, _cfg=cfg, _out=out_dir) -> None:
            if kind == "generation":
                recs = ledger.chain(_cfg.chain_id, _cfg.repeat)
                _job["chain"] = _export(recs, _out)
            elif kind in ("error", "warning"):
                _job.setdefault("notes", []).append(data.get("message"))

        try:
            runner = ChainRunner(
                ledger=ledger,
                options=RunnerOptions(
                    compute_clip=True,
                    extractor=StationConfig(kind="extract", provider=settings.default_captioner),
                ),
                on_event=on_event,
            )
            recs = runner.run(cfg)
            job["chain"] = _export(recs, out_dir)
            job["status"] = "done"
        except Exception as e:  # noqa: BLE001
            job["status"] = "error"
            job["error"] = f"{type(e).__name__}: {e}"
        after, _ = ledger.total_cost()
        limiter.add(max(0.0, after - before))


def _export(recs, out_dir: Path) -> dict[str, Any]:
    if not recs:
        return {}
    export_chain(recs, out_dir, thumb_size=512, full_size=1280, experiment_meta=None)
    key = f"{recs[0].chain_id}__r{recs[0].repeat}"
    doc = json.loads((out_dir / "chains" / f"{key}.json").read_text())
    # rewrite image paths to the API route so the SPA can show them from any origin
    for g in doc["generations"]:
        for k in ("thumb", "full"):
            if g[k]:
                g[k] = "live/" + g[k]
    return doc


def _ensure_worker() -> None:
    global worker_started
    if not worker_started:
        threading.Thread(target=_worker, daemon=True).start()
        worker_started = True


@app.get("/api/live/status")
def live_status() -> dict[str, Any]:
    return {
        "enabled": settings.telephone_live,
        "daily_cap_usd": settings.telephone_live_daily_cap_usd,
        "remaining_usd": limiter.remaining(),
        "presets": {k: v[0] for k, v in PRESETS.items()},
        "max_generations": MAX_GENERATIONS,
    }


@app.post("/api/live")
def live_start(req: LiveRequest, request: Request) -> dict[str, Any]:
    if not settings.telephone_live:
        raise HTTPException(403, "Live runs are disabled (TELEPHONE_LIVE=0).")
    if req.preset not in PRESETS:
        raise HTTPException(400, f"Unknown preset; choose from {sorted(PRESETS)}")
    limiter.check(request.client.host if request.client else "unknown")
    original = _find_original(req.image)
    cfg = ChainConfig(
        chain_id=f"live__{req.preset}__{original.stem}",
        experiment_id="live",
        image=str(original),
        stations=PRESETS[req.preset][1],
        generations=req.generations,
        seed=settings.default_seed,
    )
    job_id = uuid.uuid4().hex[:10]
    with jobs_lock:
        jobs[job_id] = {
            "id": job_id,
            "status": "queued",
            "chain": None,
            "cfg": cfg,
            "created": time.time(),
        }
        queue.append(job_id)
        position = len(queue)
    _ensure_worker()
    return {"id": job_id, "status": "queued", "chain": None, "position": position}


@app.get("/api/live/{job_id}")
def live_job(job_id: str) -> dict[str, Any]:
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "unknown job")
    return {k: v for k, v in job.items() if k != "cfg"}


@app.get("/api/live/img/{key}/{name}")
def live_image(key: str, name: str) -> Any:
    p = EXPORT_DIR / "live" / "img" / key / name
    if not p.exists() or ".." in key or ".." in name:
        raise HTTPException(404)
    return FileResponse(p)
