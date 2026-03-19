"""Reusable UI components."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FeatureFileInfo:
    """Parsed metadata from a single .feature file."""

    path: Path
    name: str  # Feature name from the Feature: line
    scenario_count: int = 0
    tags: list[str] = field(default_factory=list)
    lines: int = 0
    size_bytes: int = 0
    parent_folder: str = ""  # e.g. "PBI21273"


@dataclass
class WorkspaceMetrics:
    """Aggregated metrics from a workspace scan."""

    total_files: int = 0
    feature_files: int = 0
    prompt_files: int = 0
    summary_files: int = 0
    total_scenarios: int = 0
    total_tags: dict[str, int] = field(default_factory=dict)  # tag → count
    features: list[FeatureFileInfo] = field(default_factory=list)
    scenarios_by_folder: dict[str, int] = field(default_factory=dict)  # folder → count
    file_types: dict[str, int] = field(default_factory=dict)  # ext → count


def scan_workspace(root: Path) -> WorkspaceMetrics:
    """Scan a workspace directory and return structured metrics."""
    metrics = WorkspaceMetrics()

    if not root.exists():
        return metrics

    all_files = [f for f in root.rglob("*") if f.is_file() and not f.name.startswith(".")]
    metrics.total_files = len(all_files)

    # Count by extension
    for f in all_files:
        ext = f.suffix.lower()
        metrics.file_types[ext] = metrics.file_types.get(ext, 0) + 1

    # Prompts and summaries
    metrics.prompt_files = len([f for f in all_files if "prompt" in f.name.lower() and f.suffix == ".md"])
    metrics.summary_files = len([f for f in all_files if "summary" in f.name.lower() and f.suffix == ".md"])

    # Parse .feature files
    feature_paths = [f for f in all_files if f.suffix == ".feature"]
    metrics.feature_files = len(feature_paths)

    for fp in feature_paths:
        info = _parse_feature_file(fp, root)
        metrics.features.append(info)
        metrics.total_scenarios += info.scenario_count
        for tag in info.tags:
            metrics.total_tags[tag] = metrics.total_tags.get(tag, 0) + 1
        if info.parent_folder:
            metrics.scenarios_by_folder[info.parent_folder] = (
                metrics.scenarios_by_folder.get(info.parent_folder, 0) + info.scenario_count
            )

    return metrics


def _parse_feature_file(path: Path, root: Path) -> FeatureFileInfo:
    """Parse a .feature file for metadata."""
    name = path.stem
    scenario_count = 0
    tags: list[str] = []
    lines = 0

    try:
        content = path.read_text(encoding="utf-8")
        lines = content.count("\n") + 1

        # Extract Feature name
        feature_match = re.search(r"^\s*Feature:\s*(.+)$", content, re.MULTILINE)
        if feature_match:
            name = feature_match.group(1).strip()

        # Count scenarios (Scenario: and Scenario Outline:)
        scenario_count = len(re.findall(r"^\s*Scenario(?:\s+Outline)?:", content, re.MULTILINE))

        # Extract tags (@Something)
        found_tags = re.findall(r"@(\w+)", content)
        tags = sorted(set(found_tags))

    except Exception:
        pass

    # Determine parent folder relative to workspace root
    try:
        rel = path.relative_to(root)
        parts = rel.parts
        parent_folder = parts[0] if len(parts) > 1 else ""
    except ValueError:
        parent_folder = ""

    return FeatureFileInfo(
        path=path,
        name=name,
        scenario_count=scenario_count,
        tags=tags,
        lines=lines,
        size_bytes=path.stat().st_size if path.exists() else 0,
        parent_folder=parent_folder,
    )
