"""Domain models for ADO work items and tree structures."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Attachment:
    """An attachment on an ADO work item."""

    name: str
    url: str
    local_path: Path | None = None


@dataclass
class Relation:
    """A link/relation on an ADO work item."""

    rel: str
    url: str
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkItem:
    """A single ADO work item (Epic, Feature, User Story, etc.)."""

    id: int
    title: str
    work_item_type: str
    description: str = ""
    acceptance_criteria: str = ""
    state: str = ""
    tags: list[str] = field(default_factory=list)
    fields: dict[str, Any] = field(default_factory=dict)
    relations: list[Relation] = field(default_factory=list)
    attachments: list[Attachment] = field(default_factory=list)


@dataclass
class WorkItemNode:
    """A node in the work item hierarchy tree (recursive)."""

    item: WorkItem
    children: list[WorkItemNode] = field(default_factory=list)

    @property
    def id(self) -> int:
        return self.item.id

    @property
    def title(self) -> str:
        return self.item.title

    @property
    def work_item_type(self) -> str:
        return self.item.work_item_type

    def walk(self) -> list[WorkItemNode]:
        """Yield all nodes in the tree (BFS)."""
        result: list[WorkItemNode] = []
        queue = [self]
        while queue:
            node = queue.pop(0)
            result.append(node)
            queue.extend(node.children)
        return result

    def find_by_type(self, work_item_type: str) -> list[WorkItemNode]:
        """Find all nodes of a given type in the tree."""
        return [n for n in self.walk() if n.work_item_type == work_item_type]


@dataclass
class AdoTarget:
    """Parsed ADO URL target."""

    org: str
    org_url: str
    project: str
    work_item_id: int


@dataclass
class PromptBundle:
    """Multi-stage prompt: system (generic + tailored) + user (story-specific).

    system_message: Generic SpecFlow rules + product-specific context.
                    Sent as the system/developer message to the LLM.
    user_message:   The actual user story content to generate from.
                    Sent as the user message to the LLM.
    """

    system_message: str
    user_message: str

    @property
    def combined(self) -> str:
        """Fallback: merge both parts for providers that only accept a single prompt."""
        return f"{self.system_message}\n\n---\n\n{self.user_message}"


@dataclass
class WorkspacePaths:
    """Paths for a single work item in the workspace."""

    root: Path
    summary_md: Path
    references_dir: Path
    prompt_path: Path | None = None
    feature_path: Path | None = None


@dataclass
class WorkspaceManifest:
    """Maps work item IDs to their workspace paths."""

    root: Path
    items: dict[int, WorkspacePaths] = field(default_factory=dict)

    def get_paths(self, work_item_id: int) -> WorkspacePaths | None:
        return self.items.get(work_item_id)
