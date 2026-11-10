"""One run at a time, in a background thread, with progress the browser can poll.

A run is every chain of one experiment (or the chosen part of it). The ledger is written as the
run goes, exactly as the command line does, so a run that is stopped or interrupted can be picked
up again later: finished generations are not repeated.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from ..render import image_of, variant_of
from .reading import drift_position, photo_label, variant_label
from .service import RunPlan, RunRefused, chain_key

FINISHED = ("done", "failed", "stopped")


class _Stop(Exception):
    pass


@dataclass
class Job:
    id: str
    experiment: str
    name: str
    mode: str
    result_experiment: str
    chains_total: int
    generations_total: int
    estimate_usd: float
    status: str = "running"
    chains_done: int = 0
    chains_failed: int = 0
    generations_done: int = 0
    current: dict[str, Any] | None = None
    latest: dict[str, Any] | None = None
    log: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    spent_usd: float = 0.0
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    stop_requested: bool = False

    def view(self) -> dict[str, Any]:
        end = self.finished_at or time.time()
        return {
            "id": self.id,
            "experiment": self.experiment,
            "name": self.name,
            "mode": self.mode,
            "result_experiment": self.result_experiment,
            "status": self.status,
            "chains_total": self.chains_total,
            "chains_done": self.chains_done,
            "chains_failed": self.chains_failed,
            "generations_total": self.generations_total,
            "generations_done": self.generations_done,
            "current": self.current,
            "latest": self.latest,
            "log": self.log[-60:],
            "error": self.error,
            "estimate_usd": self.estimate_usd,
            "spent_usd": round(self.spent_usd, 4),
            "seconds": round(end - self.started_at, 1),
            "stop_requested": self.stop_requested,
        }


class JobManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._job: Job | None = None
        self._thread: threading.Thread | None = None

    def current(self) -> dict[str, Any] | None:
        with self._lock:
            return self._job.view() if self._job else None

    def busy(self) -> bool:
        with self._lock:
            return self._job is not None and self._job.status not in FINISHED

    def start(self, plan: RunPlan, name: str) -> dict[str, Any]:
        with self._lock:
            if self._job is not None and self._job.status not in FINISHED:
                raise RunRefused(
                    "A run is already in progress. Wait for it to finish, or stop it first."
                )
            job = Job(
                id=uuid.uuid4().hex[:10],
                experiment=plan.experiment.id,
                name=name,
                mode=plan.mode,
                result_experiment=plan.result_experiment,
                chains_total=len(plan.chains),
                # every chain also records its original as generation 0
                generations_total=plan.generations + len(plan.chains),
                estimate_usd=plan.estimate_usd,
            )
            self._job = job
            self._thread = threading.Thread(target=self._work, args=(job, plan), daemon=True)
            self._thread.start()
            return job.view()

    def stop(self) -> dict[str, Any] | None:
        with self._lock:
            if self._job is not None and self._job.status not in FINISHED:
                self._job.stop_requested = True
            return self._job.view() if self._job else None

    def dismiss(self) -> None:
        with self._lock:
            if self._job is not None and self._job.status in FINISHED:
                self._job = None

    # -- the worker thread ------------------------------------------------------------------
    def _say(self, job: Job, text: str, tone: str = "info") -> None:
        with self._lock:
            job.log.append(
                {"at": round(time.time() - job.started_at, 1), "text": text, "tone": tone}
            )
            del job.log[:-200]

    def _work(self, job: Job, plan: RunPlan) -> None:
        from ..chain import ChainRunner, RunnerOptions
        from ..cost import SpendCapExceeded, get_tracker
        from ..providers import ProviderUnavailable

        tracker = get_tracker()
        spent_before = tracker.total_usd
        seen_warnings: set[str] = set()

        def on_event(kind: str, data: dict) -> None:
            if job.stop_requested:
                raise _Stop()
            if kind in ("generation", "resume"):
                gen = data["generation"]
                with self._lock:
                    job.generations_done += 1
                    if job.current is not None:
                        job.current["generation"] = gen
                        rec = data.get("record")
                        if rec is not None and rec.generation:
                            job.current["drift"] = rec.metrics.clip_dist_to_g0
                        key = job.current["key"]
                        job.latest = {"key": key, "generation": gen, "at": time.time()}
            elif kind == "warning":
                msg = str(data.get("message", ""))
                if msg not in seen_warnings:
                    seen_warnings.add(msg)
                    self._say(job, _plain_warning(msg), "warning")
            elif kind == "error":
                self._say(
                    job, f"Stopped at generation {data['generation']}: {data['message']}", "error"
                )

        runner = None
        try:
            runner = ChainRunner(
                options=RunnerOptions(
                    compute_clip=plan.clip, compute_lpips=plan.lpips, extractor=plan.extractor
                ),
                on_event=on_event,
            )
            for c in plan.chains:
                if job.stop_requested:
                    raise _Stop()
                stem = image_of(c.chain_id)
                label = f"{photo_label(stem)['name']}, {variant_label(variant_of(c.chain_id))}"
                with self._lock:
                    job.current = {
                        "key": chain_key(c.chain_id, c.repeat),
                        "photo": stem,
                        "photo_name": photo_label(stem)["name"],
                        "variant": variant_of(c.chain_id),
                        "variant_label": variant_label(variant_of(c.chain_id)),
                        "generation": 0,
                        "generations": c.generations,
                        "drift": None,
                        "label": label,
                    }
                before = job.generations_done
                try:
                    recs = runner.run(c)
                except (_Stop, SpendCapExceeded, ProviderUnavailable):
                    raise
                except Exception as e:  # noqa: BLE001  one broken chain must not end the run
                    with self._lock:
                        job.chains_failed += 1
                        job.chains_done += 1
                        job.generations_done = before + c.generations + 1
                    self._say(job, f"{label}: failed ({type(e).__name__}: {e})", "error")
                    continue
                failed = next((r for r in recs if r.error), None)
                with self._lock:
                    job.chains_done += 1
                    job.generations_done = before + c.generations + 1
                    if failed:
                        job.chains_failed += 1
                if not failed:
                    last = recs[-1]
                    d = last.metrics.clip_dist_to_g0
                    pos = drift_position(d) if last.generation else None
                    tail = (
                        f", {round(pos * 100)}% of the way to a different photograph"
                        if pos is not None
                        else ""
                    )
                    self._say(job, f"{label}: {last.generation} generations done{tail}")
            with self._lock:
                job.status = "done"
            self._say(job, "Finished.", "good")
        except _Stop:
            with self._lock:
                job.status = "stopped"
            self._say(
                job,
                "Stopped. What was already finished is kept, and running it again carries on "
                "from there.",
                "warning",
            )
        except (SpendCapExceeded, ProviderUnavailable) as e:
            with self._lock:
                job.status, job.error = "failed", str(e)
            self._say(job, str(e), "error")
        except Exception as e:  # noqa: BLE001
            with self._lock:
                job.status, job.error = "failed", f"{type(e).__name__}: {e}"
            self._say(job, job.error or "The run failed.", "error")
        finally:
            with self._lock:
                job.spent_usd = max(0.0, tracker.total_usd - spent_before)
                job.finished_at = time.time()
                job.current = None
            if runner is not None and runner.ledger is not None:
                runner.ledger.close()


def _plain_warning(msg: str) -> str:
    if msg.startswith("CLIP unavailable"):
        return (
            "The comparison model (CLIP) could not be loaded, so drift is not measured in this "
            "run. Colour and pixel-structure measures are still recorded."
        )
    if "recomputing instead of resuming" in msg:
        return "Earlier results for this chain used different settings, so it is being run afresh."
    return msg
