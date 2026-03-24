"""Main CLI for DataSpoc Pipe."""

import typer
from rich.console import Console

from dataspoc_pipe import __version__
from dataspoc_pipe.config import (
    DATASPOC_HOME,
    PIPELINES_DIR,
    DestinationConfig,
    IncrementalConfig,
    PipelineConfig,
    ScheduleConfig,
    SourceConfig,
    save_pipeline,
)

console = Console()
app = typer.Typer(
    name="dataspoc-pipe",
    help="DataSpoc Pipe — Data ingestion engine. Singer + Parquet + Bucket.",
    no_args_is_help=True,
)

schedule_app = typer.Typer(help="Schedule management.")
app.add_typer(schedule_app, name="schedule")


def version_callback(value: bool) -> None:
    if value:
        console.print(f"dataspoc-pipe {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", "-v", help="Show version.", callback=version_callback, is_eager=True
    ),
) -> None:
    """DataSpoc Pipe — Data ingestion engine."""


@app.command()
def init() -> None:
    """Initialize the configuration structure."""
    created = False
    sources_dir = DATASPOC_HOME / "sources"
    transforms_dir = DATASPOC_HOME / "transforms"
    for d in [DATASPOC_HOME, PIPELINES_DIR, sources_dir, transforms_dir]:
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
            created = True

    config_file = DATASPOC_HOME / "config.yaml"
    if not config_file.exists():
        config_file.write_text(
            "# DataSpoc Pipe — global configuration\n"
            "# Edit as needed.\n"
            "\n"
            "defaults:\n"
            "  compression: zstd\n"
            "  partition_by: _extraction_date\n"
        )
        created = True

    if created:
        console.print(f"[green]Structure created at {DATASPOC_HOME}[/green]")
        console.print("Next step: [bold]dataspoc-pipe add <name>[/bold]")
    else:
        console.print(f"[blue]Structure already exists at {DATASPOC_HOME}[/blue]")


@app.command()
def add(nome: str = typer.Argument(..., help="Pipeline name")) -> None:
    """Create a new pipeline via interactive wizard."""
    import json

    from dataspoc_pipe.config import get_pipeline_path
    from dataspoc_pipe.tap_templates import get_template, list_known_taps, try_discover_config

    path = get_pipeline_path(nome)
    if path.exists():
        console.print(f"[red]Pipeline '{nome}' already exists at {path}[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]Creating pipeline: {nome}[/bold]\n")

    # Show known taps
    known = list_known_taps()
    console.print(f"Taps with template: {', '.join(known)}\n")

    tap = typer.prompt("Tap Singer")

    # Generate tap config
    sources_dir = DATASPOC_HOME / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)
    source_config_path = sources_dir / f"{nome}.json"

    template = get_template(tap)
    if template:
        console.print(f"[green]Template found for {tap}[/green]")
    else:
        console.print(f"[yellow]Unknown tap. Trying to discover config...[/yellow]")
        template = try_discover_config(tap)
        if template:
            console.print(f"[green]Config discovered via --about[/green]")
        else:
            template = {}
            console.print("[yellow]Empty config generated. Edit manually.[/yellow]")

    # Save tap config
    with open(source_config_path, "w") as f:
        json.dump(template, f, indent=2, ensure_ascii=False)
    console.print(f"Source config: [bold]{source_config_path}[/bold]")

    # Ask destination
    bucket = typer.prompt("Destination bucket (e.g.: s3://my-bucket, file:///tmp/lake)")
    base_path = typer.prompt("Base path in bucket", default="raw")
    compression = typer.prompt("Compression (zstd, snappy, gzip, none)", default="zstd")
    incremental = typer.confirm("Enable incremental extraction?", default=False)
    cron_expr = typer.prompt("Cron expression for scheduling (empty to skip)", default="")

    config = PipelineConfig(
        name=nome,
        source=SourceConfig(tap=tap, config=str(source_config_path)),
        destination=DestinationConfig(
            bucket=bucket, path=base_path, compression=compression
        ),
        incremental=IncrementalConfig(enabled=incremental),
        schedule=ScheduleConfig(cron=cron_expr or None),
    )

    saved_path = save_pipeline(config)
    console.print(f"\n[green]Pipeline saved at {saved_path}[/green]")
    console.print(f"\n[bold]Next steps:[/bold]")
    console.print(f"  1. Edit source config: [bold]{source_config_path}[/bold]")
    console.print(f"  2. Validate: [bold]dataspoc-pipe validate {nome}[/bold]")
    console.print(f"  3. Run: [bold]dataspoc-pipe run {nome}[/bold]")


@app.command()
def run(
    nome: str = typer.Argument(..., help="Pipeline name"),
    full: bool = typer.Option(False, "--full", help="Force full extraction (ignore incremental)"),
    all_pipelines: bool = typer.Option(False, "--all", help="Run all pipelines"),
) -> None:
    """Run an extraction pipeline."""
    from dataspoc_pipe.config import list_pipelines, load_pipeline
    from dataspoc_pipe.engine import run_pipeline
    from dataspoc_pipe.state import load_state, save_state

    from datetime import datetime, timezone
    from pathlib import Path
    from dataspoc_pipe.catalog import save_execution_log, update_manifest

    def _run_one(n: str) -> "ExtractionResult":
        config = load_pipeline(n)
        console.print(f"\n[bold]Running: {n}[/bold]")

        # Load state if incremental
        state = None
        if config.incremental.enabled and not full:
            state = load_state(config.destination.bucket, n)
            if state:
                console.print("  [blue]Incremental mode (using previous checkpoint)[/blue]")

        started_at = datetime.now(timezone.utc)
        result = run_pipeline(config, state=state, full=full, on_progress=_print_progress)
        finished_at = datetime.now(timezone.utc)

        # Save state if success and has new state
        if result.success and result.last_state:
            save_state(config.destination.bucket, n, result.last_state)

        # Update manifest and save log
        if result.success:
            tap_name = config.source.tap.split()[-1]
            source_name = Path(tap_name).stem.replace("tap-", "")
            update_manifest(config.destination.bucket, result, source_name)

        try:
            save_execution_log(config.destination.bucket, result, started_at, finished_at)
        except Exception:
            pass  # Log should not prevent the result

        _print_result(result)
        return result

    if all_pipelines:
        names = list_pipelines()
        if not names:
            console.print("[yellow]No pipelines configured.[/yellow]")
            return
        results = [_run_one(n) for n in names]
        ok = sum(1 for r in results if r.success)
        fail = len(results) - ok
        console.print(f"\n[bold]Summary: {ok} success, {fail} failure(s)[/bold]")
        return

    result = _run_one(nome)
    if not result.success:
        raise typer.Exit(1)


def _print_progress(stream: str, total: int) -> None:
    console.print(f"  {stream}: {total:,} records...", highlight=False)


def _print_result(result) -> None:
    if result.success:
        total = sum(result.streams.values())
        console.print(f"[green]Done![/green] {total:,} records in {len(result.streams)} stream(s)")
        for stream, count in result.streams.items():
            raw_count = result.streams_raw.get(stream, count)
            if raw_count != count:
                console.print(f"  {stream}: {raw_count:,} raw → {count:,} after transform")
            else:
                console.print(f"  {stream}: {count:,}")
    else:
        console.print(f"[red]Failed:[/red] {result.error}")


@app.command()
def status() -> None:
    """Show the status of all pipelines."""
    from rich.table import Table

    from dataspoc_pipe.catalog import load_latest_log
    from dataspoc_pipe.config import list_pipelines, load_pipeline

    names = list_pipelines()
    if not names:
        console.print("[yellow]No pipelines configured. Use 'dataspoc-pipe add' first.[/yellow]")
        return

    table = Table(title="Pipelines")
    table.add_column("Pipeline", style="bold")
    table.add_column("Last Run")
    table.add_column("Status")
    table.add_column("Duration")
    table.add_column("Records")

    for name in names:
        try:
            config = load_pipeline(name)
            log = load_latest_log(config.destination.bucket, name)
        except Exception:
            table.add_row(name, "-", "[yellow]no runs[/yellow]", "-", "-")
            continue

        if log is None:
            table.add_row(name, "-", "[yellow]no runs[/yellow]", "-", "-")
        else:
            status_str = "[green]success[/green]" if log["status"] == "success" else "[red]failure[/red]"
            duration = f"{log.get('duration_seconds', 0):.1f}s"
            rows = str(log.get("total_records", 0))
            table.add_row(name, log.get("started_at", "-")[:19], status_str, duration, rows)

    console.print(table)


@app.command()
def logs(nome: str = typer.Argument(..., help="Pipeline name")) -> None:
    """Show logs from the last pipeline execution."""
    import json as json_mod

    from dataspoc_pipe.catalog import load_latest_log
    from dataspoc_pipe.config import load_pipeline

    config = load_pipeline(nome)
    log = load_latest_log(config.destination.bucket, nome)

    if log is None:
        console.print(f"[yellow]No logs found for '{nome}'.[/yellow]")
        return

    console.print(json_mod.dumps(log, indent=2, ensure_ascii=False))


@app.command()
def validate(
    nome: str = typer.Argument(None, help="Pipeline name (or all if omitted)"),
) -> None:
    """Test connections to sources and buckets."""
    from dataspoc_pipe.config import list_pipelines, load_pipeline
    from dataspoc_pipe.storage import delete, exists, write_bytes

    names = [nome] if nome else list_pipelines()
    if not names:
        console.print("[yellow]No pipelines configured. Use 'dataspoc-pipe add' first.[/yellow]")
        return

    for name in names:
        try:
            config = load_pipeline(name)
        except FileNotFoundError:
            console.print(f"[red]Pipeline '{name}' not found.[/red]")
            continue

        console.print(f"\n[bold]Validating: {name}[/bold]")

        # Test bucket
        test_uri = f"{config.destination.bucket.rstrip('/')}/.dataspoc/_validate_test"
        try:
            write_bytes(test_uri, b"ok")
            assert exists(test_uri)
            delete(test_uri)
            console.print(f"  [green]Bucket OK:[/green] {config.destination.bucket}")
        except Exception as e:
            console.print(f"  [red]Bucket FAILED:[/red] {config.destination.bucket} — {e}")

        # Test tap (check if it exists in PATH)
        import shutil

        if shutil.which(config.source.tap):
            console.print(f"  [green]Tap OK:[/green] {config.source.tap} found in PATH")
        else:
            console.print(f"  [yellow]Tap:[/yellow] {config.source.tap} not found in PATH")


@app.command()
def manifest(
    bucket: str = typer.Argument(..., help="Bucket URI"),
) -> None:
    """Show the manifest/catalog of a bucket."""
    import json as json_mod

    from dataspoc_pipe.catalog import load_manifest

    m = load_manifest(bucket)
    if not m.get("tables"):
        console.print("[yellow]Empty manifest — no extractions performed on this bucket.[/yellow]")
        return

    console.print(json_mod.dumps(m, indent=2, ensure_ascii=False))


@schedule_app.command("install")
def schedule_install() -> None:
    """Install schedules in crontab."""
    import shutil

    from dataspoc_pipe.config import list_pipelines, load_pipeline

    pipe_cmd = shutil.which("dataspoc-pipe")
    if not pipe_cmd:
        console.print("[red]dataspoc-pipe not found in PATH.[/red]")
        raise typer.Exit(1)

    names = list_pipelines()
    if not names:
        console.print("[yellow]No pipelines configured.[/yellow]")
        return

    installed = 0
    for name in names:
        config = load_pipeline(name)
        cron_expr = config.schedule.cron
        if not cron_expr:
            continue

        # Use flock to prevent overlapping runs
        lock_file = f"/tmp/dataspoc-pipe-{name}.lock"
        cmd = f"flock -n {lock_file} {pipe_cmd} run {name}"
        comment = f"dataspoc-pipe:{name}"

        try:
            from crontab import CronTab

            cron = CronTab(user=True)

            # Remove previous entry if exists
            cron.remove_all(comment=comment)

            job = cron.new(command=cmd, comment=comment)
            job.setall(cron_expr)
            cron.write()
            console.print(f"  [green]Installed:[/green] {name} ({cron_expr})")
            installed += 1

        except ImportError:
            console.print("[red]Install python-crontab: pip install python-crontab[/red]")
            raise typer.Exit(1)
        except Exception as e:
            console.print(f"  [red]Error in {name}:[/red] {e}")

    if installed:
        console.print(f"\n[green]{installed} schedule(s) installed.[/green]")
    else:
        console.print("[yellow]No pipelines have schedule.cron configured.[/yellow]")


@schedule_app.command("remove")
def schedule_remove() -> None:
    """Remove schedules from crontab."""
    try:
        from crontab import CronTab

        cron = CronTab(user=True)
        removed = 0
        for job in list(cron):
            if job.comment and job.comment.startswith("dataspoc-pipe:"):
                cron.remove(job)
                removed += 1
                console.print(f"  [yellow]Removed:[/yellow] {job.comment}")
        cron.write()

        if removed:
            console.print(f"\n[green]{removed} schedule(s) removed.[/green]")
        else:
            console.print("[yellow]No dataspoc-pipe schedules found.[/yellow]")

    except ImportError:
        console.print("[red]Install python-crontab: pip install python-crontab[/red]")
        raise typer.Exit(1)
