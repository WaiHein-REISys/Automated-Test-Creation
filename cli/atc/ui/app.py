"""NiceGUI application setup and page routing."""

from __future__ import annotations

from nicegui import app, ui


def start_ui(port: int = 8080, reload: bool = False, native: bool = False) -> None:
    """Launch the ATC web UI."""

    # Import pages to register their routes
    from atc.ui.pages import config_editor, dashboard, pipeline, settings, workspace  # noqa: F401

    # --- Header / Navigation (shared across all pages) ---
    @ui.page("/")
    def index():
        _build_layout(dashboard.render)

    @ui.page("/config")
    def config_page():
        _build_layout(config_editor.render)

    @ui.page("/pipeline")
    def pipeline_page():
        _build_layout(pipeline.render)

    @ui.page("/workspace")
    def workspace_page():
        _build_layout(workspace.render)

    @ui.page("/settings")
    def settings_page():
        _build_layout(settings.render)

    ui.run(
        title="ATC — Automated Test Creation",
        port=port,
        reload=reload,
        native=native,
        favicon="🧪",
        dark=True,
        show=True,
    )


def _build_layout(page_render_fn):
    """Wrap a page render function with the shared navigation layout."""
    with ui.header().classes("items-center justify-between bg-slate-800 px-6"):
        with ui.row().classes("items-center gap-2"):
            ui.label("ATC").classes("text-2xl font-bold text-white")
            ui.label("Automated Test Creation").classes("text-sm text-slate-400")
        with ui.row().classes("gap-1"):
            ui.button("Dashboard", on_click=lambda: ui.navigate.to("/"), icon="home").props(
                "flat color=white"
            )
            ui.button("Config", on_click=lambda: ui.navigate.to("/config"), icon="settings").props(
                "flat color=white"
            )
            ui.button(
                "Pipeline", on_click=lambda: ui.navigate.to("/pipeline"), icon="play_circle"
            ).props("flat color=white")
            ui.button(
                "Workspace", on_click=lambda: ui.navigate.to("/workspace"), icon="folder_open"
            ).props("flat color=white")
            ui.button(
                "Settings", on_click=lambda: ui.navigate.to("/settings"), icon="tune"
            ).props("flat color=white")

    with ui.column().classes("w-full max-w-6xl mx-auto p-6 gap-4"):
        page_render_fn()
