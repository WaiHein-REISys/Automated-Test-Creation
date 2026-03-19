# agent.md

This is the primary entry point for **all** AI coding agents (Claude Code, Codex, Windsurf Cascade, Cursor, Copilot). Read this file completely before taking any action.

## What This Project Is

**Automated Test Creation (ATC)** — a Python CLI + agent-driven tool that generates BDD/SpecFlow `.feature` files from Azure DevOps work items. The user should never need to run commands manually or interact with a terminal. **You (the agent) are the interface.**

## Agent Workflow — Zero-Touch Pipeline

When the user says "run ATC", "generate tests", pastes an ADO URL, or asks anything about generating feature files, execute this workflow **without follow-up questions** (use `run.json` defaults for anything not specified):

### 1. Verify Environment

```bash
cd cli && ./run_atc.sh --version
```

If this fails, run setup:
```bash
cd cli && python setup_env.py
```

Credentials live in `cli/.env` — **never display PAT tokens or API keys**.

### 2. Run the Pipeline

**Full auto (provider configured in `run.json`):**
```bash
cd cli && ./run_atc.sh run --config run.json
```

**With a specific ADO URL:**
```bash
cd cli && ./run_atc.sh run --config run.json --url "https://reihsbu.visualstudio.com/EA/_workitems/edit/XXXXX"
```

**Dry run (workspace + prompts only, no LLM generation):**
```bash
cd cli && ./run_atc.sh run --config run.json --dry-run
```

### 3. If Provider Is `prompt_only` — You Generate the Features

When `run.json` has `"type": "prompt_only"`, the pipeline stops after rendering prompts. **You become the generator:**

1. Run dry-run to build workspace and render prompts
2. For each work item directory in workspace, read the split prompt files:
   - `system_prompt.md` — SpecFlow rules + product context (treat as your system instructions)
   - `user_prompt.md` — the specific user story to generate from
3. Generate the `.feature` file following ALL rules in the system prompt
4. Write it to the `Test Scenarios/` subdirectory:

```
workspace/{product}/EPIC/.../Features/Feat .../PBI... or US.../
  system_prompt.md       ← your instructions (DO NOT modify)
  user_prompt.md         ← the story content (DO NOT modify)
  scenario_prompt.md     ← combined view for reference
  Test Scenarios/
    PBI....feature       ← WRITE your generated content here
```

### 4. Report Results

After the pipeline completes, summarize:
- Total work items processed
- Feature files generated (count + locations)
- Any failures or skipped items
- Where outputs were written

## Run Configuration (`cli/run.json`)

The pipeline is driven entirely by this JSON file. Key fields:

| Field | Purpose |
|-------|---------|
| `url` | ADO work item URL (Epic, Feature, or Story) |
| `product_name` | Product identifier for folder structure |
| `provider.type` | `azure_openai`, `claude`, `ollama`, `cli_agent`, or `prompt_only` |
| `provider.model` | Model/deployment name (e.g. `gpt-4o-mini`) |
| `options.dry_run` | `true` = workspace + prompts only, no generation |
| `options.max_depth` | Hierarchy depth limit (0 = unlimited) |
| `options.generation_limit` | Max total feature files to generate (0 = unlimited) |
| `options.generation_limit_per_feature` | Max per Feature parent (0 = unlimited) |
| `options.generation_only_ids` | Only generate for specific work item IDs |
| `options.download_attachments` | Download images from ADO for vision-capable models |
| `target_repo_path` | Copy generated features to this repo path |
| `branch_name` | Git branch for committing generated files |

## CLI Reference

All commands run from the `cli/` directory:

| Task | Command |
|------|---------|
| Full pipeline | `./run_atc.sh run --config run.json` |
| Dry run | `./run_atc.sh run --config run.json --dry-run` |
| Custom URL | `./run_atc.sh run --config run.json --url "<URL>"` |
| Limit depth | `./run_atc.sh run --config run.json --max-depth 2` |
| Filter tags | `./run_atc.sh run --config run.json --filter-tag Automated` |
| Validate config | `./run_atc.sh validate --config run.json` |
| Launch UI | `./run_atc.sh ui` |
| Init setup | `./run_atc.sh init` |
| Status update | `python devops_status_update.py --dry-run` |

**Platform note:** Use `./run_atc.sh` on macOS/Linux, `.\run_atc.ps1` on Windows PowerShell, `run_atc.cmd` on Windows CMD.

## Project Structure

```
cli/
  run.json             # Active run configuration
  .env                 # Secrets (ATC_ADO_PAT, ATC_AZURE_OPENAI_API_KEY, etc.)
  run_atc.sh           # Cross-platform wrapper script
  setup_env.py         # Environment setup (installs deps)
  devops_status_update.py  # Post git-based status to ADO work items

  atc/
    __init__.py
    __main__.py        # python -m atc entry point
    main.py            # Typer CLI: run, validate, init, ui
    executor.py        # Pipeline executor (phases 1-6)
    core/
      models.py        # WorkItem, PromptBundle, WorkspaceManifest, etc.
    infra/
      ado.py           # ADO REST API client
      ado_url.py       # URL parser
      config.py        # RunConfig, ProviderConfig, RunOptions (Pydantic)
      prompts.py       # Multi-stage prompt renderer (system + user)
      settings.py      # Environment/credentials resolution
      workspace.py     # Folder structure builder
      git.py           # Git operations
    providers/
      base.py          # GenerationProvider ABC (supports PromptBundle)
      azure_openai.py  # Azure OpenAI (system + user messages)
      claude.py        # Anthropic Claude (system + user messages)
      ollama.py        # Local Ollama
      cli_agent.py     # External CLI tool
      prompt_only.py   # No generation — agent generates manually
    output/
      console.py       # Rich terminal output

  configs/
    prompts/
      system-prompt.md.j2       # Stage 1+2: generic rules + product context
      scenario-generation.md.j2 # Stage 3: user story content
      work-item-summary.md.j2   # Work item summary template
    reference/
      Instructions.txt          # SpecFlow generation rules (21 rules)
      Common_Steps.txt          # Step pattern examples (format reference only)
      Background_Steps.txt      # Background pattern examples (format reference only)

  workspace/           # Generated output (gitignored)
    {product}/EPIC/.../Features/.../PBI.../
      system_prompt.md
      user_prompt.md
      scenario_prompt.md
      Test Scenarios/
        PBI....feature
```

## Multi-Stage Prompt Architecture

The prompt pipeline is designed for cost-efficient generation with smaller models (e.g. gpt-4o-mini):

| Stage | Template | Role | Sent As |
|-------|----------|------|---------|
| **1. Generic** | `Instructions.txt` | 21 SpecFlow rules (any product) | system message |
| **2. Tailored** | `system-prompt.md.j2` | Product name, epic/feature context, step pattern references | system message |
| **3. Actual** | `scenario-generation.md.j2` | User story ID, title, description, acceptance criteria | user message |

Reference steps in Common_Steps.txt and Background_Steps.txt are **FORMAT EXAMPLES ONLY**. They must be adapted to match the actual user story — never copied literally.

## Pipeline Phases

1. **PARSE_URL** — Extract org, project, work item ID from the ADO URL
2. **FETCH_HIERARCHY** — Fetch work item tree via ADO REST API
3. **BUILD_WORKSPACE** — Create folder structure with summaries + downloaded attachments
4. **RENDER_PROMPTS** — Render multi-stage prompts (system_prompt.md + user_prompt.md)
5. **GENERATE_FEATURES** — Call AI provider to generate .feature files (or skip if prompt_only)
6. **COPY_TO_REPO** — Copy .feature files to target repo + git commit

## Environment Variables

All prefixed `ATC_`. Loaded from `cli/.env` or environment:

| Variable | Required | Purpose |
|----------|----------|---------|
| `ATC_ADO_PAT` | Yes | Azure DevOps Personal Access Token |
| `ATC_AZURE_OPENAI_ENDPOINT` | If using azure_openai | e.g. `https://my-resource.openai.azure.com` |
| `ATC_AZURE_OPENAI_API_KEY` | If using azure_openai | API key |
| `ATC_AZURE_OPENAI_DEPLOYMENT` | If using azure_openai | Deployment name (overridden by `provider.model`) |
| `ATC_ANTHROPIC_API_KEY` | If using claude | Anthropic API key |

## Critical Rules for Agents

1. **You are the interface.** The user should not need to open a terminal. Run commands on their behalf.
2. **Never display secrets.** Do not print PAT tokens, API keys, or `.env` contents.
3. **Use wrapper scripts** (`./run_atc.sh`, `.\run_atc.ps1`), not `uv run atc` directly (avoids module import issues).
4. **When generating features manually** (prompt_only mode), follow ALL 21 rules from `configs/reference/Instructions.txt`. Do not copy reference steps literally — adapt patterns to the actual story.
5. **Do not modify** `system_prompt.md` or `user_prompt.md` files — they are rendered by the pipeline.
6. **Report progress** after each phase. If something fails, diagnose and suggest a fix.
7. **Modify `run.json`** when the user asks to change settings (URL, limits, provider, etc.) — do not ask them to edit it manually.
