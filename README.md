# ATC — Automated Test Creation CLI

Generate BDD/SpecFlow `.feature` files from Azure DevOps work items with a single command.

ATC fetches your Epic → Feature → User Story hierarchy from ADO, builds a structured workspace with markdown summaries and attachments, renders AI prompts, and generates `.feature` files using your choice of AI provider.

## Quick Start

```bash
cd cli

# 1. Install dependencies (works on Windows, macOS, Linux)
python setup_env.py

# 2. Set your ADO Personal Access Token
#    Linux / macOS:
export ATC_ADO_PAT="your-pat-token"
#    Windows PowerShell:
#    $env:ATC_ADO_PAT = "your-pat-token"
#    Windows CMD:
#    set ATC_ADO_PAT=your-pat-token
#    Or add it to the .env file (recommended — created automatically by setup_env.py)

# 3. Run — just paste an ADO URL
#    Linux / macOS:
./run_atc.sh run --config run.json
#    Windows PowerShell:
#    .\run_atc.ps1 run --config run.json
#    Windows CMD:
#    run_atc.cmd run --config run.json
```

> **Note:** Always use `python -m atc` (or the wrapper scripts) instead of `uv run atc`.
> The `uv run atc` entry point has a known issue with hatchling editable installs where `.pth` files
> aren't processed reliably, causing `ModuleNotFoundError: No module named 'atc'`.
> The wrapper scripts handle this automatically — they try uv first, fall back to the venv, then system Python.

## Installation

**Prerequisites:** Python 3.12 or 3.13, and (optionally) [uv](https://docs.astral.sh/uv/).

The setup script auto-detects your OS and available tools. It uses **uv** if installed, otherwise falls back to **venv + pip**.

### PowerShell one-shot setup

From the repository root, Windows users can run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup-atc.ps1 -Provider prompt_only
```

What it does:

- calls `cli/setup_env.py` to install dependencies
- runs `atc init`
- creates `cli/.env` and `cli/run.json` if they do not already exist
- preserves existing `cli/.env` and `cli/run.json` unless you pass `-Force`

Useful options:

- `-Provider prompt_only|claude|azure_openai|ollama|cli_agent`
- `-IncludeDevTools`
- `-AdoPat "..."`, `-AdoUrl "https://dev.azure.com/..."`
- `-ProductName "EHB"`, `-TargetRepoPath "C:\Repos\EHB-UI-Automation"`
- `-BranchName "dev/DME/feature/EHB"`
- `-Force`

If you want the virtual environment to remain active in the current PowerShell session, dot-source the script:

```powershell
. .\setup-atc.ps1 -Provider prompt_only
```

```bash
cd cli

# Recommended: one-command setup (all platforms)
python setup_env.py

# Install with a specific AI provider
python setup_env.py --extras claude         # Anthropic Claude API
python setup_env.py --extras azure-openai   # Azure OpenAI

# Install dev dependencies (pytest, ruff, mypy)
python setup_env.py --extras dev

# Install everything
python setup_env.py --extras all
```

### Manual installation with uv (macOS/Linux)

```bash
uv sync --python 3.12
uv sync --python 3.12 --extra claude         # with Claude
uv sync --python 3.12 --extra azure-openai   # with Azure OpenAI
uv sync --python 3.12 --extra dev            # with dev tools
```

### Manual installation with pip (all platforms, Windows-friendly)

```bash
python -m venv .venv

# Activate:
#   Linux / macOS:  source .venv/bin/activate
#   PowerShell:     .\.venv\Scripts\Activate.ps1
#   CMD:            .\.venv\Scripts\activate.bat

pip install -e ".[claude,dev]"
```

## Commands

| Command | Description |
|---------|-------------|
| `python -m atc run` | Execute the full pipeline |
| `python -m atc validate` | Validate a run config file |
| `python -m atc init` | Create default config and directories |

### `atc run`

```bash
# Linux / macOS:
./run_atc.sh run --config run.json --url "https://dev.azure.com/..." --dry-run

# Windows PowerShell:
.\run_atc.ps1 run --config run.json --url "https://dev.azure.com/..." --dry-run

# Windows CMD:
run_atc.cmd run --config run.json --url "https://dev.azure.com/..." --dry-run
```

| Flag | Description |
|------|-------------|
| `--config`, `-c` | Path to run config JSON file (default: `run.json`) |
| `--url`, `-u` | ADO work item URL (overrides `url` in config) |
| `--dry-run` | Build workspace and render prompts but skip AI generation |

## Pipeline Phases

```
uv run python -m atc run --config run.json
    │
    ├─ 1. Parse URL        → auto-detect org, project, work item ID
    ├─ 2. Fetch hierarchy  → recursively walk Epic → Feature → User Story / PBI / Task
    ├─ 3. Build workspace  → type-prefixed folders + .md summaries + download attachments
    ├─ 4. Render prompts   → Jinja2 templates with story context + reference steps
    ├─ 5. Generate         → call AI provider to produce .feature files (with limits)
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
  "ado_api_version": "auto",
  "provider": {
    "type": "claude",
    "model": "claude-sonnet-4-20250514"
  },
  "options": {
    "dry_run": false,
    "download_attachments": true,
    "include_images_in_prompt": true,
    "generation_limit": 0,
    "generation_limit_per_feature": 0,
    "generation_only_ids": []
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
| `ado_api_version` | No | ADO REST API version: `"auto"` (default, probes server), `"7.1"`, `"7.0"`, `"6.0"` |
| `provider.type` | No | AI provider: `claude`, `azure_openai`, `ollama`, `cli_agent`, or `prompt_only` |
| `provider.model` | No | Model name or deployment name (depends on provider) |
| `provider.options` | No | Provider-specific options (see provider sections below) |
| `options.dry_run` | No | Skip AI generation, only build workspace and render prompts |
| `options.download_attachments` | No | Download work item attachments to `references/` folders (default: `true`) |
| `options.include_images_in_prompt` | No | Include image attachments in AI prompts for vision models (default: `true`) |
| `options.generation_limit` | No | Max total feature files to generate. `0` = unlimited (default: `0`) |
| `options.generation_limit_per_feature` | No | Max feature files per Feature parent folder. `0` = unlimited (default: `0`) |
| `options.generation_only_ids` | No | Only generate for these work item IDs. `[]` = all (default: `[]`) |

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
      Epic {EPIC_ID} - {EPIC_TITLE}/
        Epic_Summary.md                              ← all epic fields
        Features/
          Feat {FEATURE_ID} - {FEATURE_TITLE}/
            Feature_Summary.md                       ← all feature fields
            references/                              ← feature attachments
            US{STORY_ID} - {STORY_TITLE}/            ← User Story
              User_Story_Summary.md
              references/
              scenario_prompt.md                     ← rendered AI prompt
              US{STORY_ID} - {STORY_TITLE}.feature   ← generated feature file
            PBI{PBI_ID} - {PBI_TITLE}/               ← Product Backlog Item
              Product_Backlog_Item_Summary.md
              references/
              scenario_prompt.md
              PBI{PBI_ID} - {PBI_TITLE}.feature
            Task {TASK_ID} - {TASK_TITLE}/            ← Task
              Task_Summary.md
              references/
              scenario_prompt.md
              Task {TASK_ID} - {TASK_TITLE}.feature
```

Folder and file names are prefixed by type (`Epic`, `Feat`, `US`, `PBI`, `Task`) for easy identification. Supports **User Story**, **Product Backlog Item**, and **Task** work item types.

Each `*_Summary.md` includes: title, state, tags, area/iteration path, description, acceptance criteria, additional fields, and attachment links.

## URL Formats

ATC auto-parses these ADO URL formats — no manual org/project configuration needed:

```
https://dev.azure.com/{org}/{project}/_workitems/edit/{id}
https://dev.azure.com/{org}/{project}/_backlogs/backlog/{team}/Epics/?workitem={id}
https://{org}.visualstudio.com/{project}/_workitems/edit/{id}
https://{server}/{path}/{collection}/{project}/_workitems/edit/{id}   (on-prem ADS)
```

On-premises Azure DevOps Server (ADS) URLs are detected automatically by looking for ADO path markers (`_workitems`, `_backlogs`, etc.).

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
  setup_env.py                      ← cross-platform setup script
  run_atc.sh                        ← run wrapper (macOS / Linux)
  run_atc.ps1                       ← run wrapper (Windows PowerShell)
  run_atc.cmd                       ← run wrapper (Windows CMD)
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
# Run tests (with uv)
uv run pytest

# Or without uv (activate venv first)
pytest

# Lint
uv run ruff check .

# Format
uv run ruff format .

# Type check
uv run mypy atc/
```

## Troubleshooting

### `ModuleNotFoundError: No module named 'atc'`

This is a known issue with hatchling editable installs via uv. The `.pth` file that registers the package
isn't reliably processed when Python runs the entry point script.

**Fix:** Use the wrapper scripts or `python -m atc` instead of `uv run atc`:

```bash
# These always work:
./run_atc.sh run --config run.json          # macOS / Linux
.\run_atc.ps1 run --config run.json         # Windows PowerShell
run_atc.cmd run --config run.json           # Windows CMD
uv run python -m atc run --config run.json  # Direct (any platform)

# This may fail:
uv run atc run --config run.json  # don't use this
```

### `uv` not working on Windows

If `uv` fails to install or run on Windows, use the pip fallback:

```bash
python setup_env.py          # auto-detects and uses pip if uv is unavailable
```

Or install manually:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m atc --help
```

### `400 Bad Request` — API version out of range (on-prem ADS)

If your on-premises Azure DevOps Server returns:

```
The requested REST API version of 7.1 is out of range for this server.
```

ATC now **auto-detects** the server's supported version by default. If you still see this on older code, set the version explicitly:

```json
// in run.json:
"ado_api_version": "7.0"
```

Or via environment variable:
```
ATC_ADO_API_VERSION=7.0
```

### PowerShell execution policy error

If `.\run_atc.ps1` is blocked by execution policy:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```
