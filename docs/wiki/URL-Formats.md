# URL Formats

ATC auto-detects the Azure DevOps organization, project, and work item ID from the URL. No manual org/project configuration is needed.

## Supported formats

### Azure DevOps Services (cloud)

```
https://dev.azure.com/{org}/{project}/_workitems/edit/{id}
https://dev.azure.com/{org}/{project}/_backlogs/backlog/{team}/Epics/?workitem={id}
https://dev.azure.com/{org}/{project}/_queries/query/{guid}/?workitem={id}
```

### Visual Studio Online (legacy cloud)

```
https://{org}.visualstudio.com/{project}/_workitems/edit/{id}
```

### Azure DevOps Server — on-premises (ADS)

```
https://{server}/{virtual_dir}/{collection}/{project}/_workitems/edit/{id}
```

**Example:**
```
https://ehbads.hrsa.gov/ads/EHBs/EHBs/_workitems/edit/411599
```

Parsed as:

| Field | Value |
|-------|-------|
| `org` | `EHBs` (collection name) |
| `org_url` | `https://ehbads.hrsa.gov/ads/EHBs` |
| `project` | `EHBs` |
| `work_item_id` | `411599` |

## How on-prem URL detection works

The parser (`cli/atc/infra/ado_url.py`) uses a priority-based approach:

1. **`dev.azure.com`** — matched by hostname. First two path segments are org and project.
2. **`*.visualstudio.com`** — matched by hostname. Org is extracted from the subdomain.
3. **Everything else** — treated as on-prem ADS. The parser scans path segments for ADO markers (`_workitems`, `_backlogs`, `_queries`, `_apis`). The segment immediately before the marker is the **project**, the one before that is the **collection** (org), and the preceding segments form the **org base URL**.

### Path marker detection

The parser recognizes these ADO path markers:

- `_workitems` — work item edit/view pages
- `_backlogs` — backlog boards
- `_queries` — saved queries
- `_apis` — REST API endpoints

Any URL containing one of these markers with at least two preceding path segments (collection + project) is accepted as an on-prem ADS URL.

### API URL construction

For the example `https://ehbads.hrsa.gov/ads/EHBs/EHBs/_workitems/edit/411599`:

```
org_url  = https://ehbads.hrsa.gov/ads/EHBs
project  = EHBs
base_url = {org_url}/{project}/_apis = https://ehbads.hrsa.gov/ads/EHBs/EHBs/_apis
```

This matches the Azure DevOps Server REST API convention: `{server}/{virtual_dir}/{collection}/{project}/_apis/...`

### Custom ports

If your on-prem ADS uses a non-standard port (not 80 or 443), include it in the URL:

```
https://myserver.example.com:8443/ads/DefaultCollection/MyProject/_workitems/edit/100
```

The port is preserved in `org_url`.

## Work item ID extraction

The work item ID is extracted using these strategies (in order):

1. **Path match:** `.../_workitems/edit/{id}` — most common
2. **Query parameter:** `?workitem={id}` — used in backlog and query URLs
3. **Last numeric path segment** — fallback for unusual URL formats

## Adding a new URL format

To support a new URL pattern:

1. Edit `cli/atc/infra/ado_url.py`
2. Add a new `elif` branch in `parse_ado_url()` before the on-prem fallback, or add a new marker to `_ADO_PATH_MARKERS`
3. Return an `AdoTarget(org, org_url, project, work_item_id)`
4. The `AdoClient` constructs its base URL as `{org_url}/{project}/_apis`, so ensure `org_url` points to the collection root

## Future enhancements

- Support for `/_boards/` URL format
- Automatic detection of API version supported by the server
- Collection-level queries (WIQL) for batch work item discovery
