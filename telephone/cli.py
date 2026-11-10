"""Command line interface. `telephone --help`.

Works from any folder: paths anchor on the project root (telephone/paths.py). Errors a user can
act on (a missing key, a blown spend cap, an unknown experiment, a bad folder) end the command
with one red line; tracebacks only appear with -v.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from . import __version__, paths
from .config import get_settings
from .models import ChainConfig, StationConfig

app = typer.Typer(
    help="Telephone: pass photographs through the systems that circulate and interpret them.",
    no_args_is_help=True,
)
console = Console()
_verbose = False
MOCK_HELP = "Use the offline mock stand-ins for every model station; results are filed under '<experiment>-mock'"


def _fail(message: str, code: int = 2) -> None:
    console.print(f"[bold red]{message}", soft_wrap=True)
    raise typer.Exit(code)


def _runner(
    extractor: StationConfig | None, clip: bool = True, lpips: bool = False, quiet: bool = False
):
    from .chain import ChainRunner, RunnerOptions

    def on_event(kind: str, data: dict) -> None:
        if quiet:
            return
        if kind == "generation":
            rec = data["record"]
            m = rec.metrics
            clipd = f"{m.clip_dist_to_g0:.3f}" if m.clip_dist_to_g0 is not None else "  -  "
            surv = f"{rec.survival.alive_count}/{rec.survival.total}" if rec.survival else " - "
            cap = (rec.caption or "")[:60].replace("\n", " ")
            console.print(
                f"  g{rec.generation:02d}  clip {clipd}  hist {m.hist_dist_to_g0 or 0:.3f}  ssim {m.ssim_to_g0 or 0:.3f}  alive {surv}  ${rec.cost_usd:.4f}  {cap}"
            )
        elif kind == "resume":
            console.print(f"  g{data['generation']:02d}  (already in ledger)", style="dim")
        elif kind == "error":
            console.print(f"  g{data['generation']:02d}  STOP: {data['message']}", style="bold red")
        elif kind == "warning":
            console.print(f"  warning: {data['message']}", style="yellow")

    return ChainRunner(
        options=RunnerOptions(compute_clip=clip, compute_lpips=lpips, extractor=extractor),
        on_event=on_event,
    )


def parse_stations(spec: str, captioner: str | None, generator: str | None) -> list[StationConfig]:
    """'platform:instagram,caption:detailed,regenerate' -> StationConfigs."""
    out: list[StationConfig] = []
    for part in [p.strip() for p in spec.split(",") if p.strip()]:
        kind, _, arg = part.partition(":")
        if kind == "platform":
            out.append(StationConfig(kind="platform", params={"preset": arg or "instagram"}))
        elif kind == "caption":
            prov, _, model = (captioner or "").partition("/")
            out.append(
                StationConfig(
                    kind="caption",
                    provider=prov or None,
                    model=model or None,
                    params={"mode": arg or "detailed"},
                )
            )
        elif kind == "regenerate":
            prov, _, model = (generator or "").partition("/")
            out.append(
                StationConfig(
                    kind="regenerate",
                    provider=prov or None,
                    model=model or None,
                    params={"size": int(arg)} if arg else {},
                )
            )
        elif kind == "physical":
            out.append(StationConfig(kind="physical", params={"folder": arg}))
        else:
            raise typer.BadParameter(f"unknown station {kind!r}")
    return out


def _extractor_from(spec: str | None) -> StationConfig | None:
    """'none' -> no extraction; None -> the default captioner; 'provider[/model]' otherwise."""
    if spec is None:
        return StationConfig(kind="extract")
    if spec == "none":
        return None
    prov, _, model = spec.partition("/")
    return StationConfig(kind="extract", provider=prov or None, model=model or None)


def _run_guarded(runner, cfg: ChainConfig) -> bool:
    """Run one chain. A missing key or a blown cap ends the command with one line; any other
    failure is reported in one line and the caller moves on. Returns True on success."""
    from .cost import SpendCapExceeded
    from .providers import ProviderUnavailable

    try:
        runner.run(cfg)
        return True
    except SpendCapExceeded as e:
        _fail(str(e))
    except ProviderUnavailable as e:
        _fail(
            f"{e}. Put the key in .env at the project root (see .env.example), or run with "
            "--mock to use the offline stand-ins."
        )
    except ValueError as e:
        _fail(str(e))
    except Exception as e:  # noqa: BLE001
        if _verbose:
            logging.getLogger("telephone").exception("chain failed")
        hint = "" if _verbose else "  (run with -v for the traceback)"
        console.print(f"[bold red]chain failed: {type(e).__name__}: {e}{hint}", soft_wrap=True)
    return False


@app.callback()
def _main(verbose: bool = typer.Option(False, "--verbose", "-v")):
    global _verbose
    _verbose = verbose
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )


@app.command()
def version():
    console.print(__version__)


@app.command("run-chain")
def run_chain(
    image: Annotated[Path, typer.Option(..., exists=True, help="Generation-0 photograph")],
    stations: Annotated[
        str, typer.Option(help="e.g. 'platform:instagram,caption:detailed,regenerate'")
    ] = "platform:instagram,caption:detailed,regenerate",
    generations: int = typer.Option(None, help="Default from settings (12)"),
    seed: int = typer.Option(None),
    captioner: str = typer.Option(
        None, help="provider[/model] for the caption station, e.g. anthropic, gemini or mock"
    ),
    generator: str = typer.Option(
        None, help="provider[/model] for the regenerate station, e.g. gemini, cloudflare or mock"
    ),
    extractor: str = typer.Option(
        None,
        help="provider[/model] for attribute extraction (default: the captioner's default "
        "provider), or 'none'",
    ),
    mock: bool = typer.Option(False, "--mock", help=MOCK_HELP),
    experiment: str = typer.Option("adhoc", help="Experiment id to file this chain under"),
    name: str = typer.Option(None, help="Chain id (default derived from image and stations)"),
    no_clip: bool = typer.Option(False, help="Skip CLIP embeddings"),
    lpips: bool = typer.Option(False, help="Also compute LPIPS (slow, needs weights)"),
):
    """Run a single chain on one image."""
    from .experiments import MOCK_SUFFIX

    s = get_settings()
    if mock:
        captioner, generator, extractor = "mock", "mock", "mock"
        if not experiment.endswith(MOCK_SUFFIX):
            experiment += MOCK_SUFFIX
    st = parse_stations(
        stations, captioner or s.default_captioner, generator or s.default_generator
    )
    ex = _extractor_from(extractor)
    cfg = ChainConfig(
        chain_id=name
        or f"{experiment}__{stations.replace(':', '-').replace(',', '_')}__{image.stem}",
        experiment_id=experiment,
        image=str(image),
        stations=st,
        generations=generations or s.default_generations,
        seed=seed if seed is not None else s.default_seed,
    )
    runner = _runner(ex, clip=not no_clip, lpips=lpips)
    console.rule(f"[bold]{cfg.chain_id}[/]  {cfg.station_sequence()}  x{cfg.generations}")
    calls, est = runner.estimate(cfg)
    console.print(f"estimate: {calls} paid calls, about ${est:.3f} (cache ignored)", style="dim")
    _check_budget(est)
    if _run_guarded(runner, cfg):
        _cost_line(runner)
        n = len(runner.ledger.chain(cfg.chain_id, cfg.repeat))
        console.print(f"{n} generations in ledger at {s.ledger_path}")


def _cost_line(runner) -> None:
    from .cost import get_tracker

    t = get_tracker()
    console.print(
        f"this run spent ${t.session_usd:.4f}; total so far ${t.total_usd:.4f} of the "
        f"${t.cap_usd:.2f} cap (${t.remaining():.2f} left; list price total "
        f"${t.total_list_usd:.4f}); cache {runner.cache.stats()}",
        style="dim",
    )


def _check_budget(estimate_usd: float) -> None:
    """Refuse to start when the estimate does not fit in what is left of the lifetime cap."""
    from .cost import get_tracker

    t = get_tracker()
    if estimate_usd > t.remaining():
        _fail(
            f"Estimated cost ${estimate_usd:.2f} exceeds the remaining budget "
            f"${t.remaining():.2f} (spent ${t.total_usd:.2f} of the ${t.cap_usd:.2f} cap, "
            "TELEPHONE_SPEND_CAP_USD). Run less (--limit, --variant, --generations) or raise "
            "the cap."
        )


def _no_chains(exp, images: list[Path] | None, variant: list[str] | None) -> None:
    s = get_settings()
    if not images and not exp.resolve_images():
        if "fixtures" in exp.images:
            hint = "run `telephone make-fixtures` to create the synthetic test images"
        else:
            hint = (
                f"add photographs to {s.originals_dir} (named <type>_<slug>.jpg, see "
                "data/originals/README.md), or pass --image"
            )
        _fail(f"No images for {exp.id}. It looks for {exp.images}; {hint}.", code=1)
    names = [v["name"] for v in exp.variants]
    _fail(
        f"No chains left after filtering. The variants of {exp.id} are {names}; check --variant "
        "and --limit.",
        code=1,
    )


@app.command("run-experiment")
def run_experiment(
    name: Annotated[str, typer.Argument(help="Experiment id or prefix, e.g. exp01")],
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Print chains, call counts and cost estimate; run nothing"
    ),
    images: list[Path] = typer.Option(None, "--image", help="Override the experiment's images"),
    generations: int = typer.Option(None),
    repeats: int = typer.Option(None),
    variant: list[str] = typer.Option(None, help="Only these variant names"),
    limit: int = typer.Option(None, help="Run at most this many chains"),
    physical_root: Path = typer.Option(
        None, help="For exp06: folder containing <image_stem>/ frame folders"
    ),
    no_clip: bool = typer.Option(False),
    lpips: bool = typer.Option(None, help="Override the experiment's lpips setting"),
    no_extract: bool = typer.Option(
        False,
        "--no-extract",
        help="Skip attribute extraction (the survival form) even if the experiment defines one; "
        "needs no vision model and no key",
    ),
    mock: bool = typer.Option(False, "--mock", help=MOCK_HELP),
):
    """Run every chain of an experiment (resumable; cached stations cost nothing)."""
    from .experiments import find, mockify

    try:
        exp = find(name)
    except KeyError as e:
        _fail(str(e).strip("'\""))
    chains = exp.chains(images=images or None, generations=generations, repeats=repeats)
    extractor_cfg = None if no_extract else exp.extractor_config()
    if mock:
        chains = [mockify(c) for c in chains]
        if extractor_cfg is not None:
            extractor_cfg = StationConfig(kind="extract", provider="mock")
    if variant:
        chains = [c for c in chains if any(c.chain_id.split("__")[1] == v for v in variant)]
    if physical_root:
        for c in chains:
            for st in c.stations:
                if st.kind == "physical":
                    st.params["folder"] = str(physical_root / Path(c.image).stem)
    if limit:
        chains = chains[:limit]
    if not chains:
        _no_chains(exp, images, variant)
    use_lpips = exp.metrics.get("lpips", False) if lpips is None else lpips
    runner = _runner(
        extractor_cfg, clip=not no_clip and exp.metrics.get("clip", True), lpips=use_lpips
    )
    total_calls, total_cost = 0, 0.0
    title = f"{chains[0].experiment_id}: {len(chains)} chains"
    table = Table(title=title, show_lines=False)
    table.add_column("chain")
    table.add_column("stations")
    table.add_column("gens", justify="right")
    table.add_column("paid calls", justify="right")
    table.add_column("est. USD", justify="right")
    for c in chains:
        calls, cost = runner.estimate(c)
        total_calls += calls
        total_cost += cost
        table.add_row(
            c.chain_id, c.station_sequence(), str(c.generations), str(calls), f"{cost:.3f}"
        )
    table.add_row("[bold]total", "", "", f"[bold]{total_calls}", f"[bold]{total_cost:.3f}")
    console.print(table)
    s = get_settings()
    billing = "free tier, costed at 0" if s.gemini_free_tier else "list price"
    console.print(
        f"Estimates ignore the cache. Gemini is billed at {billing} (GEMINI_FREE_TIER); mock and "
        "Cloudflare cost 0. List prices are logged per call.",
        style="dim",
    )
    if dry_run:
        return
    _check_budget(total_cost)
    failed = 0
    for i, c in enumerate(chains, 1):
        console.rule(
            f"[bold]{i}/{len(chains)} {c.chain_id}[/]  {c.station_sequence()}  x{c.generations}"
        )
        if not _run_guarded(runner, c):
            failed += 1
    _cost_line(runner)
    if failed:
        console.print(f"[yellow]{failed} of {len(chains)} chains failed; see the lines above.")


@app.command("list")
def list_cmd(experiment: str = typer.Option(None)):
    """Experiments defined and chains in the ledger."""
    from .experiments import experiments_dir, load_all
    from .ledger import Ledger

    s = get_settings()
    exps = load_all()
    t = Table(title=str(experiments_dir()))
    t.add_column("id")
    t.add_column("title")
    t.add_column("variants", justify="right")
    for e in exps.values():
        t.add_row(e.id, e.title, str(len(e.variants)))
    console.print(t)
    if not s.ledger_path.exists():
        console.print("ledger: empty", style="dim")
        return
    led = Ledger(s.ledger_path)
    t2 = Table(title=f"ledger {s.ledger_path}")
    for col in (
        "experiment_id",
        "chain_id",
        "repeat",
        "generations",
        "errors",
        "cost_usd",
        "list_price_usd",
    ):
        t2.add_column(col, justify="right" if col not in ("experiment_id", "chain_id") else "left")
    for row in led.chains(experiment):
        t2.add_row(
            row["experiment_id"],
            row["chain_id"],
            str(row["repeat"]),
            str(row["generations"]),
            str(row["errors"]),
            f"{row['cost_usd']:.4f}",
            f"{row['list_price_usd']:.4f}",
        )
    console.print(t2)


@app.command()
def cost():
    """Total spend recorded in the ledger."""
    from .ledger import Ledger

    s = get_settings()
    if not s.ledger_path.exists():
        console.print("ledger: empty")
        return
    led = Ledger(s.ledger_path)
    paid, listp = led.total_spend()
    cap = s.telephone_spend_cap_usd
    console.print(
        f"paid so far ${paid:.4f} of the ${cap:.2f} cap (${max(0.0, cap - paid):.2f} left); "
        f"list price ${listp:.4f}"
    )
    console.print(
        "Gemini billing: " + ("free tier, costed at 0" if s.gemini_free_tier else "list price"),
        style="dim",
    )
    rec_paid, rec_list = led.total_cost()
    console.print(
        f"recorded on generation rows: paid ${rec_paid:.4f}, list ${rec_list:.4f} "
        "(re-runs replace rows and cache hits copy old costs, so this can differ from the total)",
        style="dim",
    )
    for row in led.experiments():
        console.print(
            f"  {row['experiment_id']:<24} chains {row['chains']:>3}  gens {row['generations']:>4}  paid ${row['cost_usd']:.4f}  list ${row['list_price_usd']:.4f}"
        )


@app.command()
def doctor(as_json: bool = typer.Option(False, "--json", help="Machine-readable output")):
    """What is installed, which keys are set, where the photos are, and what can run now."""
    from .doctor import collect, render_text

    d = collect()
    typer.echo(json.dumps(d, indent=2) if as_json else render_text(d))


@app.command("save-results")
def save_results(
    experiment: Annotated[str, typer.Argument(help="Experiment id, e.g. exp01_compression")],
    out: Path = typer.Option(None, help="Output file (default data/results/<experiment>.jsonl)"),
):
    """Write one experiment's ledger rows to a sorted JSONL file that can be committed."""
    from .ledger import Ledger

    s = get_settings()
    if not s.ledger_path.exists():
        _fail("ledger: empty, nothing to save", code=1)
    led = Ledger(s.ledger_path)
    known = [row["experiment_id"] for row in led.experiments()]
    if experiment not in known:
        matches = [k for k in known if k.startswith(experiment)]
        if len(matches) != 1:
            _fail(f"No experiment {experiment!r} in the ledger. Known: {known}", code=1)
        experiment = matches[0]
    path = out or s.results_dir / f"{experiment}.jsonl"
    n = led.save_results(experiment, path)
    console.print(f"wrote {n} rows to {path}")


@app.command("load-results")
def load_results(
    file: Annotated[Path, typer.Argument(exists=True, help="A file written by save-results")],
):
    """Load a saved results file into the ledger. Rows with the same key are replaced."""
    from .ledger import Ledger

    s = get_settings()
    led = Ledger(s.ledger_path)
    n = led.import_jsonl(file)
    console.print(f"loaded {n} rows into {s.ledger_path}")


@app.command("make-fixtures")
def make_fixtures(
    folder: Path = typer.Option(None, help="Default: data/fixtures (only exp00 reads it)"),
):
    """Write the five synthetic test images that exp00 (the smoke test) runs on."""
    from .fixtures import make_all

    for p in make_all(folder or get_settings().fixtures_dir):
        console.print(f"wrote {p}")


@app.command()
def render(
    experiment: str = typer.Argument(None, help="Experiment id, or all when omitted"),
    out: Path = typer.Option(None, help="Default: data/figures"),
):
    """Contact sheets, drift curves and survival heatmaps from the ledger."""
    from .render import render_all

    for p in render_all(experiment, out or get_settings().figures_dir):
        console.print(f"wrote {p}")


@app.command()
def export(
    out: Path = typer.Option(None, help="Default: web/public/data at the project root"),
    thumb: int = typer.Option(512, help="Thumbnail long edge"),
    include_private: bool = typer.Option(
        False, help="Also export photographs from data/originals/private/"
    ),
    include_mock: bool = typer.Option(
        False, help="Also export runs on mock providers ('-mock' experiments)"
    ),
    experiment: list[str] = typer.Option(None, help="Only these experiment ids"),
    clean: bool = typer.Option(False, help="Delete the output folder first"),
):
    """Ledger -> JSON + thumbnails for the website."""
    from .export import export_all

    summary = export_all(
        out or paths.project_root() / "web" / "public" / "data",
        thumb_size=thumb,
        include_private=include_private,
        experiments=experiment or None,
        clean=clean,
        include_mock=include_mock,
    )
    console.print(json.dumps(summary, indent=2))


@app.command()
def validate(
    labels: Path = typer.Option(None, help="Default: analysis/validation/labels.csv"),
    out: Path = typer.Option(None, help="Default: analysis/validation/report.md"),
):
    """Agreement between hand labels and the automated measures."""
    from .validate import agreement_report

    folder = paths.project_root() / "analysis" / "validation"
    console.print(agreement_report(labels or folder / "labels.csv", out or folder / "report.md"))


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000, reload: bool = False):
    """Run the FastAPI service (static results, optional live runs)."""
    import uvicorn

    uvicorn.run(
        "api.main:app", host=host, port=port, reload=reload, app_dir=str(paths.project_root())
    )


@app.command()
def dashboard(
    host: str = typer.Option("127.0.0.1", help="Address to listen on. Keep the default."),
    port: int = typer.Option(8321, help="Port to listen on"),
    no_open: bool = typer.Option(False, "--no-open", help="Do not open the browser"),
):
    """Open the dashboard in your browser: run experiments and read results without the terminal."""
    try:
        import uvicorn

        from .dashboard.server import create_app
    except ImportError as e:
        _fail(
            f"The dashboard needs FastAPI and uvicorn ({e.name} is missing). Install them with: "
            'pip install -e ".[api]"'
        )
    url = f"http://{'localhost' if host in ('127.0.0.1', '0.0.0.0') else host}:{port}"
    console.print(f"Telephone dashboard: [bold]{url}[/]   (Ctrl+C to stop)")
    if not no_open:
        import threading
        import webbrowser

        threading.Timer(1.0, webbrowser.open, args=(url,)).start()
    uvicorn.run(create_app(), host=host, port=port, log_level="warning")


if __name__ == "__main__":
    app()
