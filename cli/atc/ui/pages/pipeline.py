"""Pipeline execution page — run, monitor progress, view results."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from nicegui import ui

from atc.core.progress import Phase, PipelineResult
from atc.executor import PipelineCancelled
from atc.infra.config import RunConfig
from atc.ui.state import NiceGuiReporter, app_state

logger = logging.getLogger(__name__)

# ── Persistent UI element references ─────────────────────────────────
# Set once per page render and reused by the reporter callback so we
# never call ui.navigate.to() while the pipeline is running.
_log_container: ui.column | None = None
_phase_row: ui.row | None = None
_results_column: ui.column | None = None
_run_btn: ui.button | None = None
_cancel_btn: ui.button | None = None

# Level → Tailwind color class
_LEVEL_COLORS = {
    "info": "text-slate-300",
    "warning": "text-yellow-400",
    "error": "text-red-400",
    "success": "text-green-400",
}


def render() -> None:
    """Render the pipeline execution page."""
    global _log_container, _phase_row, _results_column, _run_btn, _cancel_btn

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
        _run_btn = ui.button(
            "Run Pipeline",
            icon="play_arrow",
            on_click=_start_pipeline,
        ).props("color=positive")

        _cancel_btn = ui.button(
            "Cancel",
            icon="stop",
            on_click=_cancel_pipeline,
        ).props("color=negative outlined")

        if app_state.is_running:
            _run_btn.disable()
        else:
            _cancel_btn.disable()

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
        _phase_row = ui.row().classes("w-full justify-between")
        with _phase_row:
            for phase in Phase:
                status = app_state.phase_progress.get(phase.value, "pending")
                _render_phase_step(phase, status)

    # Progress and log in two columns
    with ui.row().classes("w-full gap-4 mt-4"):
        # Left: Live log
        with ui.column().classes("flex-1"):
            ui.label("Live Log").classes("text-lg font-semibold")
            _log_container = ui.column().classes(
                "w-full max-h-96 overflow-y-auto bg-slate-900 rounded p-3 gap-0"
            )
            with _log_container:
                if app_state.logs:
                    for entry in app_state.logs[-100:]:
                        _render_log_entry(entry)
                else:
                    ui.label(
                        "No log entries yet. Run the pipeline to see output."
                    ).classes("text-slate-500 text-sm")

        # Right: Results summary
        with ui.column().classes("w-80"):
            ui.label("Results").classes("text-lg font-semibold")
            _results_column = ui.column().classes("w-full")
            with _results_column:
                if app_state.result:
                    _render_results(app_state.result)
                elif app_state.is_running:
                    with ui.card().classes("w-full"):
                        ui.spinner("dots", size="lg")
                        ui.label("Running...").classes("text-slate-400")
                else:
                    with ui.card().classes("w-full"):
                        ui.label("Run the pipeline to see results.").classes(
                            "text-slate-400"
                        )


# ── Phase / log / result renderers ────────────────────────────────────

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
    color = _LEVEL_COLORS.get(entry.level, "text-slate-300")
    ui.label(
        f"[{entry.timestamp}] [{entry.phase}] {entry.message}"
    ).classes(f"text-xs font-mono {color} whitespace-pre-wrap")


def _render_results(result: PipelineResult) -> None:
    """Render the pipeline results summary."""
    with ui.card().classes("w-full"):
        ui.label("Generation").classes("font-semibold text-blue-400 text-sm")
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

    # Test execution results (if tests were run)
    tr = result.test_result
    if tr.executed:
        with ui.card().classes("w-full mt-2"):
            ui.label("Test Execution").classes("font-semibold text-blue-400 text-sm")
            status_color = "text-green-400" if tr.exit_code == 0 else "text-red-400"
            status_label = "PASSED" if tr.exit_code == 0 else "FAILED"
            with ui.column().classes("gap-2"):
                with ui.row().classes("justify-between"):
                    ui.label("Status").classes("font-semibold")
                    ui.label(status_label).classes(f"font-bold {status_color}")
                with ui.row().classes("justify-between"):
                    ui.label("Tests Passed").classes("text-green-400")
                    ui.label(str(tr.passed)).classes("font-bold text-green-400")
                with ui.row().classes("justify-between"):
                    ui.label("Tests Failed").classes("text-red-400")
                    ui.label(str(tr.failed)).classes("font-bold text-red-400")
                ui.separator()
                with ui.row().classes("justify-between"):
                    ui.label("Total Tests").classes("font-semibold")
                    ui.label(str(tr.total)).classes("font-bold")

                if tr.trx_path:
                    ui.label(f"TRX: {tr.trx_path}").classes("text-xs text-slate-400 break-all")
                if tr.extent_report:
                    ui.label(f"Report: {tr.extent_report}").classes("text-xs text-slate-400 break-all")

                if tr.failed_tests:
                    with ui.expansion("Failed Tests", icon="error").classes("w-full"):
                        for ft in tr.failed_tests:
                            with ui.row().classes("gap-2"):
                                ui.icon("close", size="xs").classes("text-red-400")
                                ui.label(ft.get("name", "")).classes("text-xs font-mono text-red-300")
                            if ft.get("error_message"):
                                ui.label(ft["error_message"][:200]).classes(
                                    "text-xs text-slate-400 ml-6"
                                )


# ── Live UI update callback (called from NiceGuiReporter) ─────────────

def _push_live_update() -> None:
    """Append the latest log entry and refresh phase indicators in-place.

    This runs inside the NiceGUI event loop on the *same* client that
    owns the page elements, so it is safe to mutate them directly — no
    page navigation required.
    """
    # Append new log entry
    if _log_container is not None and app_state.logs:
        latest = app_state.logs[-1]
        try:
            with _log_container:
                _render_log_entry(latest)
            _log_container.scroll_to(percent=1.0)  # auto-scroll to bottom
        except Exception:
            pass  # element may be gone if user navigated away

    # Refresh phase indicators
    if _phase_row is not None:
        try:
            _phase_row.clear()
            with _phase_row:
                for phase in Phase:
                    status = app_state.phase_progress.get(phase.value, "pending")
                    _render_phase_step(phase, status)
        except Exception:
            pass


def _safe_notify(message: str, type: str = "info") -> None:
    """Call ui.notify, swallowing errors if the UI context is gone."""
    try:
        ui.notify(message, type=type)
    except Exception:
        logger.info("UI notify skipped (context unavailable): %s", message)


# ── Pipeline lifecycle ────────────────────────────────────────────────

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

    # Update button states
    if _run_btn is not None:
        try:
            _run_btn.disable()
        except Exception:
            pass
    if _cancel_btn is not None:
        try:
            _cancel_btn.enable()
        except Exception:
            pass

    # Clear previous log entries and show spinner
    if _log_container is not None:
        try:
            _log_container.clear()
        except Exception:
            pass
    if _results_column is not None:
        try:
            _results_column.clear()
            with _results_column:
                with ui.card().classes("w-full"):
                    ui.spinner("dots", size="lg")
                    ui.label("Running...").classes("text-slate-400")
        except Exception:
            pass

    # Use in-place UI updates — never navigate while running
    reporter = NiceGuiReporter(app_state, on_update=_push_live_update)

    try:
        from atc.executor import execute_pipeline

        await execute_pipeline(
            config, reporter=reporter, cancel_event=app_state.cancel_event
        )

        # Build result
        from atc.core.progress import TestExecutionResult

        result = PipelineResult(workspace_root=str(config.workspace_dir))
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
            # Parse test results from log entries
            if "All tests passed:" in entry.message:
                try:
                    nums = entry.message.split("All tests passed:")[1].split("(")[0].strip()
                    p, t = nums.split("/")
                    result.test_result = TestExecutionResult(
                        executed=True, exit_code=0,
                        passed=int(p), total=int(t), failed=0,
                        outcome="Passed",
                    )
                except (ValueError, IndexError):
                    result.test_result = TestExecutionResult(executed=True, exit_code=0, outcome="Passed")
            elif "Tests finished:" in entry.message and entry.phase == "Run Tests":
                try:
                    msg = entry.message
                    passed = int(msg.split("passed")[0].split()[-1])
                    failed = int(msg.split("failed")[0].split()[-1])
                    total = int(msg.split("out of")[1].strip())
                    result.test_result = TestExecutionResult(
                        executed=True, exit_code=1,
                        passed=passed, failed=failed, total=total,
                        outcome="Failed",
                    )
                except (ValueError, IndexError):
                    result.test_result = TestExecutionResult(executed=True, exit_code=1, outcome="Failed")

        app_state.result = result
        app_state.save_run(result)
        _safe_notify("Pipeline completed!", type="positive")

    except PipelineCancelled:
        _safe_notify("Pipeline cancelled.", type="warning")
        from atc.ui.state import LogEntry
        from datetime import datetime

        app_state.add_log(LogEntry(
            timestamp=datetime.now().strftime("%H:%M:%S"),
            phase="Cancelled",
            message="Pipeline cancelled by user",
            level="warning",
        ))
        try:
            _push_live_update()
        except Exception:
            pass

    except Exception as e:
        logger.exception("Pipeline error")
        _safe_notify(f"Pipeline error: {e}", type="negative")

        from atc.ui.state import LogEntry
        from datetime import datetime

        app_state.add_log(LogEntry(
            timestamp=datetime.now().strftime("%H:%M:%S"),
            phase="Error",
            message=str(e),
            level="error",
        ))
        try:
            _push_live_update()
        except Exception:
            pass

    finally:
        app_state.is_running = False

        # Restore button states
        if _run_btn is not None:
            try:
                _run_btn.enable()
            except Exception:
                pass
        if _cancel_btn is not None:
            try:
                _cancel_btn.disable()
            except Exception:
                pass

        # Show final results in-place
        if _results_column is not None and app_state.result:
            try:
                _results_column.clear()
                with _results_column:
                    _render_results(app_state.result)
            except Exception:
                pass


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
