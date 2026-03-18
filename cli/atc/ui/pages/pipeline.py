"""Pipeline execution page — run, monitor progress, view results."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from nicegui import ui

from atc.core.progress import Phase, PipelineResult
from atc.executor import PipelineCancelled
from atc.infra.config import RunConfig
from atc.ui.state import NiceGuiReporter, app_state


def render() -> None:
    """Render the pipeline execution page."""
    ui.label("Pipeline Execution").classes("text-3xl font-bold")

    # Config summary
    with ui.card().classes("w-full"):
        ui.label("Current Configuration").classes("font-semibold text-blue-400")
        if app_state.config_data:
            url = app_state.config_data.get("url", "Not set")
            product = app_state.config_data.get("product_name", "Not set")
            provider = app_state.config_data.get("provider", {}).get("type", "prompt_only")
            dry_run = app_state.config_data.get("options", {}).get("dry_run", False)

            with ui.row().classes("gap-6"):
                with ui.column().classes("gap-0"):
                    ui.label("URL").classes("text-xs text-slate-400")
                    ui.label(url[:80]).classes("text-sm font-mono")
                with ui.column().classes("gap-0"):
                    ui.label("Product").classes("text-xs text-slate-400")
                    ui.label(product).classes("text-sm")
                with ui.column().classes("gap-0"):
                    ui.label("Provider").classes("text-xs text-slate-400")
                    ui.label(provider).classes("text-sm")
                if dry_run:
                    ui.badge("DRY RUN", color="orange").classes("self-center")
        else:
            ui.label("No config loaded.").classes("text-slate-400")
            ui.button(
                "Go to Config Editor",
                icon="settings",
                on_click=lambda: ui.navigate.to("/config"),
            )

    # Controls
    with ui.row().classes("gap-2"):
        run_btn = ui.button(
            "Run Pipeline",
            icon="play_arrow",
            on_click=_start_pipeline,
        ).props("color=positive")

        cancel_btn = ui.button(
            "Cancel",
            icon="stop",
            on_click=_cancel_pipeline,
        ).props("color=negative outlined")

        if app_state.is_running:
            run_btn.disable()
        else:
            cancel_btn.disable()

        # Load from file
        config_file = ui.input(
            "Config file",
            value=app_state.config_path or "run.json",
        ).classes("w-64")
        ui.button(
            "Load & Run",
            icon="upload_file",
            on_click=lambda: _load_and_run(config_file.value),
        ).props("outlined")

    # Phase stepper
    ui.label("Pipeline Phases").classes("text-xl font-semibold mt-4")
    with ui.card().classes("w-full"):
        with ui.row().classes("w-full justify-between"):
            for phase in Phase:
                status = app_state.phase_progress.get(phase.value, "pending")
                _render_phase_step(phase, status)

    # Progress and log in two columns
    with ui.row().classes("w-full gap-4 mt-4"):
        # Left: Live log
        with ui.column().classes("flex-1"):
            ui.label("Live Log").classes("text-lg font-semibold")
            log_container = ui.column().classes(
                "w-full max-h-96 overflow-y-auto bg-slate-900 rounded p-3 gap-0"
            )
            with log_container:
                if app_state.logs:
                    for entry in app_state.logs[-100:]:  # show last 100
                        _render_log_entry(entry)
                else:
                    ui.label("No log entries yet. Run the pipeline to see output.").classes(
                        "text-slate-500 text-sm"
                    )

        # Right: Results summary
        with ui.column().classes("w-80"):
            ui.label("Results").classes("text-lg font-semibold")
            if app_state.result:
                _render_results(app_state.result)
            elif app_state.is_running:
                with ui.card().classes("w-full"):
                    ui.spinner("dots", size="lg")
                    ui.label("Running...").classes("text-slate-400")
            else:
                with ui.card().classes("w-full"):
                    ui.label("Run the pipeline to see results.").classes("text-slate-400")


def _render_phase_step(phase: Phase, status: str) -> None:
    """Render a single phase step indicator."""
    color_map = {
        "pending": "text-slate-500",
        "active": "text-blue-400",
        "done": "text-green-400",
    }
    icon_map = {
        "pending": "radio_button_unchecked",
        "active": "pending",
        "done": "check_circle",
    }
    with ui.column().classes("items-center gap-1"):
        ui.icon(icon_map.get(status, "radio_button_unchecked")).classes(
            color_map.get(status, "text-slate-500") + " text-2xl"
        )
        ui.label(phase.label).classes(
            f"text-xs {color_map.get(status, 'text-slate-500')}"
        )


def _render_log_entry(entry) -> None:
    """Render a single log line."""
    level_colors = {
        "info": "text-slate-300",
        "warning": "text-yellow-400",
        "error": "text-red-400",
        "success": "text-green-400",
    }
    color = level_colors.get(entry.level, "text-slate-300")
    ui.label(
        f"[{entry.timestamp}] [{entry.phase}] {entry.message}"
    ).classes(f"text-xs font-mono {color} whitespace-pre-wrap")


def _render_results(result: PipelineResult) -> None:
    """Render the pipeline results summary."""
    with ui.card().classes("w-full"):
        with ui.column().classes("gap-2"):
            with ui.row().classes("justify-between"):
                ui.label("Generated").classes("text-green-400")
                ui.label(str(result.generated)).classes("font-bold text-green-400")
            with ui.row().classes("justify-between"):
                ui.label("Failed").classes("text-red-400")
                ui.label(str(result.failed)).classes("font-bold text-red-400")
            with ui.row().classes("justify-between"):
                ui.label("Skipped").classes("text-yellow-400")
                ui.label(str(result.skipped)).classes("font-bold text-yellow-400")
            ui.separator()
            with ui.row().classes("justify-between"):
                ui.label("Total").classes("font-semibold")
                ui.label(str(result.total)).classes("font-bold")
            if result.workspace_root:
                ui.separator()
                ui.button(
                    "Browse Workspace",
                    icon="folder_open",
                    on_click=lambda: ui.navigate.to("/workspace"),
                ).props("flat color=primary")


async def _start_pipeline() -> None:
    """Start the pipeline execution."""
    if app_state.is_running:
        ui.notify("Pipeline is already running", type="warning")
        return

    if not app_state.config_data:
        ui.notify("No config loaded. Go to Config Editor first.", type="negative")
        return

    try:
        config = RunConfig(**app_state.config_data)
    except Exception as e:
        ui.notify(f"Invalid config: {e}", type="negative")
        return

    app_state.reset_run()
    app_state.is_running = True

    reporter = NiceGuiReporter(app_state, on_update=lambda: ui.navigate.to("/pipeline"))

    try:
        from atc.executor import execute_pipeline

        await execute_pipeline(config, reporter=reporter, cancel_event=app_state.cancel_event)

        # Build result
        result = PipelineResult(workspace_root=str(config.workspace_dir))
        # Parse counts from logs
        for entry in app_state.logs:
            if "Generation complete:" in entry.message:
                parts = entry.message
                try:
                    result.generated = int(parts.split("generated")[0].split()[-1])
                    result.failed = int(parts.split("failed")[0].split()[-1])
                    result.skipped = int(parts.split("skipped")[0].split()[-1])
                    result.total = int(parts.split("out of")[1].strip().rstrip(")"))
                except (ValueError, IndexError):
                    pass
                break

        app_state.result = result
        app_state.save_run(result)
        ui.notify("Pipeline completed!", type="positive")

    except PipelineCancelled:
        ui.notify("Pipeline cancelled.", type="warning")
        from atc.ui.state import LogEntry
        from datetime import datetime

        app_state.add_log(LogEntry(
            timestamp=datetime.now().strftime("%H:%M:%S"),
            phase="Cancelled",
            message="Pipeline cancelled by user",
            level="warning",
        ))
    except Exception as e:
        ui.notify(f"Pipeline error: {e}", type="negative")
        from atc.ui.state import LogEntry
        from datetime import datetime

        app_state.add_log(LogEntry(
            timestamp=datetime.now().strftime("%H:%M:%S"),
            phase="Error",
            message=str(e),
            level="error",
        ))
    finally:
        app_state.is_running = False
        ui.navigate.to("/pipeline")


def _cancel_pipeline() -> None:
    """Request pipeline cancellation."""
    app_state.cancel_event.set()
    ui.notify("Cancellation requested...", type="warning")


async def _load_and_run(path_str: str) -> None:
    """Load a config file and immediately run the pipeline."""
    path = Path(path_str)
    if not path.exists():
        ui.notify(f"File not found: {path}", type="negative")
        return
    try:
        data = json.loads(path.read_text())
        config = RunConfig(**data)
        app_state.config_data = json.loads(config.model_dump_json())
        app_state.config_path = str(path)
        await _start_pipeline()
    except Exception as e:
        ui.notify(f"Error: {e}", type="negative")
