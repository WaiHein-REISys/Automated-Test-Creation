"""Dashboard — insights hub with workspace analytics and quick actions."""

from __future__ import annotations

from pathlib import Path

from nicegui import ui

from atc.ui.components import WorkspaceMetrics, scan_workspace
from atc.ui.state import app_state


def render() -> None:
    """Render the dashboard page."""

    # ── Page header ──────────────────────────────────────────────────
    with ui.row().classes("w-full items-center justify-between"):
        with ui.column().classes("gap-0"):
            ui.label("Dashboard").classes("text-3xl font-bold")
            ui.label("Workspace insights and quick actions").classes(
                "text-sm text-slate-400"
            )

    # ── Quick-action cards ───────────────────────────────────────────
    with ui.row().classes("w-full gap-4"):
        _action_card(
            "New Config",
            "Create a run configuration",
            "add_circle",
            "indigo",
            "/config",
        )
        _action_card(
            "Run Pipeline",
            "Execute test generation",
            "play_circle",
            "emerald",
            "/pipeline",
        )
        _action_card(
            "Browse Workspace",
            "View generated artifacts",
            "folder_open",
            "amber",
            "/workspace",
        )

    # ── Pipeline status banner ───────────────────────────────────────
    if app_state.is_running:
        with ui.card().classes("w-full").style(
            "border-left: 4px solid #6366f1; background: rgba(99,102,241,0.06);"
        ):
            with ui.row().classes("items-center gap-3"):
                ui.spinner("dots", size="lg").classes("text-indigo-400")
                with ui.column().classes("gap-0"):
                    ui.label("Pipeline is running...").classes(
                        "text-lg font-semibold text-indigo-300"
                    )
                    phase = app_state.current_phase
                    if phase:
                        ui.label(f"Current phase: {phase.label}").classes(
                            "text-sm text-slate-400"
                        )

    # ── Workspace analytics ──────────────────────────────────────────
    workspace_dir = app_state.config_data.get("workspace_dir", "./workspace")
    workspace_path = Path(workspace_dir)

    if workspace_path.exists():
        metrics = scan_workspace(workspace_path)
        _render_analytics(metrics)
    else:
        _render_empty_workspace()

    # ── Recent runs ──────────────────────────────────────────────────
    _render_recent_runs()


# ── Analytics section ────────────────────────────────────────────────


def _render_analytics(metrics: WorkspaceMetrics) -> None:
    """Render the full analytics dashboard from workspace metrics."""

    # Stat cards row
    with ui.row().classes("w-full gap-4 flex-wrap"):
        _stat_card(
            "Feature Files",
            str(metrics.feature_files),
            "description",
            "#10b981",
            f"+{metrics.feature_files} generated" if metrics.feature_files else "None yet",
        )
        _stat_card(
            "Total Scenarios",
            str(metrics.total_scenarios),
            "checklist",
            "#6366f1",
            f"Across {metrics.feature_files} files",
        )
        _stat_card(
            "Prompts",
            str(metrics.prompt_files),
            "edit_note",
            "#3b82f6",
            "Scenario prompts rendered",
        )
        _stat_card(
            "Total Files",
            str(metrics.total_files),
            "inventory_2",
            "#64748b",
            f"{len(metrics.file_types)} file types",
        )

    # Charts row
    with ui.row().classes("w-full gap-4 mt-2"):
        # Left: Tag distribution chart
        with ui.card().classes("flex-1 min-w-[300px]"):
            ui.label("Scenario Tags").classes("font-semibold text-sm text-slate-300 mb-2")
            if metrics.total_tags:
                # Sort tags by count, take top 10
                sorted_tags = sorted(
                    metrics.total_tags.items(), key=lambda x: x[1], reverse=True
                )[:10]
                tag_names = [t[0] for t in sorted_tags]
                tag_counts = [t[1] for t in sorted_tags]

                ui.echart(
                    {
                        "backgroundColor": "transparent",
                        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
                        "grid": {
                            "left": "3%",
                            "right": "8%",
                            "top": "3%",
                            "bottom": "3%",
                            "containLabel": True,
                        },
                        "xAxis": {"type": "value", "show": False},
                        "yAxis": {
                            "type": "category",
                            "data": list(reversed(tag_names)),
                            "axisLabel": {
                                "color": "#94a3b8",
                                "fontSize": 11,
                                "formatter": "@{value}",
                            },
                            "axisLine": {"show": False},
                            "axisTick": {"show": False},
                        },
                        "series": [
                            {
                                "type": "bar",
                                "data": list(reversed(tag_counts)),
                                "barWidth": "60%",
                                "itemStyle": {
                                    "color": {
                                        "type": "linear",
                                        "x": 0,
                                        "y": 0,
                                        "x2": 1,
                                        "y2": 0,
                                        "colorStops": [
                                            {"offset": 0, "color": "#6366f1"},
                                            {"offset": 1, "color": "#818cf8"},
                                        ],
                                    },
                                    "borderRadius": [0, 4, 4, 0],
                                },
                            }
                        ],
                    }
                ).classes("w-full h-64")
            else:
                ui.label("No tags found yet.").classes("text-slate-500 text-sm")

        # Right: File type breakdown
        with ui.card().classes("flex-1 min-w-[300px]"):
            ui.label("File Types").classes("font-semibold text-sm text-slate-300 mb-2")
            if metrics.file_types:
                # Prepare pie chart data
                colors = [
                    "#6366f1", "#10b981", "#f59e0b", "#3b82f6",
                    "#ef4444", "#8b5cf6", "#ec4899", "#14b8a6",
                ]
                sorted_types = sorted(
                    metrics.file_types.items(), key=lambda x: x[1], reverse=True
                )
                pie_data = [
                    {"value": count, "name": ext or "(no ext)"}
                    for ext, count in sorted_types[:8]
                ]

                ui.echart(
                    {
                        "backgroundColor": "transparent",
                        "tooltip": {
                            "trigger": "item",
                            "formatter": "{b}: {c} ({d}%)",
                        },
                        "series": [
                            {
                                "type": "pie",
                                "radius": ["40%", "70%"],
                                "center": ["50%", "55%"],
                                "avoidLabelOverlap": True,
                                "itemStyle": {
                                    "borderRadius": 6,
                                    "borderColor": "#0f172a",
                                    "borderWidth": 2,
                                },
                                "label": {
                                    "color": "#94a3b8",
                                    "fontSize": 11,
                                },
                                "data": pie_data,
                                "color": colors,
                            }
                        ],
                    }
                ).classes("w-full h-64")
            else:
                ui.label("No files found yet.").classes("text-slate-500 text-sm")

    # Feature files detail table
    if metrics.features:
        with ui.card().classes("w-full mt-2"):
            with ui.row().classes("items-center justify-between mb-2"):
                ui.label("Generated Feature Files").classes(
                    "font-semibold text-sm text-slate-300"
                )
                ui.button(
                    "View All in Workspace",
                    icon="open_in_new",
                    on_click=lambda: ui.navigate.to("/workspace"),
                ).props("flat dense no-caps color=indigo")

            columns = [
                {
                    "name": "name",
                    "label": "Feature Name",
                    "field": "name",
                    "align": "left",
                    "sortable": True,
                },
                {
                    "name": "scenarios",
                    "label": "Scenarios",
                    "field": "scenarios",
                    "align": "center",
                    "sortable": True,
                },
                {
                    "name": "tags",
                    "label": "Tags",
                    "field": "tags",
                    "align": "center",
                    "sortable": True,
                },
                {
                    "name": "lines",
                    "label": "Lines",
                    "field": "lines",
                    "align": "center",
                    "sortable": True,
                },
                {
                    "name": "folder",
                    "label": "Parent",
                    "field": "folder",
                    "align": "left",
                    "sortable": True,
                },
            ]

            rows = [
                {
                    "name": f.name[:60] + ("..." if len(f.name) > 60 else ""),
                    "scenarios": f.scenario_count,
                    "tags": len(f.tags),
                    "lines": f.lines,
                    "folder": f.parent_folder or "-",
                }
                for f in sorted(
                    metrics.features, key=lambda x: x.scenario_count, reverse=True
                )
            ]

            ui.table(columns=columns, rows=rows, row_key="name").classes(
                "w-full"
            ).props("dense flat bordered")


# ── Empty state ──────────────────────────────────────────────────────


def _render_empty_workspace() -> None:
    """Render placeholder when no workspace exists."""
    with ui.card().classes("w-full").style(
        "border: 1px dashed #334155; background: transparent;"
    ):
        with ui.column().classes("items-center py-8 gap-3"):
            ui.icon("science", size="xl").classes("text-slate-600")
            ui.label("No workspace data yet").classes("text-lg font-semibold text-slate-400")
            ui.label(
                "Run the pipeline to generate feature files and see analytics here."
            ).classes("text-sm text-slate-500")
            ui.button(
                "Go to Pipeline",
                icon="play_circle",
                on_click=lambda: ui.navigate.to("/pipeline"),
            ).props("color=indigo unelevated no-caps")


# ── Recent runs ──────────────────────────────────────────────────────


def _render_recent_runs() -> None:
    """Render the recent pipeline runs table."""
    with ui.row().classes("items-center justify-between mt-4"):
        ui.label("Recent Runs").classes("text-xl font-semibold")
        if app_state.run_history:
            ui.badge(
                f"{len(app_state.run_history)} total",
                color="indigo",
            ).props("outline")

    if not app_state.run_history:
        with ui.card().classes("w-full"):
            ui.label(
                "No runs yet. Create a config and run the pipeline to get started."
            ).classes("text-slate-400 text-sm")
    else:
        with ui.card().classes("w-full"):
            columns = [
                {
                    "name": "time",
                    "label": "Time",
                    "field": "time",
                    "align": "left",
                    "sortable": True,
                },
                {
                    "name": "product",
                    "label": "Product",
                    "field": "product",
                    "align": "left",
                },
                {
                    "name": "url",
                    "label": "ADO URL",
                    "field": "url",
                    "align": "left",
                },
                {
                    "name": "generated",
                    "label": "Generated",
                    "field": "generated",
                    "align": "center",
                    "sortable": True,
                },
                {
                    "name": "failed",
                    "label": "Failed",
                    "field": "failed",
                    "align": "center",
                },
                {
                    "name": "skipped",
                    "label": "Skipped",
                    "field": "skipped",
                    "align": "center",
                },
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
            ui.table(columns=columns, rows=rows).classes("w-full").props(
                "dense flat bordered"
            )


# ── Reusable card components ─────────────────────────────────────────


def _action_card(
    title: str, subtitle: str, icon: str, color: str, href: str
) -> None:
    """Quick-action card with hover effect."""
    with ui.card().classes("flex-1 cursor-pointer card-hover").on(
        "click", lambda: ui.navigate.to(href)
    ).style("min-width: 180px;"):
        with ui.row().classes("items-center gap-3"):
            ui.icon(icon, size="md").classes(f"text-{color}-400")
            with ui.column().classes("gap-0"):
                ui.label(title).classes("text-base font-semibold")
                ui.label(subtitle).classes("text-xs text-slate-400")


def _stat_card(
    label: str, value: str, icon: str, color: str, subtitle: str = ""
) -> None:
    """Metric card with colored left border."""
    with ui.card().classes("flex-1 stat-card min-w-[160px]").style(
        f"border-left-color: {color};"
    ):
        with ui.row().classes("items-center gap-3"):
            ui.icon(icon).classes("text-2xl").style(f"color: {color};")
            with ui.column().classes("gap-0"):
                ui.label(value).classes("text-2xl font-bold")
                ui.label(label).classes("text-xs text-slate-400 font-medium")
        if subtitle:
            ui.label(subtitle).classes("text-[11px] text-slate-500 mt-1")
