# agent.md

This file is the primary entry point for all AI coding agents (Claude Code, Codex, Windsurf, etc.) working in this repository.

## Project Overview

**Automated Test Creation (ATC)** — a Python CLI tool that automates BDD test generation from Azure DevOps user stories via a single command driven by a JSON configuration file. Integrates with ADO REST API, prepares prompts for Windsurf FedRAMP + Cascade, and manages the full lifecycle: ingestion, scenario generation, approval gates, code generation, publishing, dedup, and bug reporting.

Design documents:
- `Automated_Test_Creation_Technical_Plan.md` — requirements and sprint plan
- `Automated_Test_Creation_CLI_Design.md` — **active design**: single-command CLI + MCP server

## Technology Stack

- **Python 3.12+**, **Typer** (CLI), **Rich** (terminal output), **Pydantic** (config/validation)
- **mcp** (Anthropic SDK) — MCP server for IDE agent integration
- **httpx** — ADO REST API, **rapidfuzz** — Levenshtein dedup, **Jinja2** — prompt templates
- **SQLite** (stdlib) — state/audit, **pytest** — tests, **uv** — packaging, **Ruff** + **mypy** — lint/types

## Primary Interface

Everything runs through one command and a JSON config file:

```bash
atc run --config run.json           # Execute pipeline
atc run --config run.json --dry-run # Simulate
atc run --config run.json --resume  # Continue from last pause
atc status --epic 12345             # Inspect state
atc validate --config run.json      # Check config
atc serve                           # MCP server for IDE agents
atc init                            # One-time setup
atc new-config --template full-auto --epic 12345  # Generate config
```

## Run Configuration (`run.json`)

Declares what to process and how. Template configs in `configs/runs/`.

Key fields: `epics`/`stories` (what to process), `phases` (which steps to run), `gates` (auto_approve/pause/skip + reviewer), `publish` (pr/push strategy), `options` (dry_run, resume, fail_fast, concurrency).

Exit codes: `0` success, `1` failure, `2` config error, `3` dry run done, `10` paused at Gate 1, `11` paused at Gate 2.

Output modes: `--format rich` (default), `--format json` (NDJSON events), `--format plain`.

## Project Structure

```
src/atc/
  main.py          # Typer app: run, init, status, validate, serve, new-config
  executor.py      # Pipeline executor (reads config, drives phases)
  phases/          # Phase implementations: ingest, scenario_gen, code_gen, gate, publish, execute, dedup, bug_report
  core/            # Domain logic: models, state machine, fingerprint, severity, eligibility
  infra/           # Adapters: ado client, git client, db, workspace, config parser, prompt renderer
  mcp/             # MCP server, tools, resources
  output/          # Formatters: rich, json, plain

configs/
  agent.md         # Policy file (parsed into Pydantic AgentConfig at startup)
  run.schema.json  # JSON Schema for run.json
  runs/            # Template configs: full-auto, scenarios-only, dry-run, etc.
  prompts/         # Jinja2 templates for scenario gen, code gen, bug hypotheses
```

## Build and Dev Commands

```bash
uv sync                                              # Install deps
uv run atc run --config configs/runs/full-auto.json  # Run pipeline
uv run atc serve                                     # MCP server

uv run pytest                                        # All tests
uv run pytest tests/test_executor.py                 # Single file
uv run pytest -k "test_resume_from_gate"             # Single test
uv run mypy src/                                     # Type check
uv run ruff check src/ tests/                        # Lint
uv run ruff format src/ tests/                       # Format
uv run alembic upgrade head                          # Migrations
```

## Architecture: Key Concepts

### Single-Command Pipeline
`atc run --config run.json` reads the JSON config, resolves stories, and drives them through phases sequentially. Gate behavior (auto_approve/pause/skip) is declared in JSON, not interactive. Resume reads state from SQLite and picks up where it left off.

### Workflow State Machine (20 states, story-level)
`Discovered` → ... → `ScenarioApproved` → ... → `CodeApproved` → `Publishing` → ... → `Completed`. Gates enforce: only `ScenarioApproved` → code gen, only `CodeApproved` → publish, `Failed` → dedup → bug report.

### Two-Layer Duplicate Prevention
Layer 1: fingerprint in SQLite (`{class}|{method}|{exception}|{failure_site}|{story_id}`). Layer 2: WIQL + rapidfuzz ≥ 85% against ADO bugs.

### Prompt Preparation (not Cascade invocation)
Tool renders Jinja2 templates with story/epic context. Human or IDE agent feeds prompt to Cascade. Tool ingests output.

## Environment Variables

Prefix `ATC_`. Required: `ATC_ADO_ORG`, `ATC_ADO_PROJECT`, `ATC_ADO_PAT`, `ATC_REPO_URL`, `ATC_TARGET_PATH`. Validated via Pydantic Settings. `.env` supported.
