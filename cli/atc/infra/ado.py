"""Azure DevOps REST API client."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import httpx
from markdownify import markdownify as md

from atc.core.models import Attachment, Relation, WorkItem, WorkItemNode


class AdoClient:
    """Async client for Azure DevOps REST API."""

    API_VERSION = "7.1"

    def __init__(self, org_url: str, project: str, pat: str) -> None:
        self.org_url = org_url.rstrip("/")
        self.project = project
        token = base64.b64encode(f":{pat}".encode()).decode()
        self._client = httpx.AsyncClient(
            base_url=f"{self.org_url}/{project}/_apis",
            headers={"Authorization": f"Basic {token}"},
            timeout=30.0,
        )

    @classmethod
    def from_url(cls, url: str, pat: str) -> "AdoClient":
        from atc.infra.ado_url import parse_ado_url

        target = parse_ado_url(url)
        return cls(target.org_url, target.project, pat)

    async def __aenter__(self) -> "AdoClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self._client.aclose()

    async def get_work_item(self, work_item_id: int) -> WorkItem:
        """Fetch a single work item with all fields and relations."""
        resp = await self._client.get(
            f"/wit/workitems/{work_item_id}",
            params={"$expand": "all", "api-version": self.API_VERSION},
        )
        resp.raise_for_status()
        data = resp.json()
        return self._parse_work_item(data)

    async def get_work_items_batch(self, ids: list[int]) -> list[WorkItem]:
        """Fetch multiple work items in batches of 200."""
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

    async def get_tree(self, root_id: int) -> WorkItemNode:
        """Recursively fetch the full work item hierarchy."""
        root_item = await self.get_work_item(root_id)
        root_node = WorkItemNode(item=root_item)
        await self._build_tree(root_node)
        return root_node

    async def _build_tree(self, node: WorkItemNode) -> None:
        """Recursively populate children for a node."""
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
            child_node = WorkItemNode(item=child_item)
            node.children.append(child_node)
            await self._build_tree(child_node)

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
