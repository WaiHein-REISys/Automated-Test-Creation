"""Parse Azure DevOps URLs to extract org, project, and work item ID."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from atc.core.models import AdoTarget


def parse_ado_url(url: str) -> AdoTarget:
    """Parse an ADO URL and extract org, project, and work item ID.

    Supported formats:
        https://dev.azure.com/{org}/{project}/_workitems/edit/{id}
        https://dev.azure.com/{org}/{project}/_backlogs/backlog/{team}/Epics/?workitem={id}
        https://{org}.visualstudio.com/{project}/_workitems/edit/{id}
        https://dev.azure.com/{org}/{project}/_queries/query/{guid}/?workitem={id}
    """
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    path_parts = [p for p in parsed.path.strip("/").split("/") if p]

    # Format: https://dev.azure.com/{org}/{project}/...
    if "dev.azure.com" in hostname:
        if len(path_parts) < 2:
            raise ValueError(f"Cannot parse ADO URL: not enough path segments in {url}")
        org = path_parts[0]
        project = path_parts[1]
        org_url = f"https://dev.azure.com/{org}"
        work_item_id = _extract_work_item_id(url, path_parts, parsed.query)

    # Format: https://{org}.visualstudio.com/{project}/...
    elif "visualstudio.com" in hostname:
        org = hostname.split(".")[0]
        if len(path_parts) < 1:
            raise ValueError(f"Cannot parse ADO URL: no project in path for {url}")
        project = path_parts[0]
        org_url = f"https://dev.azure.com/{org}"
        work_item_id = _extract_work_item_id(url, path_parts, parsed.query)

    else:
        raise ValueError(
            f"Unrecognized ADO URL format: {url}. "
            "Expected https://dev.azure.com/... or https://{{org}}.visualstudio.com/..."
        )

    return AdoTarget(
        org=org,
        org_url=org_url,
        project=project,
        work_item_id=work_item_id,
    )


def _extract_work_item_id(url: str, path_parts: list[str], query: str) -> int:
    """Extract work item ID from URL path or query parameters."""
    # Try path: .../_workitems/edit/{id}
    for i, part in enumerate(path_parts):
        if part == "edit" and i + 1 < len(path_parts):
            try:
                return int(path_parts[i + 1])
            except ValueError:
                pass

    # Try query: ?workitem={id}
    if query:
        match = re.search(r"workitem=(\d+)", query)
        if match:
            return int(match.group(1))

    # Try: last numeric segment in path
    for part in reversed(path_parts):
        try:
            return int(part)
        except ValueError:
            continue

    raise ValueError(f"Cannot extract work item ID from URL: {url}")
