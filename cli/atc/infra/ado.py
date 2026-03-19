"""Azure DevOps REST API client."""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Any

import httpx
from markdownify import markdownify as md

from atc.core.models import Attachment, Relation, WorkItem, WorkItemNode

logger = logging.getLogger(__name__)

# Versions to probe in order (newest first) when ado_api_version="auto"
_PROBE_VERSIONS = ("7.1", "7.0", "6.0")


def _has_matching_tag(item: WorkItem, filter_tags: set[str]) -> bool:
    """Return True if the work item has at least one tag in *filter_tags*.

    Comparison is case-insensitive (*filter_tags* must already be lowercased).
    """
    return any(t.lower() in filter_tags for t in item.tags)


class AdoClient:
    """Async client for Azure DevOps REST API."""

    API_VERSION = "7.1"  # default; overridden by ``api_version`` param or auto-probe

    def __init__(
        self,
        org_url: str,
        project: str,
        pat: str,
        *,
        api_version: str = "auto",
    ) -> None:
        self.org_url = org_url.rstrip("/")
        self.project = project
        self._requested_api_version = api_version
        self._api_version_resolved = False
        token = base64.b64encode(f":{pat}".encode()).decode()
        self._client = httpx.AsyncClient(
            base_url=f"{self.org_url}/{project}/_apis",
            headers={"Authorization": f"Basic {token}"},
            timeout=30.0,
        )

        # If an explicit version was given (not "auto"), use it immediately.
        if api_version.lower() != "auto":
            self.API_VERSION = api_version
            self._api_version_resolved = True

    @classmethod
    def from_url(
        cls,
        url: str,
        pat: str,
        *,
        api_version: str = "auto",
    ) -> "AdoClient":
        from atc.infra.ado_url import parse_ado_url

        target = parse_ado_url(url)
        return cls(target.org_url, target.project, pat, api_version=api_version)

    # ------------------------------------------------------------------
    # Auto-probe: detect the best API version the server supports
    # ------------------------------------------------------------------

    async def _ensure_api_version(self) -> None:
        """Probe the server for its supported API version (once)."""
        if self._api_version_resolved:
            return

        for version in _PROBE_VERSIONS:
            try:
                resp = await self._client.get(
                    "/wit/workitemtypes",
                    params={"api-version": version, "$top": 1},
                )
                if resp.status_code < 400:
                    self.API_VERSION = version
                    self._api_version_resolved = True
                    logger.info("ADO server supports API version %s", version)
                    return

                # Check for the specific "version out of range" error
                body = resp.text
                if "VssVersionOutOfRangeException" in body:
                    logger.debug(
                        "ADO server rejected API version %s — trying older version",
                        version,
                    )
                    continue

                # Some other 4xx/5xx — might be auth related; stop probing
                # and fall through to the default to surface a clear error later
                logger.warning(
                    "Unexpected %s response during API version probe with v%s",
                    resp.status_code,
                    version,
                )
                break
            except httpx.HTTPError as exc:
                logger.warning(
                    "HTTP error during API version probe with v%s: %s", version, exc
                )
                break

        # If no version succeeded, fall back to the lowest we tried
        self.API_VERSION = _PROBE_VERSIONS[-1]
        self._api_version_resolved = True
        logger.warning(
            "Could not auto-detect ADO API version; falling back to %s",
            self.API_VERSION,
        )

    async def __aenter__(self) -> "AdoClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self._client.aclose()

    async def get_work_item(self, work_item_id: int) -> WorkItem:
        """Fetch a single work item with all fields and relations."""
        await self._ensure_api_version()
        resp = await self._client.get(
            f"/wit/workitems/{work_item_id}",
            params={"$expand": "all", "api-version": self.API_VERSION},
        )
        resp.raise_for_status()
        data = resp.json()
        return self._parse_work_item(data)

    async def get_work_items_batch(self, ids: list[int]) -> list[WorkItem]:
        """Fetch multiple work items in batches of 200."""
        await self._ensure_api_version()
        results: list[WorkItem] = []
        for i in range(0, len(ids), 200):
            chunk = ids[i : i + 200]
            id_str = ",".join(str(x) for x in chunk)
            resp = await self._client.get(
                "/wit/workitems",
                params={
                    "ids": id_str,
                    "$expand": "all",
                    "api-version": self.API_VERSION,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            for item_data in data.get("value", []):
                results.append(self._parse_work_item(item_data))
        return results

    async def get_children_ids(self, work_item_id: int) -> list[int]:
        """Get child work item IDs from a parent's relations."""
        item = await self.get_work_item(work_item_id)
        child_ids: list[int] = []
        for rel in item.relations:
            if rel.rel == "System.LinkTypes.Hierarchy-Forward":
                # URL ends with the child work item ID
                try:
                    child_id = int(rel.url.rstrip("/").split("/")[-1])
                    child_ids.append(child_id)
                except ValueError:
                    pass
        return child_ids

    async def get_tree(
        self,
        root_id: int,
        *,
        max_depth: int = 0,
        filter_tags: list[str] | None = None,
    ) -> WorkItemNode:
        """Recursively fetch the work item hierarchy.

        Args:
            root_id: The root work item ID.
            max_depth: Maximum levels below the root to fetch.
                ``0`` means unlimited (full tree).
                ``1`` fetches the root and its direct children only.
                ``2`` fetches root → children → grandchildren, etc.
            filter_tags: If non-empty, only include child work items that have
                at least one of these tags (case-insensitive). The root item
                is always included regardless of tags.
        """
        root_item = await self.get_work_item(root_id)
        root_node = WorkItemNode(item=root_item)
        # Normalize filter tags to lowercase for case-insensitive matching
        normalized_tags = {t.lower() for t in filter_tags} if filter_tags else set()
        await self._build_tree(
            root_node,
            current_depth=1,
            max_depth=max_depth,
            filter_tags=normalized_tags,
        )
        return root_node

    async def _build_tree(
        self,
        node: WorkItemNode,
        *,
        current_depth: int = 1,
        max_depth: int = 0,
        filter_tags: set[str] | None = None,
    ) -> None:
        """Recursively populate children for a node.

        Args:
            node: The parent node to expand.
            current_depth: How many levels deep we are (root's children = 1).
            max_depth: Stop expanding beyond this depth. ``0`` = unlimited.
            filter_tags: If non-empty, only include children that have at least
                one of these tags (already lowercased).
        """
        # Respect depth limit
        if max_depth and current_depth > max_depth:
            return

        child_ids: list[int] = []
        for rel in node.item.relations:
            if rel.rel == "System.LinkTypes.Hierarchy-Forward":
                try:
                    child_id = int(rel.url.rstrip("/").split("/")[-1])
                    child_ids.append(child_id)
                except ValueError:
                    pass

        if not child_ids:
            return

        children = await self.get_work_items_batch(child_ids)
        for child_item in children:
            # Apply tag filter: skip children that don't match any required tag
            if filter_tags and not _has_matching_tag(child_item, filter_tags):
                logger.debug(
                    "Skipping work item #%d (%s) — tags %s don't match filter %s",
                    child_item.id,
                    child_item.title,
                    child_item.tags,
                    filter_tags,
                )
                continue

            child_node = WorkItemNode(item=child_item)
            node.children.append(child_node)
            await self._build_tree(
                child_node,
                current_depth=current_depth + 1,
                max_depth=max_depth,
                filter_tags=filter_tags,
            )

    # ------------------------------------------------------------------
    # Download helpers
    # ------------------------------------------------------------------

    async def download_attachment(self, url: str, dest: Path) -> Path:
        """Download an attachment to a local path."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        # Attachment URLs from ADO include auth in the relation, but we add PAT header
        resp = await self._client.get(url, follow_redirects=True)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        return dest

    def _parse_work_item(self, data: dict[str, Any]) -> WorkItem:
        """Parse ADO REST API response into a WorkItem."""
        fields = data.get("fields", {})

        # Extract and convert HTML fields to markdown
        description_html = fields.get("System.Description", "") or ""
        ac_html = fields.get("Microsoft.VSTS.Common.AcceptanceCriteria", "") or ""

        description = md(description_html).strip() if description_html else ""
        acceptance_criteria = md(ac_html).strip() if ac_html else ""

        # Parse tags
        tags_str = fields.get("System.Tags", "") or ""
        tags = [t.strip() for t in tags_str.split(";") if t.strip()]

        # Parse relations
        relations: list[Relation] = []
        attachments: list[Attachment] = []

        for rel_data in data.get("relations", []) or []:
            rel = Relation(
                rel=rel_data.get("rel", ""),
                url=rel_data.get("url", ""),
                attributes=rel_data.get("attributes", {}),
            )
            relations.append(rel)

            if rel.rel == "AttachedFile":
                name = rel.attributes.get("name", rel.url.split("/")[-1])
                attachments.append(Attachment(name=name, url=rel.url))

        return WorkItem(
            id=data.get("id", 0),
            title=fields.get("System.Title", ""),
            work_item_type=fields.get("System.WorkItemType", ""),
            description=description,
            acceptance_criteria=acceptance_criteria,
            state=fields.get("System.State", ""),
            tags=tags,
            fields=fields,
            relations=relations,
            attachments=attachments,
        )
