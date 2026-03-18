# Getting Started

This guide covers installing ATC and running your first pipeline on any operating system.

## Prerequisites

- **Python 3.12 or 3.13** (required)
- **Git** (required for the copy-to-repo and commit phases)
- **uv** (optional — the setup script falls back to pip if uv is unavailable)
- **Azure DevOps Personal Access Token (PAT)** with work item read access

## Step 1 — Clone and install

```bash
git clone <repo-url>
cd Automated-Test-Creation/cli
```

### One-command setup (recommended)

```bash
python setup_env.py
```

This script:
1. Checks your Python version (3.12 or 3.13 required)
2. Uses `uv sync` if uv is available, otherwise creates a `.venv` and uses `pip`
3. Copies `.env.example` to `.env` if `.env` doesn't already exist

Install with optional extras:

```bash
python setup_env.py --extras claude         # Anthropic Claude API
python setup_env.py --extras azure-openai   # Azure OpenAI
python setup_env.py --extras dev            # pytest, ruff, mypy
python setup_env.py --extras all            # everything
```

### Windows PowerShell one-shot setup

From the **repository root** (not `cli/`):

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup-atc.ps1 -Provider prompt_only
```

This runs `setup_env.py`, calls `atc init`, and creates `cli/.env` + `cli/run.json` in one step. See [Cross-Platform Support](Cross-Platform-Support.md) for full details.

## Step 2 — Configure credentials

Edit `cli/.env` with your ADO Personal Access Token:

```bash
ATC_ADO_PAT=your-ado-personal-access-token
```

Or set it as an environment variable:

```bash
# Linux / macOS
export ATC_ADO_PAT="your-pat-token"

# Windows PowerShell
$env:ATC_ADO_PAT = "your-pat-token"

# Windows CMD
set ATC_ADO_PAT=your-pat-token
```

If you use an AI provider other than `prompt_only`, also set its API key. See [Providers](Providers.md).

## Step 3 — Create a run configuration

```bash
python -m atc init
```

This creates `configs/runs/example.json`. Copy or edit it as `run.json`:

```json
{
  "url": "https://dev.azure.com/org/project/_workitems/edit/12345",
  "product_name": "EHB",
  "provider": {
    "type": "prompt_only"
  }
}
```

See [Configuration](Configuration.md) for all available fields.

## Step 4 — Run the pipeline

```bash
# macOS / Linux
./run_atc.sh run --config run.json

# Windows PowerShell
.\run_atc.ps1 run --config run.json

# Windows CMD
run_atc.cmd run --config run.json
```

To build the workspace and prompts without generating `.feature` files:

```bash
./run_atc.sh run --config run.json --dry-run
```

To override the ADO URL from the command line:

```bash
./run_atc.sh run --config run.json --url "https://ehbads.hrsa.gov/ads/EHBs/EHBs/_workitems/edit/411599"
```

## Step 5 — Review output

After the pipeline completes, the workspace directory contains:

```
workspace/{product_name}/EPIC/Epic .../Features/Feat .../
  US{id} - {title}/
    User_Story_Summary.md       ← work item details
    references/                 ← downloaded attachments
    scenario_prompt.md          ← rendered AI prompt
    Test Scenarios/
      US{id} - {title}.feature  ← generated feature file
```

## What's next

- [Configuration](Configuration.md) — all run config fields, generation limits, and options
- [Providers](Providers.md) — set up Claude, Azure OpenAI, Ollama, or CLI Agent
- [Windsurf Integration](Windsurf-Integration.md) — zero-interaction workflow in Windsurf Cascade
