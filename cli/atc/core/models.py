"""Domain models for ADO work items and tree structures."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Feature-generatable story detection
# ---------------------------------------------------------------------------
# A user story is considered "feature-generatable" when its combined text
# (description + acceptance criteria) identifies three things:
#   1. The **user / actor** — who benefits
#   2. The **goal / action** — what they want to do
#   3. The **benefit / purpose** — why it matters
#
# We detect each component via lightweight regex patterns that cover the
# most common phrasing conventions in ADO user stories (including HTML-
# wrapped content from the rich-text editor).

# Strip HTML tags so content inside <div>/<p>/etc. is treated as plain text.
_HTML_TAG = re.compile(r"<[^>]+>")

# 1. User / actor
_USER_PATTERNS = re.compile(
    r"(?:^|[\s>])"
    r"(?:as\s+an?\b|user|actor|role|persona|stakeholder|administrator|admin|customer|applicant|reviewer|grantee)",
    re.IGNORECASE | re.MULTILINE,
)

# 2. Goal / action
_GOAL_PATTERNS = re.compile(
    r"(?:^|[\s>])"
    r"(?:I\s+want|I\s+need|I\s+should|should\s+be\s+able|able\s+to|can\s+(?:view|create|edit|delete|submit|manage|access|update|search|filter|select|navigate|upload|download|approve|reject|configure|enter|verify|validate))",
    re.IGNORECASE | re.MULTILINE,
)

# 3. Benefit / purpose
_BENEFIT_PATTERNS = re.compile(
    r"(?:^|[\s>])"
    r"(?:so\s+that|in\s+order\s+to|to\s+ensure|to\s+allow|to\s+enable|to\s+provide|to\s+support|to\s+reduce|to\s+improve|to\s+verify|to\s+prevent|to\s+streamline|benefit|value|purpose|outcome)",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass
class StoryCompletenessResult:
    """Result of checking whether a work item is feature-generatable."""

    has_user: bool
    has_goal: bool
    has_benefit: bool

    @property
    def is_generatable(self) -> bool:
        return self.has_user and self.has_goal and self.has_benefit

    @property
    def missing(self) -> list[str]:
        parts: list[str] = []
        if not self.has_user:
            parts.append("user/actor")
        if not self.has_goal:
            parts.append("goal/action")
        if not self.has_benefit:
            parts.append("benefit/purpose")
        return parts


def check_story_completeness(
    description: str,
    acceptance_criteria: str,
    *,
    has_attachments: bool = False,
) -> StoryCompletenessResult:
    """Check whether a work item has enough context to generate a feature file.

    Examines the combined *description* and *acceptance_criteria* for three
    elements: a user/actor, a goal/action, and a benefit/purpose.

    *has_attachments* is noted but does **not** substitute for missing
    textual elements — attachments alone cannot define the story structure.
    """
    # Merge and strip HTML so rich-text content is searchable.
    combined = f"{description}\n{acceptance_criteria}"
    combined = _HTML_TAG.sub(" ", combined)

    return StoryCompletenessResult(
        has_user=bool(_USER_PATTERNS.search(combined)),
        has_goal=bool(_GOAL_PATTERNS.search(combined)),
        has_benefit=bool(_BENEFIT_PATTERNS.search(combined)),
    )


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
