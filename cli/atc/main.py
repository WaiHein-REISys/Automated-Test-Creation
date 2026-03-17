"""ATC CLI — Automated Test Creation."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console

from atc import __version__
from atc.infra.config import RunConfig

app = typer.Typer(
    name="atc",
    help="Automated Test Creation — generate BDD feature files from Azure DevOps work items.",
    no_args_is_help=True,
)
console = Console()


def version_callback(value: bool) -> None:
    if value:
        console.print(f"atc {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        Optional[bool],
        typer.Option("--version", "-v", callback=version_callback, is_eager=True),
    ] = None,
) -> None:
    """ATC — Automated Test Creation CLI."""


@app.command()
def run(
    config: Annotated[Path, typer.Option("--config", "-c", help="Path to run config JSON file")] = Path("run.json"),
    url: Annotated[Optional[str], typer.Option("--url", "-u", help="ADO work item URL")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Simulate without making changes")] = False,
) -> None:
    """Execute the ATC pipeline: fetch ADO items, generate feature files."""
    from atc.executor import execute_pipeline

    run_config = _load_config(config)

    # CLI --url overrides config
    if url:
        run_config.url = url
    if dry_run:
        run_config.options.dry_run = True

    if not run_config.url:
        console.print("[red]Error: No ADO URL provided. Use --url or set 'url' in config.[/red]")
        raise typer.Exit(code=2)

    asyncio.run(execute_pipeline(run_config))


@app.command()
def validate(
    config: Annotated[Path, typer.Option("--config", "-c", help="Path to run config JSON file")] = Path("run.json"),
) -> None:
    """Validate a run configuration file."""
    run_config = _load_config(config)
    console.print(f"[green]Config is valid.[/green]")
    console.print(run_config.model_dump_json(indent=2))


@app.command()
def init() -> None:
    """One-time setup: create default config and directory structure."""
    configs_dir = Path("configs/runs")
    configs_dir.mkdir(parents=True, exist_ok=True)

    example_config = configs_dir / "example.json"
    if not example_config.exists():
        default = RunConfig(
            url="https://dev.azure.com/org/project/_workitems/edit/12345",
            product_name="EHB",
        )
        example_config.write_text(default.model_dump_json(indent=2))
        console.print(f"[green]Created example config: {example_config}[/green]")
    else:
        console.print(f"[yellow]Config already exists: {example_config}[/yellow]")

    console.print("[green]Setup complete. Set ATC_ADO_PAT environment variable to get started.[/green]")


def _load_config(path: Path) -> RunConfig:
    """Load and validate a run configuration file."""
    if not path.exists():
        console.print(f"[red]Config file not found: {path}[/red]")
        raise typer.Exit(code=2)
    try:
        data = json.loads(path.read_text())
        return RunConfig(**data)
    except Exception as e:
        console.print(f"[red]Invalid config: {e}[/red]")
        raise typer.Exit(code=2)
