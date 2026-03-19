"""Workspace browser — explore generated artifacts."""

from __future__ import annotations

import shutil
from pathlib import Path

from nicegui import ui

from atc.ui.components import scan_workspace
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

# ── Module-level UI references ────────────────────────────────────────
_file_viewer_container: ui.column | None = None


def render() -> None:
    """Render the workspace browser page."""
    global _file_viewer_container

    # Page header
    with ui.row().classes("w-full items-center justify-between"):
        with ui.column().classes("gap-0"):
            ui.label("Workspace Browser").classes("text-3xl font-bold")
            ui.label("Explore generated artifacts and feature files").classes(
                "text-sm text-slate-400"
            )

    # Workspace path input
    workspace_dir = app_state.config_data.get("workspace_dir", "./workspace")
    with ui.row().classes("w-full items-center gap-2"):
        path_input = ui.input(
            "Workspace directory",
            value=str(workspace_dir),
        ).classes("flex-1")
        ui.button(
            "Reload",
            icon="refresh",
            on_click=lambda: _browse(path_input.value),
        ).props("outline no-caps")

    workspace_path = Path(workspace_dir)
    if not workspace_path.exists():
        with ui.card().classes("w-full").style(
            "border: 1px dashed #334155; background: transparent;"
        ):
            with ui.column().classes("items-center py-8 gap-3"):
                ui.icon("folder_off", size="xl").classes("text-slate-600")
                ui.label("Workspace directory does not exist yet").classes(
                    "text-lg font-semibold text-slate-400"
                )
                ui.label("Run the pipeline first to generate artifacts.").classes(
                    "text-sm text-slate-500"
                )
                ui.button(
                    "Go to Pipeline",
                    icon="play_circle",
                    on_click=lambda: ui.navigate.to("/pipeline"),
                ).props("color=indigo unelevated no-caps")
        return

    # Stats row
    metrics = scan_workspace(workspace_path)
    with ui.row().classes("w-full gap-4 flex-wrap"):
        _stat_card("Feature Files", str(metrics.feature_files), "description", "#10b981")
        _stat_card("Scenarios", str(metrics.total_scenarios), "checklist", "#6366f1")
        _stat_card("Prompts", str(metrics.prompt_files), "edit_note", "#3b82f6")
        _stat_card("Total Files", str(metrics.total_files), "inventory_2", "#64748b")

    # Tree toggle
    tree_visible = {"value": True}
    tree_panel: ui.column | None = None

    def _toggle_tree() -> None:
        tree_visible["value"] = not tree_visible["value"]
        if tree_panel is not None:
            tree_panel.set_visibility(tree_visible["value"])
        toggle_btn.props(
            f'icon={"chevron_left" if tree_visible["value"] else "menu"}'
        )

    with ui.row().classes("items-center gap-2 mt-2"):
        toggle_btn = ui.button(
            icon="chevron_left",
            on_click=_toggle_tree,
        ).props("flat dense round").tooltip("Toggle file tree")
        ui.label("Files").classes("text-lg font-semibold")

    # Main content: tree + viewer side by side
    with ui.row().classes("w-full gap-4 items-start flex-nowrap"):
        # Left: Collapsible tree
        tree_panel = ui.column().classes("shrink-0")
        with tree_panel:
            with ui.card().classes(
                "max-h-[600px] overflow-y-auto overflow-x-auto"
            ).style("width: 340px;"):
                _build_tree(workspace_path, workspace_path)

        # Right: File viewer
        with ui.column().classes("flex-1 min-w-0"):
            ui.label("File Contents").classes("text-lg font-semibold")
            _file_viewer_container = ui.column().classes("w-full")
            with _file_viewer_container:
                with ui.card().classes("w-full").style(
                    "border: 1px dashed #334155; background: transparent;"
                ):
                    with ui.column().classes("items-center py-6 gap-2"):
                        ui.icon("description", size="lg").classes("text-slate-600")
                        ui.label("Select a file from the tree").classes(
                            "text-sm text-slate-400"
                        )


# ── Components ───────────────────────────────────────────────────────


def _stat_card(label: str, value: str, icon: str, color: str) -> None:
    with ui.card().classes("flex-1 stat-card min-w-[140px]").style(
        f"border-left-color: {color};"
    ):
        with ui.row().classes("items-center gap-3"):
            ui.icon(icon).classes("text-2xl").style(f"color: {color};")
            with ui.column().classes("gap-0"):
                ui.label(value).classes("text-2xl font-bold")
                ui.label(label).classes("text-xs text-slate-400 font-medium")


def _build_tree(path: Path, root: Path, depth: int = 0) -> None:
    """Recursively build a clickable file tree with delete buttons."""
    if depth > 8:
        return

    try:
        entries = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    except PermissionError:
        return

    for entry in entries:
        if entry.name.startswith("."):
            continue

        if entry.is_dir():
            with ui.expansion(
                entry.name, icon="folder"
            ).classes("tree-folder-row").props(
                "dense dense-toggle switch-toggle-side"
            ) as exp:
                _build_tree(entry, root, depth + 1)
            # Right-click context menu for delete
            with ui.menu().props("context-menu"):
                ui.menu_item(
                    f"Delete \u201c{entry.name}\u201d",
                    on_click=lambda _, p=entry: _confirm_delete(p),
                ).props("dense").classes("text-red-400")
        else:
            icon = _file_icon(entry)
            with ui.row().classes(
                "items-center flex-nowrap gap-1 tree-file-row"
            ):
                ui.button(
                    entry.name,
                    icon=icon,
                    on_click=lambda _, p=entry: _show_file(p),
                ).props("flat dense align=left no-wrap").classes(
                    "text-left text-xs"
                )
                _del_btn = ui.button(
                    icon="close",
                    on_click=lambda _, p=entry: _confirm_delete(p),
                ).props("flat dense round size=xs color=negative").classes(
                    "tree-del-btn shrink-0"
                ).tooltip(f"Delete {entry.name}")


def _confirm_delete(path: Path) -> None:
    """Show a confirmation dialog before deleting a file or folder."""
    if not _is_within_root(path, _get_allowed_root()):
        ui.notify("Cannot delete: path is outside the workspace.", type="negative")
        return

    is_dir = path.is_dir()
    kind = "folder" if is_dir else "file"

    # Count contents for folders
    extra = ""
    if is_dir:
        try:
            contents = list(path.rglob("*"))
            file_count = sum(1 for c in contents if c.is_file())
            if file_count:
                extra = f" ({file_count} file{'s' if file_count != 1 else ''} inside)"
        except Exception:
            pass

    with ui.dialog() as dialog, ui.card().classes("min-w-[360px]"):
        with ui.column().classes("gap-3 w-full"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("warning", size="sm").classes("text-red-400")
                ui.label(f"Delete {kind}?").classes("text-lg font-semibold")

            ui.label(f"{path.name}{extra}").classes("font-mono text-sm text-slate-300")
            ui.label(
                "This action cannot be undone."
            ).classes("text-xs text-red-400")

            with ui.row().classes("justify-end gap-2 mt-2"):
                ui.button(
                    "Cancel",
                    on_click=dialog.close,
                ).props("flat no-caps")
                ui.button(
                    f"Delete {kind}",
                    icon="delete",
                    on_click=lambda: _execute_delete(path, dialog),
                ).props("color=negative unelevated no-caps")

    dialog.open()


def _execute_delete(path: Path, dialog) -> None:
    """Actually delete the file or folder, then refresh the page."""
    if not _is_within_root(path, _get_allowed_root()):
        ui.notify("Cannot delete: path is outside the workspace.", type="negative")
        dialog.close()
        return

    try:
        if path.is_dir():
            shutil.rmtree(path)
            ui.notify(f"Deleted folder: {path.name}", type="positive")
        elif path.is_file():
            path.unlink()
            ui.notify(f"Deleted file: {path.name}", type="positive")
        else:
            ui.notify("Path no longer exists.", type="warning")
    except Exception as e:
        ui.notify(f"Delete failed: {e}", type="negative")
        dialog.close()
        return

    dialog.close()

    # Clear file viewer if the deleted path was being viewed
    if _file_viewer_container is not None:
        _file_viewer_container.clear()
        with _file_viewer_container:
            with ui.card().classes("w-full").style(
                "border: 1px dashed #334155; background: transparent;"
            ):
                with ui.column().classes("items-center py-6 gap-2"):
                    ui.icon("description", size="lg").classes("text-slate-600")
                    ui.label("Select a file from the tree").classes(
                        "text-sm text-slate-400"
                    )

    # Refresh the page to rebuild the tree
    ui.navigate.to("/workspace")


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
    workspace_dir = app_state.config_data.get("workspace_dir", "./workspace")
    return Path(workspace_dir).resolve()


def _is_within_root(path: Path, root: Path) -> bool:
    try:
        return path.resolve().is_relative_to(root)
    except (ValueError, OSError):
        return False


def _show_file(path: Path) -> None:
    """Display file contents in the viewer panel."""
    global _file_viewer_container
    if _file_viewer_container is None:
        return

    # Guard against stale client reference (e.g. user navigated away and back)
    try:
        _ = _file_viewer_container.client
    except RuntimeError:
        _file_viewer_container = None
        return

    if not _is_within_root(path, _get_allowed_root()):
        ui.notify("Access denied: file is outside the workspace directory.", type="negative")
        return

    _file_viewer_container.clear()

    with _file_viewer_container:
        with ui.card().classes("w-full overflow-hidden"):
            # File header with delete button
            with ui.row().classes("items-center gap-2 w-full min-w-0"):
                ui.icon(_file_icon(path), size="xs").classes("text-indigo-400 shrink-0")
                ui.label(path.name).classes("font-semibold shrink-0")
                ui.label(str(path)).classes(
                    "text-xs text-slate-500 font-mono truncate min-w-0 flex-1"
                )
                ui.button(
                    icon="delete_outline",
                    on_click=lambda _, p=path: _confirm_delete(p),
                ).props("flat dense round size=sm color=negative").tooltip(
                    "Delete this file"
                )

            try:
                content = path.read_text(encoding="utf-8")
            except Exception as e:
                ui.label(f"Cannot read file: {e}").classes("text-red-400")
                return

            ext = path.suffix.lower()
            lang = LANG_MAP.get(ext, "text")

            # File metadata
            size = path.stat().st_size
            size_label = f"{size:,} bytes" if size < 10240 else f"{size / 1024:.1f} KB"
            lines = content.count("\n") + 1
            with ui.row().classes("gap-3 mt-1"):
                ui.badge(f"{lines} lines", color="indigo").props("outline")
                ui.badge(size_label, color="indigo").props("outline")
                ui.badge(ext or "no ext", color="indigo").props("outline")

            ui.separator().classes("my-2")

            # Code viewer
            ui.code(content, language=lang).classes("w-full")


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
