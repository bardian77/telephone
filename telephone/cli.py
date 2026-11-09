"""Command line interface. `telephone --help`."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .config import get_settings
from .models import ChainConfig, StationConfig

app = typer.Typer(
    help="Telephone: pass photographs through the systems that circulate and interpret them.",
    no_args_is_help=True,
)
console = Console()


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


@app.callback()
def _main(verbose: bool = typer.Option(False, "--verbose", "-v")):
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
        None, help="provider[/model], e.g. anthropic/claude-sonnet-5-5 or mock"
    ),
    generator: str = typer.Option(None, help="provider[/model], e.g. gemini, cloudflare, mock"),
    extractor: str = typer.Option(
        "anthropic", help="provider[/model] for attribute extraction, or 'none'"
    ),
    experiment: str = typer.Option("adhoc", help="Experiment id to file this chain under"),
    name: str = typer.Option(None, help="Chain id (default derived from image and stations)"),
    no_clip: bool = typer.Option(False, help="Skip CLIP embeddings"),
    lpips: bool = typer.Option(False, help="Also compute LPIPS (slow, needs weights)"),
):
    """Run a single chain on one image."""
    s = get_settings()
    st = parse_stations(
        stations, captioner or s.default_captioner, generator or s.default_generator
    )
    ex = (
        None
        if extractor == "none"
        else StationConfig(
            kind="extract",
            provider=extractor.partition("/")[0],
            model=extractor.partition("/")[2] or None,
        )
    )
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
    recs = runner.run(cfg)
    _cost_line(runner)
    console.print(f"{len(recs)} generations in ledger at {s.ledger_path}")


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
        console.print(
            f"[red]Estimated cost ${estimate_usd:.2f} exceeds the remaining budget "
            f"${t.remaining():.2f} (spent ${t.total_usd:.2f} of the ${t.cap_usd:.2f} cap, "
            "TELEPHONE_SPEND_CAP_USD). Run less (--limit, --variant, --generations) or raise "
            "the cap."
        )
        raise typer.Exit(2)


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
):
    """Run every chain of an experiment (resumable; cached stations cost nothing)."""
    from .experiments import find

    exp = find(name)
    chains = exp.chains(images=images or None, generations=generations, repeats=repeats)
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
        console.print(
            "[red]No chains: are there images in data/originals? (telephone make-fixtures for test images)"
        )
        raise typer.Exit(1)
    use_lpips = exp.metrics.get("lpips", False) if lpips is None else lpips
    extractor_cfg = None if no_extract else exp.extractor_config()
    runner = _runner(
        extractor_cfg, clip=not no_clip and exp.metrics.get("clip", True), lpips=use_lpips
    )
    total_calls, total_cost = 0, 0.0
    table = Table(title=f"{exp.id}: {len(chains)} chains", show_lines=False)
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
    for i, c in enumerate(chains, 1):
        console.rule(
            f"[bold]{i}/{len(chains)} {c.chain_id}[/]  {c.station_sequence()}  x{c.generations}"
        )
        try:
            runner.run(c)
        except Exception as e:  # noqa: BLE001
            from .cost import SpendCapExceeded

            if isinstance(e, SpendCapExceeded):
                console.print(f"[bold red]{e}")
                raise typer.Exit(2) from e
            console.print(f"[bold red]chain failed: {type(e).__name__}: {e}")
            logging.getLogger("telephone").exception("chain failed")
    _cost_line(runner)


@app.command("list")
def list_cmd(experiment: str = typer.Option(None)):
    """Experiments defined and chains in the ledger."""
    from .experiments import load_all
    from .ledger import Ledger

    s = get_settings()
    exps = load_all()
    t = Table(title="experiments/")
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


@app.command("save-results")
def save_results(
    experiment: Annotated[str, typer.Argument(help="Experiment id, e.g. exp01_compression")],
    out: Path = typer.Option(None, help="Output file (default data/results/<experiment>.jsonl)"),
):
    """Write one experiment's ledger rows to a sorted JSONL file that can be committed."""
    from .ledger import Ledger

    s = get_settings()
    if not s.ledger_path.exists():
        console.print("[red]ledger: empty, nothing to save")
        raise typer.Exit(1)
    led = Ledger(s.ledger_path)
    known = [row["experiment_id"] for row in led.experiments()]
    if experiment not in known:
        matches = [k for k in known if k.startswith(experiment)]
        if len(matches) != 1:
            console.print(f"[red]No experiment {experiment!r} in the ledger. Known: {known}")
            raise typer.Exit(1)
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
def make_fixtures(folder: Path = typer.Option(Path("data/fixtures"))):
    """Write the five synthetic test images."""
    from .fixtures import make_all

    for p in make_all(folder):
        console.print(f"wrote {p}")


@app.command()
def render(
    experiment: str = typer.Argument(None, help="Experiment id, or all when omitted"),
    out: Path = typer.Option(Path("data/figures")),
):
    """Contact sheets, drift curves and survival heatmaps from the ledger."""
    from .render import render_all

    for p in render_all(experiment, out):
        console.print(f"wrote {p}")


@app.command()
def export(
    out: Path = typer.Option(Path("web/public/data")),
    thumb: int = typer.Option(512, help="Thumbnail long edge"),
    include_private: bool = typer.Option(False),
    experiment: list[str] = typer.Option(None, help="Only these experiment ids"),
    clean: bool = typer.Option(False, help="Delete the output folder first"),
):
    """Ledger -> JSON + thumbnails for the website."""
    from .export import export_all

    summary = export_all(
        out,
        thumb_size=thumb,
        include_private=include_private,
        experiments=experiment or None,
        clean=clean,
    )
    console.print(json.dumps(summary, indent=2))


@app.command()
def validate(
    labels: Path = typer.Option(Path("analysis/validation/labels.csv")),
    out: Path = typer.Option(Path("analysis/validation/report.md")),
):
    """Agreement between hand labels and the automated measures."""
    from .validate import agreement_report

    console.print(agreement_report(labels, out))


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000, reload: bool = False):
    """Run the FastAPI service (static results, optional live runs)."""
    import uvicorn

    uvicorn.run("api.main:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    app()
