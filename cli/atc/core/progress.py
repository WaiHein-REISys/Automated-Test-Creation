"""Progress reporting protocol for pipeline execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol


class Phase(Enum):
    """Pipeline execution phases."""

    PARSE_URL = "parse_url"
    FETCH_HIERARCHY = "fetch_hierarchy"
    BUILD_WORKSPACE = "build_workspace"
    RENDER_PROMPTS = "render_prompts"
    GENERATE_FEATURES = "generate_features"
    COPY_TO_REPO = "copy_to_repo"
    GIT_OPERATIONS = "git_operations"
    RUN_TESTS = "run_tests"

    @property
    def label(self) -> str:
        return {
            "parse_url": "Parse URL",
            "fetch_hierarchy": "Fetch Hierarchy",
            "build_workspace": "Build Workspace",
            "render_prompts": "Render Prompts",
            "generate_features": "Generate Features",
            "copy_to_repo": "Copy to Repo",
            "git_operations": "Git Operations",
            "run_tests": "Run Tests",
        }[self.value]


@dataclass
class ProgressEvent:
    """A single progress event emitted by the executor."""

    phase: Phase
    message: str
    current: int = 0
    total: int = 0
    level: str = "info"  # info, warning, error, success


@dataclass
class TestExecutionResult:
    """Summary of a test execution run (EHB Test Runner)."""

    executed: bool = False
    exit_code: int = -1
    total: int = 0
    passed: int = 0
    failed: int = 0
    outcome: str = "NotRun"
    trx_path: str = ""
    extent_report: str = ""
    failed_tests: list[dict] = field(default_factory=list)


@dataclass
class PipelineResult:
    """Summary of a pipeline run."""

    generated: int = 0
    failed: int = 0
    skipped: int = 0
    total: int = 0
    workspace_root: str = ""
    events: list[ProgressEvent] = field(default_factory=list)
    test_result: TestExecutionResult = field(default_factory=TestExecutionResult)


class ProgressReporter(Protocol):
    """Protocol for receiving pipeline progress events."""

    async def report(self, event: ProgressEvent) -> None: ...

    async def phase_start(self, phase: Phase, message: str) -> None: ...

    async def phase_end(self, phase: Phase, message: str) -> None: ...

    async def item_progress(
        self, phase: Phase, current: int, total: int, message: str
    ) -> None: ...
