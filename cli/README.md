# ATC — Automated Test Creation CLI

Generate BDD/SpecFlow `.feature` files from Azure DevOps work items with a single command.

ATC fetches your Epic → Feature → User Story hierarchy from ADO, builds a structured workspace with markdown summaries and attachments, renders AI prompts, and generates `.feature` files using your choice of AI provider.

## Quick Start

```bash
cd cli

# 1. Install dependencies
uv sync --python 3.12

# 2. Set your ADO Personal Access Token
export ATC_ADO_PAT="your-pat-token"

# 3. Run — just paste an ADO URL
uv run atc run \
  --url "https://dev.azure.com/org/project/_workitems/edit/12345" \
  --config configs/runs/example.json
```

## Installation

**Prerequisites:** Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
# Install uv (if not already installed)
pip install uv

# Install project dependencies
uv sync --python 3.12

# Install with a specific AI provider
uv sync --python 3.12 --extra claude         # Anthropic Claude API
uv sync --python 3.12 --extra azure-openai   # Azure OpenAI

# Install dev dependencies (pytest, ruff, mypy)
uv sync --python 3.12 --extra dev
```

## Commands

| Command | Description |
|---------|-------------|
| `atc run` | Execute the full pipeline |
| `atc validate` | Validate a run config file |
| `atc init` | Create default config and directories |

### `atc run`

```bash
uv run atc run --config configs/runs/example.json --url "https://dev.azure.com/..." [--dry-run]
```

| Flag | Description |
|------|-------------|
| `--config`, `-c` | Path to run config JSON file (default: `run.json`) |
| `--url`, `-u` | ADO work item URL (overrides `url` in config) |
| `--dry-run` | Build workspace and render prompts but skip AI generation |

## Pipeline Phases

```
atc run --url "https://dev.azure.com/org/project/_workitems/edit/12345"
    │
    ├─ 1. Parse URL        → auto-detect org, project, work item ID
    ├─ 2. Fetch hierarchy  → recursively walk Epic → Feature → User Story (any depth)
    ├─ 3. Build workspace  → folders + .md summaries + download attachments
    ├─ 4. Render prompts   → Jinja2 templates with story context + reference steps
    ├─ 5. Generate         → call AI provider to produce .feature files
    ├─ 6. Copy to repo     → place files in target automation repository
    └─ 7. Git commit       → branch + commit (optional push)
```

## Configuration

### Run Config (`run.json`)

```json
{
  "url": "https://dev.azure.com/org/project/_workitems/edit/12345",
  "product_name": "EHB",
  "workspace_dir": "./workspace",
  "target_repo_path": "/path/to/EHB-UI-Automation",
  "branch_name": "dev/DME/feature/EHB",
  "provider": {
    "type": "claude",
    "model": "claude-sonnet-4-20250514"
  },
  "options": {
    "dry_run": false,
    "download_attachments": true,
    "include_images_in_prompt": true
  }
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `url` | Yes | ADO work item URL — org, project, and ID are parsed automatically |
| `product_name` | Yes | Product name for the top-level folder (e.g., `"EHB"`) |
| `workspace_dir` | No | Local workspace directory (default: `./workspace`) |
| `target_repo_path` | No | Path to target automation repo. If set, generated files are copied there |
| `branch_name` | No | Git branch name (e.g., `dev/DME/feature/EHB`). If set, auto-commits |
| `provider.type` | No | AI provider: `claude`, `azure_openai`, `ollama`, `cli_agent`, or `prompt_only` |
| `provider.model` | No | Model name or deployment name (depends on provider) |
| `provider.options` | No | Provider-specific options (see provider sections below) |
| `options.dry_run` | No | Skip AI generation, only build workspace and render prompts |
| `options.download_attachments` | No | Download work item attachments to `references/` folders (default: `true`) |
| `options.include_images_in_prompt` | No | Include image attachments in AI prompts for vision models (default: `true`) |

### Environment Variables (`.env`)

Create a `.env` file in the `cli/` directory:

```bash
# ── Required ──────────────────────────────────────────
ATC_ADO_PAT=your-ado-personal-access-token

# ── Claude (if provider.type = "claude") ──────────────
ATC_ANTHROPIC_API_KEY=sk-ant-...

# ── Azure OpenAI (if provider.type = "azure_openai") ──
ATC_AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
ATC_AZURE_OPENAI_API_KEY=your-key1-or-key2
ATC_AZURE_OPENAI_DEPLOYMENT=gpt-4o
ATC_AZURE_OPENAI_API_VERSION=2024-12-01-preview

# ── Ollama (if provider.type = "ollama") ──────────────
ATC_OLLAMA_MODEL=llama3
ATC_OLLAMA_URL=http://localhost:11434

# ── CLI Agent (if provider.type = "cli_agent") ────────
ATC_CLI_AGENT_CMD="windsurf generate --prompt {prompt_file}"
```

All variables use the `ATC_` prefix. Only `ATC_ADO_PAT` is always required — the rest depend on your chosen provider.

## AI Providers

### Claude (Anthropic API)

```json
{ "provider": { "type": "claude", "model": "claude-sonnet-4-20250514" } }
```

Supports vision — image attachments from ADO are sent to the API for context-aware generation.

**Requires:** `ATC_ANTHROPIC_API_KEY` + install with `uv sync --extra claude`

### Azure OpenAI

```json
{
  "provider": {
    "type": "azure_openai",
    "model": "gpt-4o",
    "options": {
      "endpoint": "https://your-resource.openai.azure.com/",
      "api_version": "2024-12-01-preview"
    }
  }
}
```

Supports vision with compatible deployments (e.g., `gpt-4o`). The `model` field maps to your Azure deployment name. Endpoint and API version can be set in the config or via env vars.

**Requires:** `ATC_AZURE_OPENAI_API_KEY` + `ATC_AZURE_OPENAI_ENDPOINT` + install with `uv sync --extra azure-openai`

### Ollama (Local LLM)

```json
{ "provider": { "type": "ollama", "model": "llama3" } }
```

Runs against a local Ollama instance. Supports multimodal models (e.g., `llava`) for image context.

**Requires:** [Ollama](https://ollama.com/) running locally.

### CLI Agent (External Tool)

```json
{
  "provider": {
    "type": "cli_agent",
    "options": { "command": "windsurf generate --prompt {prompt_file}" }
  }
}
```

Invokes any external CLI command. Use `{prompt_file}` as a placeholder for the temp file containing the rendered prompt. The tool reads stdout as the generated `.feature` content.

### Prompt Only (Manual)

```json
{ "provider": { "type": "prompt_only" } }
```

No AI invocation. The tool renders and saves prompts to the workspace. You copy them into your preferred tool (e.g., Windsurf Cascade), generate manually, and place the `.feature` files yourself.

## Workspace Structure

After running, the workspace directory contains:

```
workspace/
  {PRODUCT_NAME}/
    EPIC/
      {EPIC_ID} - {EPIC_TITLE}/
        EPIC_Summary.md                         ← all epic fields
        Features/
          {FEATURE_ID} - {FEATURE_TITLE}/
            Feature_Summary.md                  ← all feature fields
            references/                         ← feature attachments
            {STORY_ID} - {STORY_TITLE}/
              User_Story_Summary.md             ← story fields + acceptance criteria
              references/                       ← story attachments (images, docs)
              scenario_prompt.md                ← rendered AI prompt
              US{STORY_ID} - {STORY_TITLE}.feature  ← generated feature file
```

Each `*_Summary.md` includes: title, state, tags, area/iteration path, description, acceptance criteria, additional fields, and attachment links.

## URL Formats

ATC auto-parses these ADO URL formats — no manual org/project configuration needed:

```
https://dev.azure.com/{org}/{project}/_workitems/edit/{id}
https://dev.azure.com/{org}/{project}/_backlogs/backlog/{team}/Epics/?workitem={id}
https://{org}.visualstudio.com/{project}/_workitems/edit/{id}
```

## Reference Files

The `configs/reference/` directory contains files that are injected into every AI prompt:

| File | Purpose |
|------|---------|
| `Instructions.txt` | System prompt with 22 mandatory SpecFlow formatting rules |
| `Common_Steps.txt` | Existing step definitions to reuse (avoids duplicates) |
| `Background_Steps.txt` | Navigation and setup steps for Background sections |

Edit these files to customize the generation rules and step library for your project.

## Project Structure

```
cli/
  pyproject.toml                    ← dependencies and build config
  .env                              ← environment variables (not committed)
  atc/
    main.py                         ← Typer CLI: run, validate, init
    executor.py                     ← pipeline orchestrator (6 phases)
    core/
      models.py                     ← WorkItem, WorkItemNode, AdoTarget
    infra/
      ado.py                        ← Azure DevOps REST API client
      ado_url.py                    ← URL parser
      workspace.py                  ← folder structure builder
      prompts.py                    ← Jinja2 prompt renderer
      config.py                     ← RunConfig, ProviderConfig (Pydantic)
      settings.py                   ← environment variable settings
      git.py                        ← git branch/commit/push operations
    providers/
      base.py                       ← GenerationProvider abstract class
      claude.py                     ← Anthropic Claude API
      azure_openai.py               ← Azure OpenAI API
      ollama.py                     ← Local LLM via Ollama
      cli_agent.py                  ← External CLI tool invocation
      prompt_only.py                ← Save prompt for manual use
    output/
      console.py                    ← Rich terminal output helpers
  configs/
    prompts/
      scenario-generation.md.j2     ← main Jinja2 prompt template
      work-item-summary.md.j2      ← template for .md summary files
    reference/                      ← Instructions.txt, Common_Steps.txt, Background_Steps.txt
    runs/
      example.json                  ← example run config
  tests/
```

## Development

```bash
# Run tests
uv run pytest

# Lint
uv run ruff check .

# Format
uv run ruff format .

# Type check
uv run mypy atc/
```
# Automated-Test-Creation
