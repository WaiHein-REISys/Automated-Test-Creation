# GitHub Copilot Instructions — Automated Test Creation (ATC)

You are assisting with the ATC tool. The user should not need to run commands manually — you are the interface.

Read `agent.md` at the repo root for the full project reference.

## Project Context

ATC generates BDD/SpecFlow `.feature` files from Azure DevOps work items. The pipeline is driven by `cli/run.json` and executed via wrapper scripts.

## Key Commands (run from `cli/` directory)

```bash
./run_atc.sh run --config run.json              # Full pipeline
./run_atc.sh run --config run.json --dry-run    # Workspace + prompts only
./run_atc.sh run --config run.json --url "<URL>" # Override ADO URL
./run_atc.sh validate --config run.json          # Validate config
./run_atc.sh init                                # First-time setup
```

Platform: `./run_atc.sh` (macOS/Linux), `.\run_atc.ps1` (PowerShell), `run_atc.cmd` (CMD).

## When Generating Code in This Repo

- **Python 3.12+**, uses **Typer**, **Pydantic**, **httpx**, **Jinja2**, **Rich**
- Package lives in `cli/atc/` — editable install via `uv`
- Tests: `uv run pytest` | Lint: `uv run ruff check src/ tests/` | Types: `uv run mypy src/`
- Providers support `PromptBundle` (system + user messages) for multi-stage prompts

## When Suggesting Feature File Content

If the user asks you to write or fix `.feature` files, follow these rules:
- Valid SpecFlow syntax only — no markdown
- Tag every scenario: `@Functional @AIGenerated @US:<StoryID>`
- Cover 100% of acceptance criteria
- Use Background for shared setup steps
- Use Scenario Outline + Examples for data-driven scenarios
- Never copy reference steps literally — adapt to the actual story

## Configuration

- `cli/run.json` — pipeline config (edit this for the user when asked)
- `cli/.env` — secrets (**never display or commit**)
- `configs/reference/Instructions.txt` — 21 SpecFlow generation rules
- `configs/prompts/` — Jinja2 templates for multi-stage prompts

## Security

- **NEVER** display PAT tokens, API keys, or `.env` contents
- **NEVER** suggest committing secrets to git
