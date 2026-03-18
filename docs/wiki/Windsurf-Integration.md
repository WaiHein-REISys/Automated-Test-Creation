# Windsurf Integration

ATC can run through Windsurf Cascade with minimum interaction. This page explains how to set it up and the two workflow options.

## Setup

1. Install ATC ([Getting Started](Getting-Started.md))
2. Configure `cli/.env` with your ADO PAT and provider API key
3. Configure `cli/run.json` with your ADO URL and product name
4. The `.windsurfrules` file at the repo root teaches Cascade the ATC workflow

## Option A: Fully automated (AI provider generates features)

Set `provider.type` in `run.json` to `claude`, `azure_openai`, or `ollama`. Then tell Cascade:

> Run ATC for https://ehbads.hrsa.gov/ads/EHBs/EHBs/_workitems/edit/411599

Cascade reads `.windsurfrules` and runs:

```powershell
# Windows PowerShell:
cd cli; .\run_full.ps1 -Url "https://ehbads.hrsa.gov/ads/EHBs/EHBs/_workitems/edit/411599"

# macOS / Linux:
cd cli && ./run_full.sh --url "https://ehbads.hrsa.gov/ads/EHBs/EHBs/_workitems/edit/411599"
```

The single command does everything:

1. Parses the ADO URL (cloud or on-prem)
2. Fetches the Epic → Feature → User Story hierarchy
3. Builds the workspace with summaries and attachments
4. Renders Jinja2 prompts with story context + reference steps
5. Calls the AI provider to generate `.feature` files
6. Copies files to the target repo (if `target_repo_path` is set)
7. Creates a git branch and commits (if `branch_name` is set)

**Interaction required:** just paste the URL. Everything else is automated.

## Option B: Cascade generates the features itself

Set `provider.type` to `"prompt_only"`. Tell Cascade:

> Run ATC for https://ehbads.hrsa.gov/ads/EHBs/EHBs/_workitems/edit/411599

Cascade follows the `.windsurfrules` two-phase approach:

### Phase A — Build workspace and prompts

```bash
cd cli && ./run_atc.sh run --config run.json --url "https://..." --dry-run
```

### Phase B — Cascade reads each prompt and generates features

For each `scenario_prompt.md` in the workspace:
1. Cascade reads the prompt (which includes SpecFlow rules, story context, and reference steps)
2. Cascade generates the `.feature` file content
3. Cascade writes it to the corresponding `Test Scenarios/` directory

```
workspace/{product}/EPIC/Epic .../Features/Feat .../US.../
  scenario_prompt.md           ← Cascade reads this
  Test Scenarios/
    US... - {title}.feature    ← Cascade writes this
```

**Interaction required:** paste the URL. Cascade handles both phases.

## `.windsurfrules` file

The `.windsurfrules` file at the repo root contains the full workflow instructions. Cascade reads it automatically. It covers:

- How to determine the run configuration
- When to use the auto provider vs. prompt_only workflow
- The correct wrapper script commands for each OS
- SpecFlow generation rules and reference file locations
- Security: never display PAT tokens or API keys

## Convenience scripts

| Script | Usage |
|--------|-------|
| `run_full.ps1` | `.\run_full.ps1 -Url "https://..."` (PowerShell) |
| `run_full.sh` | `./run_full.sh --url "https://..."` (bash) |

These are thin wrappers around `run_atc.*` that default to `run.json` and pass through `--url` and `--dry-run`.

## Tips for minimum interaction

1. **Pre-configure `run.json`** with your `product_name`, `provider`, `target_repo_path`, and `branch_name`. Then you only need to paste the URL.
2. **Use an API-based provider** (claude or azure_openai) for true zero-interaction runs. The `prompt_only` mode requires Cascade to generate each file.
3. **Set generation limits** if you want to test with a small batch first: `"generation_limit": 3`.
4. **Use `--dry-run` first** to inspect the workspace and prompts before committing to full generation.

## Future enhancements

- MCP server (`atc serve`) for direct IDE agent integration without CLI
- Streaming progress events for real-time Cascade feedback
- Cascade-native provider that invokes Cascade API directly
