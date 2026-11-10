"""The dashboard's HTTP layer: a JSON API over service.py and jobs.py, plus the static page.

It is meant for this machine only. `telephone dashboard` binds it to the loopback address, and
every request that changes something is refused when it comes from another website.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ..config import get_settings
from . import service
from .jobs import JobManager
from .reading import BANDS, DIFFERENT_PHOTO_CLIP, FIELD_LABELS

STATIC = Path(__file__).resolve().parent / "static"


class RunRequest(BaseModel):
    experiment: str
    mode: str = Field(description="real, free (no survival form, no key) or simulation")
    photos: list[str] | None = None
    variants: list[str] | None = None
    generations: int | None = None
    clip: bool = True
    confirm_usd: float | None = Field(
        default=None, description="The estimate the person confirmed, for a paid run"
    )


class ExperimentRequest(BaseModel):
    experiment: str


def create_app() -> FastAPI:
    app = FastAPI(title="Telephone dashboard", docs_url=None, redoc_url=None, openapi_url=None)
    jobs = JobManager()
    app.state.jobs = jobs

    @app.middleware("http")
    async def same_origin_only(request: Request, call_next):
        # A page on another website must not be able to start runs on this machine.
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            origin = request.headers.get("origin")
            if origin and urlparse(origin).netloc != request.headers.get("host"):
                return JSONResponse({"detail": "Cross-site request refused."}, status_code=403)
        response = await call_next(request)
        if request.url.path.startswith("/static/") or request.url.path == "/":
            response.headers["Cache-Control"] = "no-cache"
        return response

    @app.exception_handler(service.NotFound)
    async def _not_found(_: Request, exc: service.NotFound):
        return JSONResponse({"detail": str(exc)}, status_code=404)

    @app.exception_handler(service.RunRefused)
    async def _refused(_: Request, exc: service.RunRefused):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    # -- the page ---------------------------------------------------------------------------
    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    # -- reading state ----------------------------------------------------------------------
    @app.get("/api/overview")
    def overview() -> dict[str, Any]:
        from ..doctor import PACKAGES, collect
        from ..experiments import load_all

        d = collect()
        chains = service.all_chain_summaries()
        exps = load_all()
        return {
            "root": d["root"],
            "env_file": d["env_file"],
            "env_file_found": d["env_file_found"],
            "keys": d["keys"],
            "gemini_billing": d["gemini_billing"],
            "spend": d["spend"],
            "packages": [
                {"name": name, "installed": ok, "used_for": PACKAGES[name]}
                for name, ok in d["packages"].items()
            ],
            "clip_ready": bool(d["packages"].get("torch") and d["packages"].get("open_clip")),
            "clip_weights_cached": d["clip_weights_cached"],
            "photos": service.photos(chains),
            "private_photos": d["photos"]["private"],
            "experiments": [
                service.experiment_card(exp, d["experiments"].get(eid, {}))
                for eid, exp in exps.items()
            ],
            "results": service.results_index(chains),
            "saved_results": service.saved_results(),
            "scale": {
                "different_photo": DIFFERENT_PHOTO_CLIP,
                "bands": [
                    {"key": k, "upto": None if u == float("inf") else u, "label": lbl, "meaning": m}
                    for k, u, lbl, m in BANDS
                ],
            },
            "field_labels": FIELD_LABELS,
            "job": jobs.current(),
        }

    @app.get("/api/results")
    def results() -> dict[str, Any]:
        return {"experiments": service.results_index(service.all_chain_summaries())}

    @app.get("/api/results/{experiment_id}")
    def experiment_results(experiment_id: str) -> dict[str, Any]:
        return service.experiment_results(experiment_id)

    @app.get("/api/chains/{key}")
    def chain(key: str) -> dict[str, Any]:
        return service.chain_detail(key)

    # -- pictures ---------------------------------------------------------------------------
    @app.get("/api/image/chain/{key}/{generation}")
    def chain_image(key: str, generation: int, w: int | None = None, raw: int = 0, v: str = ""):
        src, sha = service.chain_image_path(key, generation)
        if raw:
            return FileResponse(src)
        data = service.resized_jpeg(src, w, sha)
        cache = "private, max-age=86400, immutable" if v else "no-cache"
        return Response(data, media_type="image/jpeg", headers={"Cache-Control": cache})

    @app.get("/api/image/photo/{stem}")
    def photo_image(stem: str, w: int | None = None):
        src = service.find_original(stem)
        stat = src.stat()
        data = service.resized_jpeg(src, w, f"orig_{stem}_{int(stat.st_mtime)}_{stat.st_size}")
        return Response(data, media_type="image/jpeg", headers={"Cache-Control": "no-cache"})

    @app.get("/api/figures/{experiment_id}/{name}")
    def figure(experiment_id: str, name: str) -> FileResponse:
        return FileResponse(service.figure_path(experiment_id, name))

    # -- running ----------------------------------------------------------------------------
    def _plan(req: RunRequest) -> service.RunPlan:
        return service.plan_run(
            req.experiment, req.mode, req.photos, req.variants, req.generations, req.clip
        )

    @app.post("/api/estimate")
    def estimate(req: RunRequest) -> dict[str, Any]:
        return service.estimate(_plan(req))

    @app.post("/api/runs")
    def start_run(req: RunRequest) -> dict[str, Any]:
        from ..cost import get_tracker

        plan = _plan(req)
        service.check_budget(plan.estimate_usd, req.confirm_usd, get_tracker().remaining())
        name = service.EXPERIMENT_PLAIN.get(plan.experiment.id, {}).get(
            "name", plan.experiment.title
        )
        return {"job": jobs.start(plan, name)}

    @app.get("/api/runs/current")
    def current_run() -> dict[str, Any]:
        return {"job": jobs.current()}

    @app.post("/api/runs/current/stop")
    def stop_run() -> dict[str, Any]:
        return {"job": jobs.stop()}

    @app.post("/api/runs/current/dismiss")
    def dismiss_run() -> dict[str, Any]:
        jobs.dismiss()
        return {"job": jobs.current()}

    # -- other actions ----------------------------------------------------------------------
    def _idle() -> None:
        if jobs.busy():
            raise HTTPException(409, "A run is in progress. Try again when it has finished.")

    @app.post("/api/actions/load-saved")
    def load_saved(req: ExperimentRequest) -> dict[str, Any]:
        _idle()
        return {"rows": service.load_saved(req.experiment)}

    @app.post("/api/actions/save-snapshot")
    def save_snapshot(req: ExperimentRequest) -> dict[str, Any]:
        _idle()
        return service.save_snapshot(req.experiment)

    @app.post("/api/actions/figures")
    def figures(req: ExperimentRequest) -> dict[str, Any]:
        _idle()
        return {"written": service.make_figures(req.experiment)}

    @app.post("/api/actions/recheck")
    def recheck() -> dict[str, Any]:
        """Read .env again, so a key added while the dashboard is open is noticed."""
        _idle()
        from ..providers import clear_provider_cache

        get_settings.cache_clear()
        clear_provider_cache()
        return {"ok": True}

    return app
