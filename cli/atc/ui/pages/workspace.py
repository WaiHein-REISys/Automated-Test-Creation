"""Workspace browser — explore generated artifacts."""

from __future__ import annotations

from pathlib import Path

from nicegui import ui

from atc.ui.state import app_state

# File extensions and their syntax highlighting languages
LANG_MAP = {
    ".feature": "gherkin",
    ".md": "markdown",
    ".json": "json",
    ".py": "python",
    ".txt": "text",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".j2": "jinja2",
}


def render() -> None:
    """Render the workspace browser page."""
    ui.label("Workspace Browser").classes("text-3xl font-bold")

    # Workspace path input
    workspace_dir = app_state.config_data.get("workspace_dir", "./workspace")
    with ui.row().classes("w-full items-center gap-2"):
        path_input = ui.input(
            "Workspace directory",
            value=str(workspace_dir),
        ).classes("flex-1")
        ui.button(
            "Browse",
            icon="refresh",
            on_click=lambda: _browse(path_input.value),
        )

    workspace_path = Path(workspace_dir)
    if not workspace_path.exists():
        with ui.card().classes("w-full"):
            ui.label("Workspace directory does not exist yet.").classes("text-slate-400")
            ui.label("Run the pipeline first to generate artifacts.").classes("text-sm text-slate-500")
            ui.button(
                "Go to Pipeline",
                icon="play_circle",
                on_click=lambda: ui.navigate.to("/pipeline"),
            )
        return

    # Stats
    stats = _compute_stats(workspace_path)
    with ui.row().classes("w-full gap-4"):
        _stat_card("Feature Files", str(stats["features"]), "description", "green")
        _stat_card("Prompts", str(stats["prompts"]), "edit_note", "blue")
        _stat_card("Summaries", str(stats["summaries"]), "article", "amber")
        _stat_card("Total Files", str(stats["total"]), "folder", "slate")

    # Two-column: tree | file viewer
    with ui.row().classes("w-full gap-4 mt-4"):
        # Left: Directory tree
        with ui.column().classes("w-80"):
            ui.label("Files").classes("text-lg font-semibold")
            with ui.card().classes("w-full max-h-[600px] overflow-y-auto"):
                _build_tree(workspace_path, workspace_path)

        # Right: File viewer
        with ui.column().classes("flex-1"):
            ui.label("File Contents").classes("text-lg font-semibold")
            global _file_viewer_container
            _file_viewer_container = ui.column().classes("w-full")
            with _file_viewer_container:
                ui.label("Select a file from the tree to view its contents.").classes(
                    "text-slate-400"
                )


_file_viewer_container = None


def _stat_card(label: str, value: str, icon: str, color: str) -> None:
    with ui.card().classes("flex-1"):
        with ui.row().classes("items-center gap-2"):
            ui.icon(icon).classes(f"text-{color}-400 text-xl")
            with ui.column().classes("gap-0"):
                ui.label(value).classes("text-2xl font-bold")
                ui.label(label).classes("text-xs text-slate-400")


def _compute_stats(root: Path) -> dict[str, int]:
    features = list(root.rglob("*.feature"))
    prompts = list(root.rglob("*prompt*.md"))
    summaries = list(root.rglob("*Summary*.md"))
    total = list(root.rglob("*"))
    total_files = [f for f in total if f.is_file()]
    return {
        "features": len(features),
        "prompts": len(prompts),
        "summaries": len(summaries),
        "total": len(total_files),
    }


def _build_tree(path: Path, root: Path, depth: int = 0) -> None:
    """Recursively build a clickable file tree."""
    if depth > 8:  # safety limit
        return

    try:
        entries = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    except PermissionError:
        return

    for entry in entries:
        if entry.name.startswith("."):
            continue

        if entry.is_dir():
            with ui.expansion(entry.name, icon="folder").classes("w-full"):
                _build_tree(entry, root, depth + 1)
        else:
            icon = _file_icon(entry)
            ui.button(
                entry.name,
                icon=icon,
                on_click=lambda e=entry: _show_file(e),
            ).props("flat dense align=left").classes("w-full text-left text-xs")


def _file_icon(path: Path) -> str:
    ext = path.suffix.lower()
    icons = {
        ".feature": "description",
        ".md": "article",
        ".json": "data_object",
        ".py": "code",
        ".txt": "text_snippet",
    }
    return icons.get(ext, "insert_drive_file")


def _get_allowed_root() -> Path:
    """Return the resolved workspace root that all paths must be confined to."""
    workspace_dir = app_state.config_data.get("workspace_dir", "./workspace")
    return Path(workspace_dir).resolve()


def _is_within_root(path: Path, root: Path) -> bool:
    """Check that a resolved path is within the allowed root directory."""
    try:
        return path.resolve().is_relative_to(root)
    except (ValueError, OSError):
        return False


def _show_file(path: Path) -> None:
    """Display file contents in the viewer panel."""
    global _file_viewer_container
    if _file_viewer_container is None:
        return

    if not _is_within_root(path, _get_allowed_root()):
        ui.notify("Access denied: file is outside the workspace directory.", type="negative")
        return

    _file_viewer_container.clear()

    with _file_viewer_container:
        with ui.card().classes("w-full"):
            with ui.row().classes("items-center justify-between"):
                ui.label(path.name).classes("font-semibold")
                ui.label(str(path)).classes("text-xs text-slate-400 font-mono")

            try:
                content = path.read_text(encoding="utf-8")
            except Exception as e:
                ui.label(f"Cannot read file: {e}").classes("text-red-400")
                return

            ext = path.suffix.lower()
            lang = LANG_MAP.get(ext, "text")

            # File size info
            size = path.stat().st_size
            size_label = f"{size:,} bytes" if size < 10240 else f"{size / 1024:.1f} KB"
            lines = content.count("\n") + 1
            ui.label(f"{lines} lines, {size_label}").classes("text-xs text-slate-500")

            ui.separator()

            # Code viewer with syntax highlighting
            ui.code(content, language=lang).classes("w-full max-h-[500px]")


def _browse(path_str: str) -> None:
    """Navigate to a workspace directory, confined to the current workspace root."""
    requested = Path(path_str).resolve()
    allowed_root = _get_allowed_root()
    if not requested.is_relative_to(allowed_root):
        ui.notify(
            "Access denied: path is outside the workspace directory.",
            type="negative",
        )
        return
    app_state.config_data["workspace_dir"] = path_str
    ui.navigate.to("/workspace")
