# Architecture

This page describes ATC's project structure, pipeline execution flow, domain models, and extension points.

## Technology stack

| Layer | Technology |
|-------|-----------|
| CLI framework | **Typer** with **Rich** terminal output |
| Configuration | **Pydantic** v2 models + **Pydantic Settings** (`.env` support) |
| HTTP client | **httpx** (async) for Azure DevOps REST API |
| Templates | **Jinja2** for prompt rendering |
| HTML conversion | **markdownify** (ADO HTML fields → Markdown) |
| AI providers | **Anthropic SDK**, **OpenAI SDK**, **Ollama** HTTP, subprocess CLI |
| Packaging | **hatchling** build backend, **uv** or **pip** |
| Testing | **pytest** + **pytest-asyncio** |
| Linting | **Ruff** + **mypy** |
| Python | 3.12 or 3.13 |

## Project structure

```
Automated-Test-Creation/
├── agent.md                        ← centralized AI agent instructions
├── CLAUDE.md                       ← points to agent.md
├── .windsurfrules                  ← Windsurf Cascade workflow rules
├── setup-atc.ps1                   ← PowerShell one-shot setup (repo root)
├── README.md
├── docs/
│   ├── wiki/                       ← this wiki
│   ├── Automated_Test_Creation_CLI_Design.md
│   ├── Automated_Test_Creation_Technical_Plan.md
│   └── Automated_Test_Creation_Tool_Design.md
│
└── cli/                            ← main application
    ├── pyproject.toml              ← dependencies and build config
    ├── setup_env.py                ← cross-platform setup script
    ├── run_atc.sh / .ps1 / .cmd   ← platform run wrappers
    ├── run_full.sh / .ps1          ← one-shot convenience wrappers
    ├── .env                        ← credentials (not committed)
    │
    ├── atc/                        ← Python package
    │   ├── __init__.py             ← version
    │   ├── __main__.py             ← python -m atc entry point
    │   ├── main.py                 ← Typer CLI: run, validate, init
    │   ├── executor.py             ← pipeline orchestrator
    │   │
    │   ├── core/
    │   │   └── models.py           ← domain models (WorkItem, AdoTarget, etc.)
    │   │
    │   ├── infra/
    │   │   ├── ado.py              ← AdoClient (async REST API)
    │   │   ├── ado_url.py          ← URL parser (cloud + on-prem ADS)
    │   │   ├── config.py           ← RunConfig, ProviderConfig, RunOptions
    │   │   ├── settings.py         ← AtcSettings (env vars via Pydantic)
    │   │   ├── workspace.py        ← WorkspaceBuilder (folder structure)
    │   │   ├── prompts.py          ← PromptRenderer (Jinja2)
    │   │   └── git.py              ← GitClient (subprocess, cross-platform)
    │   │
    │   ├── providers/
    │   │   ├── __init__.py         ← create_provider() factory
    │   │   ├── base.py             ← GenerationProvider abstract class
    │   │   ├── claude.py           ← Anthropic Claude (vision support)
    │   │   ├── azure_openai.py     ← Azure OpenAI (vision support)
    │   │   ├── ollama.py           ← Local Ollama
    │   │   ├── cli_agent.py        ← External CLI command
    │   │   └── prompt_only.py      ← Manual mode (no AI call)
    │   │
    │   └── output/
    │       └── console.py          ← Rich console helpers
    │
    ├── configs/
    │   ├── prompts/                ← Jinja2 templates
    │   ├── reference/              ← Instructions.txt, Common_Steps.txt, Background_Steps.txt
    │   └── runs/                   ← example.json
    │
    └── tests/
        └── conftest.py             ← pytest fixtures
```

## Pipeline phases

The pipeline is orchestrated by `executor.py:execute_pipeline(config)`:

```
Phase 1: Parse URL
    └─ ado_url.parse_ado_url(url) → AdoTarget(org, org_url, project, work_item_id)

Phase 2: Fetch hierarchy
    └─ AdoClient.get_tree(root_id) → WorkItemNode tree
       Recursively walks Epic → Feature → User Story / PBI / Task
       via ADO REST API (System.LinkTypes.Hierarchy-Forward relations)

Phase 3: Build workspace
    └─ WorkspaceBuilder.build_from_tree(tree, ado) → WorkspaceManifest
       Creates type-prefixed folders, *_Summary.md files,
       downloads attachments to references/ directories

Phase 4: Render prompts
    └─ PromptRenderer.render_scenario_prompt(story, ancestors, images) → str
       Jinja2 template + Instructions + Common Steps + Background Steps
       Written to scenario_prompt.md for each leaf work item

Phase 5: Generate features
    └─ GenerationProvider.generate(prompt, images) → str
       Respects generation_limit, generation_limit_per_feature, generation_only_ids
       Written to Test Scenarios/*.feature

Phase 6: Copy to repo + git
    └─ copy_to_target_repo(manifest, target_repo_path) → int
       GitClient: checkout_or_create_branch, add_all, commit
```

### Leaf detection

Only work items of type **User Story**, **Product Backlog Item**, or **Task** are considered "leaf" items that generate `.feature` files. Epics and Features serve as structural containers.

### Generation limits

The executor checks limits in this order for each leaf item:
1. Total limit (`generation_limit`) — skip if already reached
2. ID filter (`generation_only_ids`) — skip if not in the list
3. Per-feature limit (`generation_limit_per_feature`) — skip if the Feature parent has reached its cap

## Domain models

All defined in `cli/atc/core/models.py`:

| Model | Purpose |
|-------|---------|
| `WorkItem` | Single ADO work item: id, title, type, description, acceptance_criteria, state, tags, fields, relations, attachments |
| `WorkItemNode` | Tree node: item + children list. Supports `.walk()` (BFS) and `.find_by_type()` |
| `Attachment` | name, url, local_path (populated after download) |
| `Relation` | rel (link type), url, attributes dict |
| `AdoTarget` | Parsed URL: org, org_url, project, work_item_id |
| `WorkspacePaths` | Filesystem paths for a single item: root, summary_md, references_dir, prompt_path, feature_path |
| `WorkspaceManifest` | root path + items dict (id → WorkspacePaths) |

## ADO REST API client

`AdoClient` (`cli/atc/infra/ado.py`):

- **Async** httpx client with Basic Auth (PAT token base64-encoded)
- **API version:** 7.1
- **Base URL:** `{org_url}/{project}/_apis`
- **Methods:** `get_work_item`, `get_work_items_batch` (200 per request), `get_children_ids`, `get_tree` (recursive), `download_attachment`
- **HTML → Markdown:** Description and acceptance criteria fields are converted from HTML to Markdown using `markdownify`

## Provider architecture

All providers implement `GenerationProvider.generate(prompt, images) -> str`:

```python
class GenerationProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, images: list[Path] | None = None) -> str: ...
```

The factory function `create_provider(config, settings)` selects and configures the provider based on `provider.type` in `run.json`. See [Providers](Providers.md) for details.

## Extension points

### Adding a new AI provider

1. Create `cli/atc/providers/my_provider.py` implementing `GenerationProvider`
2. Add a branch in `cli/atc/providers/__init__.py:create_provider()`
3. Add any new env vars to `cli/atc/infra/settings.py:AtcSettings`
4. Update `ProviderConfig.type` description in `cli/atc/infra/config.py`

### Adding a new URL format

See [URL Formats — Adding a new URL format](URL-Formats.md#adding-a-new-url-format).

### Adding a new work item type

1. Add the type name to `_LEAF_TYPES` in `executor.py` (if it should generate features)
2. Add a type prefix in `workspace.py:_get_type_prefix()`
3. Optionally add a child container in `workspace.py:_get_child_container_name()`

### Adding a new pipeline phase

1. Implement the phase logic in `executor.py:execute_pipeline()` at the appropriate position
2. Update the phase count in documentation

## Future architecture

The [CLI Design](../Automated_Test_Creation_CLI_Design.md) and [Technical Plan](../Automated_Test_Creation_Technical_Plan.md) describe planned features not yet implemented:

- **MCP Server** (`atc serve`) — tools for IDE agent integration
- **SQLite state database** — workflow state machine, audit trail, resume capability
- **Gate workflow** — Gate 1 (scenario approval), Gate 2 (code approval) with pause/resume
- **Duplicate prevention** — fingerprint registry + WIQL + rapidfuzz dedup
- **Bug reporting** — structured 11-section bug reports with severity classification
- **Execution phase** — run generated tests and collect results
