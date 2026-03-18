"""Parse Azure DevOps URLs to extract org, project, and work item ID."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from atc.core.models import AdoTarget


def parse_ado_url(url: str) -> AdoTarget:
    """Parse an ADO URL and extract org, project, and work item ID.

    Supported formats:
        https://dev.azure.com/{org}/{project}/_workitems/edit/{id}
        https://dev.azure.com/{org}/{project}/_backlogs/backlog/{team}/Epics/?workitem={id}
        https://{org}.visualstudio.com/{project}/_workitems/edit/{id}
        https://dev.azure.com/{org}/{project}/_queries/query/{guid}/?workitem={id}
        https://{server}/{path}/{collection}/{project}/_workitems/edit/{id}  (on-prem ADS)
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

    # On-premises Azure DevOps Server (ADS):
    # https://{server}/{vdir}/{collection}/{project}/_workitems/edit/{id}
    else:
        org, org_url, project = _parse_on_prem_ads_url(url, parsed, path_parts)
        work_item_id = _extract_work_item_id(url, path_parts, parsed.query)

    return AdoTarget(
        org=org,
        org_url=org_url,
        project=project,
        work_item_id=work_item_id,
    )


_ADO_PATH_MARKERS = {"_workitems", "_backlogs", "_queries", "_apis"}


def _parse_on_prem_ads_url(
    url: str, parsed: Any, path_parts: list[str]
) -> tuple[str, str, str]:
    """Extract (org, org_url, project) from an on-premises ADS URL.

    Assumes the URL contains a known ADO path marker (e.g. ``_workitems``).
    The segment immediately before the marker is the project, and everything
    before that is the collection/org base URL.

    Example:
        https://ehbads.hrsa.gov/ads/EHBs/EHBs/_workitems/edit/411599
          -> org="EHBs", org_url="https://ehbads.hrsa.gov/ads/EHBs", project="EHBs"
    """
    marker_idx: int | None = None
    for i, part in enumerate(path_parts):
        if part in _ADO_PATH_MARKERS:
            marker_idx = i
            break

    if marker_idx is None or marker_idx < 2:
        raise ValueError(
            f"Cannot parse on-premises ADS URL: {url}. "
            "Expected at least a collection and project segment before "
            "an ADO path marker (e.g. _workitems)."
        )

    project = path_parts[marker_idx - 1]
    org = path_parts[marker_idx - 2]  # collection name
    # org_url = scheme://host + path segments up to (but not including) the project
    prefix_parts = path_parts[: marker_idx - 1]
    org_url = f"{parsed.scheme}://{parsed.hostname}"
    if parsed.port and parsed.port not in (80, 443):
        org_url += f":{parsed.port}"
    if prefix_parts:
        org_url += "/" + "/".join(prefix_parts)

    return org, org_url, project


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
