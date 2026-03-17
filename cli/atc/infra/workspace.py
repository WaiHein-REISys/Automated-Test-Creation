"""Workspace builder — creates folder structure with .md summaries and attachments."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from atc.core.models import Attachment, WorkItem, WorkItemNode, WorkspaceManifest, WorkspacePaths
from atc.output.console import console


def sanitize_path(name: str, max_len: int = 100) -> str:
    """Sanitize a string for use as a file/directory name."""
    # Replace invalid path characters
    sanitized = re.sub(r'[<>:"/\\|?*]', "-", name)
    # Collapse multiple hyphens/spaces
    sanitized = re.sub(r"-{2,}", "-", sanitized)
    sanitized = sanitized.strip(" .-")
    # Truncate
    if len(sanitized) > max_len:
        sanitized = sanitized[:max_len].rstrip(" .-")
    return sanitized or "unnamed"


class WorkspaceBuilder:
    """Builds the local workspace folder structure from an ADO work item tree."""

    def __init__(self, workspace_dir: Path, product_name: str) -> None:
        self.workspace_dir = Path(workspace_dir)
        self.product_name = product_name

    async def build_from_tree(
        self,
        root: WorkItemNode,
        ado: "AdoClient",  # type: ignore[name-defined]
        download_attachments: bool = True,
    ) -> WorkspaceManifest:
        """Build the full workspace from a work item tree."""
        manifest = WorkspaceManifest(root=self.workspace_dir)

        # Build recursively with path context
        await self._build_node(
            node=root,
            parent_path=self.workspace_dir / self.product_name / "EPIC",
            manifest=manifest,
            ado=ado,
            download_attachments=download_attachments,
            depth=0,
        )

        return manifest

    async def _build_node(
        self,
        node: WorkItemNode,
        parent_path: Path,
        manifest: WorkspaceManifest,
        ado: "AdoClient",  # type: ignore[name-defined]
        download_attachments: bool,
        depth: int,
    ) -> None:
        """Recursively build folders for a work item node."""
        item = node.item

        # Build folder name based on type
        if item.work_item_type == "User Story":
            folder_name = sanitize_path(f"{item.id} - {item.title}")
        else:
            folder_name = sanitize_path(f"{item.id} - {item.title}")

        node_dir = parent_path / folder_name
        node_dir.mkdir(parents=True, exist_ok=True)

        # Create references dir
        refs_dir = node_dir / "references"
        refs_dir.mkdir(exist_ok=True)

        # Determine summary filename based on type
        type_label = item.work_item_type.replace(" ", "_")
        summary_name = f"{type_label}_Summary.md"
        summary_path = node_dir / summary_name

        # Write summary .md
        summary_content = _render_summary(item)
        summary_path.write_text(summary_content, encoding="utf-8")

        # Set up paths for stories (feature file + prompt)
        prompt_path = None
        feature_path = None
        if item.work_item_type == "User Story":
            feature_name = f"US{item.id} - {sanitize_path(item.title)}.feature"
            feature_path = node_dir / feature_name
            prompt_path = node_dir / "scenario_prompt.md"

        # Register in manifest
        manifest.items[item.id] = WorkspacePaths(
            root=node_dir,
            summary_md=summary_path,
            references_dir=refs_dir,
            prompt_path=prompt_path,
            feature_path=feature_path,
        )

        # Download attachments
        if download_attachments and item.attachments:
            for attachment in item.attachments:
                dest = refs_dir / sanitize_path(attachment.name)
                try:
                    await ado.download_attachment(attachment.url, dest)
                    attachment.local_path = dest
                    console.print(f"  [dim]Downloaded: {attachment.name}[/dim]")
                except Exception as e:
                    console.print(f"  [yellow]Failed to download {attachment.name}: {e}[/yellow]")

        # Determine child container folder name
        child_container = _get_child_container_name(item.work_item_type)

        # Recurse into children
        if node.children:
            if child_container:
                child_parent = node_dir / child_container
            else:
                child_parent = node_dir

            for child in node.children:
                await self._build_node(
                    node=child,
                    parent_path=child_parent,
                    manifest=manifest,
                    ado=ado,
                    download_attachments=download_attachments,
                    depth=depth + 1,
                )


def _get_child_container_name(work_item_type: str) -> str | None:
    """Get the container folder name for children of a given type."""
    containers = {
        "Epic": "Features",
        "Feature": None,  # Stories go directly under feature
    }
    return containers.get(work_item_type)


def _render_summary(item: WorkItem) -> str:
    """Render a markdown summary for a work item."""
    lines = [
        f"# {item.work_item_type}: {item.id} - {item.title}",
        "",
        f"**Type:** {item.work_item_type}",
        f"**ID:** {item.id}",
        f"**State:** {item.state}",
    ]

    if item.tags:
        lines.append(f"**Tags:** {', '.join(item.tags)}")

    # Area and iteration paths from fields
    area_path = item.fields.get("System.AreaPath", "")
    iteration_path = item.fields.get("System.IterationPath", "")
    if area_path:
        lines.append(f"**Area Path:** {area_path}")
    if iteration_path:
        lines.append(f"**Iteration Path:** {iteration_path}")

    lines.append("")

    if item.description:
        lines.extend(["## Description", "", item.description, ""])

    if item.acceptance_criteria:
        lines.extend(["## Acceptance Criteria", "", item.acceptance_criteria, ""])

    # Include other notable fields
    skip_fields = {
        "System.Title",
        "System.Description",
        "System.WorkItemType",
        "System.State",
        "System.Tags",
        "System.AreaPath",
        "System.IterationPath",
        "Microsoft.VSTS.Common.AcceptanceCriteria",
    }

    other_fields = {
        k: v
        for k, v in item.fields.items()
        if k not in skip_fields and v and not k.startswith("System.") or k in {
            "System.AssignedTo",
            "System.CreatedDate",
            "System.ChangedDate",
        }
    }

    if other_fields:
        lines.extend(["## Additional Fields", ""])
        for key, value in sorted(other_fields.items()):
            display_key = key.split(".")[-1]
            if isinstance(value, dict):
                # Handle identity fields like AssignedTo
                display_value = value.get("displayName", str(value))
            else:
                display_value = str(value)
            lines.append(f"- **{display_key}:** {display_value}")
        lines.append("")

    if item.attachments:
        lines.extend(["## Attachments", ""])
        for att in item.attachments:
            lines.append(f"- [{att.name}](references/{sanitize_path(att.name)})")
        lines.append("")

    return "\n".join(lines)


def copy_to_target_repo(manifest: WorkspaceManifest, target_repo_path: Path) -> int:
    """Copy generated .feature files from workspace to the target repo.

    Returns the number of files copied.
    """
    copied = 0
    for item_id, paths in manifest.items.items():
        if not paths.feature_path or not paths.feature_path.exists():
            continue
        if paths.feature_path.stat().st_size == 0:
            continue

        # Reconstruct relative path from workspace root
        rel_path = paths.feature_path.relative_to(manifest.root)
        dest = target_repo_path / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(paths.feature_path, dest)
        copied += 1
        console.print(f"  [green]Copied:[/green] {rel_path}")

    return copied
