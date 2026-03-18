"""Dashboard — landing page with recent runs and quick-start."""

from __future__ import annotations

from nicegui import ui

from atc.ui.state import app_state


def render() -> None:
    """Render the dashboard page."""
    ui.label("Dashboard").classes("text-3xl font-bold")

    # Quick-start cards
    with ui.row().classes("w-full gap-4"):
        with ui.card().classes("flex-1 cursor-pointer").on(
            "click", lambda: ui.navigate.to("/config")
        ):
            with ui.row().classes("items-center gap-3"):
                ui.icon("add_circle", size="lg").classes("text-blue-400")
                with ui.column().classes("gap-0"):
                    ui.label("New Config").classes("text-lg font-semibold")
                    ui.label("Create a new run configuration").classes("text-sm text-slate-400")

        with ui.card().classes("flex-1 cursor-pointer").on(
            "click", lambda: ui.navigate.to("/pipeline")
        ):
            with ui.row().classes("items-center gap-3"):
                ui.icon("play_circle", size="lg").classes("text-green-400")
                with ui.column().classes("gap-0"):
                    ui.label("Run Pipeline").classes("text-lg font-semibold")
                    ui.label("Execute test generation pipeline").classes(
                        "text-sm text-slate-400"
                    )

        with ui.card().classes("flex-1 cursor-pointer").on(
            "click", lambda: ui.navigate.to("/workspace")
        ):
            with ui.row().classes("items-center gap-3"):
                ui.icon("folder_open", size="lg").classes("text-amber-400")
                with ui.column().classes("gap-0"):
                    ui.label("Browse Workspace").classes("text-lg font-semibold")
                    ui.label("View generated artifacts").classes("text-sm text-slate-400")

    # Pipeline status
    if app_state.is_running:
        with ui.card().classes("w-full border-l-4 border-blue-500"):
            with ui.row().classes("items-center gap-3"):
                ui.spinner("dots", size="lg")
                ui.label("Pipeline is running...").classes("text-lg")
                phase = app_state.current_phase
                if phase:
                    ui.badge(phase.label, color="blue")

    # Recent runs
    ui.label("Recent Runs").classes("text-xl font-semibold mt-4")

    if not app_state.run_history:
        with ui.card().classes("w-full"):
            ui.label("No runs yet. Create a config and run the pipeline to get started.").classes(
                "text-slate-400"
            )
    else:
        with ui.card().classes("w-full"):
            columns = [
                {"name": "time", "label": "Time", "field": "time", "align": "left"},
                {"name": "product", "label": "Product", "field": "product", "align": "left"},
                {"name": "url", "label": "ADO URL", "field": "url", "align": "left"},
                {"name": "generated", "label": "Generated", "field": "generated", "align": "center"},
                {"name": "failed", "label": "Failed", "field": "failed", "align": "center"},
                {"name": "skipped", "label": "Skipped", "field": "skipped", "align": "center"},
            ]
            rows = [
                {
                    "time": r.timestamp,
                    "product": r.product_name,
                    "url": r.url[:60] + "..." if len(r.url) > 60 else r.url,
                    "generated": r.generated,
                    "failed": r.failed,
                    "skipped": r.skipped,
                }
                for r in app_state.run_history[:10]
            ]
            ui.table(columns=columns, rows=rows).classes("w-full")
