"""NiceGUI application setup and page routing."""

from __future__ import annotations

from nicegui import app, ui


def start_ui(port: int = 8080, reload: bool = False, native: bool = False) -> None:
    """Launch the ATC web UI."""

    # Import pages to register their routes
    from atc.ui.pages import config_editor, dashboard, pipeline, settings, workspace  # noqa: F401

    # --- Pages ---
    @ui.page("/")
    def index():
        _build_layout(dashboard.render, active="/")

    @ui.page("/config")
    def config_page():
        _build_layout(config_editor.render, active="/config")

    @ui.page("/pipeline")
    def pipeline_page():
        _build_layout(pipeline.render, active="/pipeline")

    @ui.page("/workspace")
    def workspace_page():
        _build_layout(workspace.render, active="/workspace")

    @ui.page("/settings")
    def settings_page():
        _build_layout(settings.render, active="/settings")

    ui.run(
        title="ATC — Automated Test Creation",
        port=port,
        reload=reload,
        native=native,
        favicon="🧪",
        dark=True,
        show=True,
    )


# Navigation items: (path, icon, label)
_NAV_ITEMS = [
    ("/", "dashboard", "Dashboard"),
    ("/config", "tune", "Configuration"),
    ("/pipeline", "play_circle", "Pipeline"),
    ("/workspace", "folder_open", "Workspace"),
    ("/settings", "settings", "Settings"),
]


def _build_layout(page_render_fn, *, active: str = "/"):
    """Wrap a page render function with the modern sidebar layout."""

    # ── Inject global CSS overrides ──────────────────────────────────
    ui.add_head_html("""
    <style>
      /* Smooth transitions on sidebar items */
      .nav-item { transition: all 0.15s ease; border-radius: 8px; }
      .nav-item:hover { background: rgba(99, 102, 241, 0.12); }
      .nav-item.active { background: rgba(99, 102, 241, 0.18); }

      /* Card hover lift */
      .card-hover { transition: transform 0.15s ease, box-shadow 0.15s ease; }
      .card-hover:hover { transform: translateY(-2px); box-shadow: 0 8px 25px rgba(0,0,0,0.3); }

      /* Stat card gradient borders */
      .stat-card { border-left: 3px solid; border-radius: 10px; }

      /* Scrollbar styling for dark theme */
      ::-webkit-scrollbar { width: 6px; }
      ::-webkit-scrollbar-track { background: transparent; }
      ::-webkit-scrollbar-thumb { background: #475569; border-radius: 3px; }
      ::-webkit-scrollbar-thumb:hover { background: #64748b; }

      /* Workspace tree: file delete button on hover */
      .tree-del-btn { opacity: 0; transition: opacity 0.15s ease; width: 24px; height: 24px; }
      .tree-file-row:hover .tree-del-btn { opacity: 0.7; }
      .tree-file-row:hover .tree-del-btn:hover { opacity: 1; }

      /* Workspace tree: folder labels stay on one line; parent card scrolls */
      .tree-folder-row .q-item__label { white-space: nowrap; }
      .tree-folder-row .q-item { min-height: 32px; }
    </style>
    """)

    # ── Top header bar ───────────────────────────────────────────────
    with ui.header().classes(
        "items-center justify-between px-6 h-14 shadow-lg"
    ).style("background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);"):
        with ui.row().classes("items-center gap-3"):
            ui.icon("science", size="sm").classes("text-indigo-400")
            ui.label("ATC").classes("text-xl font-bold text-white tracking-wide")
            ui.separator().props("vertical").classes("h-5 opacity-30")
            ui.label("Automated Test Creation").classes("text-xs text-slate-400 tracking-wider uppercase")

        with ui.row().classes("items-center gap-2"):
            # Pipeline status indicator in header
            from atc.ui.state import app_state

            if app_state.is_running:
                with ui.row().classes("items-center gap-2 bg-indigo-500/20 rounded-full px-3 py-1"):
                    ui.spinner("dots", size="xs").classes("text-indigo-400")
                    ui.label("Pipeline running").classes("text-xs text-indigo-300")

    # ── Left sidebar drawer ──────────────────────────────────────────
    with ui.left_drawer(value=True, fixed=True).classes("p-0").style(
        "background: #0f172a; width: 220px; border-right: 1px solid #1e293b;"
    ) as drawer:
        # Nav section
        with ui.column().classes("w-full p-3 gap-1 mt-2"):
            ui.label("NAVIGATION").classes(
                "text-[10px] font-bold tracking-widest text-slate-500 px-3 mb-1"
            )
            for path, icon, label in _NAV_ITEMS:
                is_active = path == active
                cls = "nav-item active" if is_active else "nav-item"
                with ui.button(
                    on_click=lambda p=path: ui.navigate.to(p),
                ).props("flat no-caps align=left").classes(
                    f"w-full justify-start px-3 py-2 {cls}"
                ):
                    ui.icon(icon, size="xs").classes(
                        "text-indigo-400" if is_active else "text-slate-400"
                    )
                    ui.label(label).classes(
                        "ml-3 text-sm "
                        + ("text-white font-medium" if is_active else "text-slate-300")
                    )

        ui.separator().classes("my-3 opacity-10")

        # Quick stats in sidebar
        with ui.column().classes("w-full p-3 gap-1"):
            ui.label("QUICK INFO").classes(
                "text-[10px] font-bold tracking-widest text-slate-500 px-3 mb-1"
            )

            from atc.ui.state import app_state

            config_loaded = bool(app_state.config_data.get("url"))
            with ui.row().classes("items-center gap-2 px-3 py-1"):
                ui.icon(
                    "check_circle" if config_loaded else "radio_button_unchecked",
                    size="xs",
                ).classes("text-green-400" if config_loaded else "text-slate-500")
                ui.label("Config loaded" if config_loaded else "No config").classes(
                    "text-xs text-slate-400"
                )

            runs = len(app_state.run_history)
            with ui.row().classes("items-center gap-2 px-3 py-1"):
                ui.icon("history", size="xs").classes("text-slate-400")
                ui.label(f"{runs} past run{'s' if runs != 1 else ''}").classes(
                    "text-xs text-slate-400"
                )

    # ── Main content area ────────────────────────────────────────────
    with ui.column().classes("w-full max-w-7xl mx-auto p-8 gap-6"):
        page_render_fn()
