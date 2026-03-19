# Changelog

Notable changes, enhancements, and additions to ATC. Organized by date with the most recent changes first.

---

## 2026-03-18

### Test execution integration (EHB Test Runner)

**Files changed:** `cli/atc/infra/config.py`, `cli/atc/core/progress.py`, `cli/atc/executor.py`, `cli/atc/main.py`, `cli/atc/ui/pages/pipeline.py`, `cli/atc/ui/pages/config_editor.py`, `cli/run_full.ps1`, `cli/run_full.sh`, `cli/configs/runs/example.json`

**Standalone tools:** `cli/tools/ehb_test_runner.py`, `cli/tools/parse_trx.py`, `cli/tools/external-runner.sh`, `cli/tools/external-runner.cmd`

Added a new pipeline phase (Phase 8: **Run Tests**) that executes generated `.feature` files against an EHB2010 .NET project after the git-commit phase.

**Key design decisions:**
- `target_repo_path` in `run.json` is reused as the `--project` path for the EHB Test Runner (it points to the EHB2010 root containing the `EHB.UI.Automation/` folder)
- Tests run in a background thread (`asyncio.to_thread`) to avoid blocking the event loop
- `cli/tools/` files are imported at runtime — the pipeline still works without .NET SDK installed
- Test results (TRX) are written to the caller's CWD, not the EHB2010 repo
- Zero external dependencies (stdlib + .NET SDK only)

**New config section (`options.test_execution`):**
```json
{
  "options": {
    "test_execution": {
      "enabled": false,
      "tag": "Automated",
      "filter_expr": "",
      "run_id": "",
      "results_dir": "./TestResults",
      "config": "Release",
      "auto_build": true
    }
  }
}
```

**New CLI flags:** `--run-tests`, `--test-tag <tag>`, `--test-filter <expr>`

**New PowerShell flags:** `-RunTests`, `-TestTag <tag>`, `-TestFilter <expr>`

**UI:** Config editor has a "Test Execution (EHB Runner)" card; pipeline results page shows passed/failed/total test counts, TRX path, and expandable failed test details.

---

### Inline credentials in run.json

**Files changed:** `cli/atc/infra/config.py`, `cli/atc/infra/settings.py`, `cli/atc/executor.py`, `cli/atc/providers/__init__.py`, `cli/atc/ui/pages/config_editor.py`

Added a `credentials` section to `run.json` so PAT and API keys can be stored alongside the run configuration — no `.env` or environment variables needed.

- New `CredentialsConfig` model with fields for all provider credentials
- `resolve_settings()` helper merges run.json credentials over env vars (run.json wins when non-empty)
- UI config editor has password-masked fields for all credentials
- Provider error messages updated to mention both env var and run.json paths

**Priority order:** `credentials.*` in run.json > `ATC_*` env var > `.env` file

---

### Hierarchy depth limit (`max_depth`)

**Files changed:** `cli/atc/infra/config.py`, `cli/atc/infra/ado.py`, `cli/atc/executor.py`, `cli/atc/main.py`, `cli/run_full.ps1`, `cli/run_full.sh`, `setup-atc.ps1`, `cli/configs/runs/example.json`, `.windsurfrules`, `cli/atc/ui/pages/config_editor.py`

Added `options.max_depth` to limit how many levels of child items are fetched:
- `0` = unlimited (default, existing behavior)
- `1` = root + direct children only
- `2` = root → children → grandchildren, etc.

Available via `--max-depth` CLI flag, `run.json`, `-MaxDepth` in PowerShell scripts, and the UI config editor.

---

### On-premises Azure DevOps Server (ADS) URL support

**Files changed:** `cli/atc/infra/ado_url.py`

Added generic support for on-premises ADS URLs. Any URL containing ADO path markers (`_workitems`, `_backlogs`, `_queries`, `_apis`) is now accepted — the parser extracts the collection (org), project, and work item ID automatically.

**Example:**
```
https://ehbads.hrsa.gov/ads/EHBs/EHBs/_workitems/edit/411599
  → org=EHBs, org_url=https://ehbads.hrsa.gov/ads/EHBs, project=EHBs, id=411599
```

**How it works:**
- Scans path segments for ADO markers
- Segment before the marker = project
- Segment before that = collection (org)
- Everything before the project = org base URL
- Custom ports are preserved

**Enhancement opportunity:** Add support for `_boards/` URLs, auto-detect server API version.

---

### Cross-platform support (Windows, macOS, Linux)

**Files added:**
- `cli/setup_env.py` — cross-platform setup script (uv or pip fallback)
- `cli/run_atc.ps1` — PowerShell run wrapper
- `cli/run_atc.cmd` — Windows CMD run wrapper
- `setup-atc.ps1` — PowerShell one-shot setup (repo root)

**Files changed:**
- `cli/run_atc.sh` — upgraded with uv detection, venv fallback, Python version checking
- `cli/atc/infra/git.py` — added `_find_git()` with Windows install path detection

**Key decisions:**
- `setup_env.py` uses `shutil.which()` to find `uv`, falls back to `venv + pip` if unavailable
- All wrapper scripts follow the same fallback chain: uv → venv → system Python → py launcher (Windows)
- Python version strictly validated: 3.12 or 3.13 only
- `_find_git()` checks `C:\Program Files\Git\cmd\git.exe` on Windows when git isn't on PATH

**Enhancement opportunity:**
- Docker container for reproducible cross-platform execution
- GitHub Actions CI matrix (Windows, macOS, Ubuntu)
- Homebrew formula, Chocolatey package

---

### Windsurf Cascade integration

**Files added:**
- `.windsurfrules` — teaches Cascade the full ATC workflow
- `cli/run_full.ps1` — one-shot PowerShell convenience script
- `cli/run_full.sh` — one-shot bash convenience script

**Two workflow options:**
1. **Auto provider** (claude/azure_openai): fully automated, paste URL → done
2. **Prompt only**: Cascade builds workspace then generates `.feature` files itself

**Enhancement opportunity:**
- MCP server for direct IDE agent integration
- Cascade-native provider
- Streaming progress events

---

### Documentation wiki

**Files added:** `docs/wiki/` directory with 10 pages

| Page | Coverage |
|------|----------|
| Home | Wiki navigation, quick links |
| Getting Started | Installation on any OS, first run |
| Configuration | run.json fields, env vars, reference files, templates |
| Providers | All 5 providers: setup, config, implementation details |
| URL Formats | All URL patterns, on-prem detection logic, extension guide |
| Architecture | Project structure, pipeline phases, domain models, extension points |
| Cross-Platform Support | Setup scripts, wrappers, git client, known issues |
| Windsurf Integration | Cascade workflow, .windsurfrules, convenience scripts |
| Troubleshooting | Installation, config, runtime, and provider-specific issues |
| Changelog | This file |

---

## Initial release (pre-2026-03-18)

### Core pipeline

- 7-phase pipeline: parse URL → fetch hierarchy → build workspace → render prompts → generate → copy to repo → git commit
- Async ADO REST API client (httpx, API v7.1)
- Recursive work item tree traversal (Epic → Feature → User Story/PBI/Task)
- HTML-to-Markdown conversion for ADO fields
- Type-prefixed workspace folder structure with `*_Summary.md` files
- Jinja2 prompt rendering with reference file injection
- Attachment download to `references/` directories

### AI providers

- Claude (Anthropic API) with vision support
- Azure OpenAI with vision support
- Ollama (local LLM) with multimodal support
- CLI Agent (external command invocation)
- Prompt Only (manual mode)
- Factory pattern: `create_provider(config, settings)`

### Configuration

- Pydantic v2 models: `RunConfig`, `ProviderConfig`, `RunOptions`
- Pydantic Settings with `ATC_` prefix and `.env` support
- Generation limits: total, per-feature, ID filter
- CLI: Typer with `run`, `validate`, `init` commands

### URL parsing (original)

- `https://dev.azure.com/{org}/{project}/_workitems/edit/{id}`
- `https://dev.azure.com/{org}/{project}/_backlogs/backlog/{team}/Epics/?workitem={id}`
- `https://{org}.visualstudio.com/{project}/_workitems/edit/{id}`
- `https://dev.azure.com/{org}/{project}/_queries/query/{guid}/?workitem={id}`

---

## Planned enhancements

These are documented in the [CLI Design](../Automated_Test_Creation_CLI_Design.md) and [Technical Plan](../Automated_Test_Creation_Technical_Plan.md) but not yet implemented:

| Feature | Design Reference | Priority |
|---------|-----------------|----------|
| MCP Server (`atc serve`) | CLI Design §8 | High |
| SQLite state database | CLI Design §4, Tool Design §5 | High |
| Workflow state machine (20 states) | Tool Design §6 | High |
| Gate 1 — scenario approval | Technical Plan Sprint 2 | High |
| Gate 2 — code approval | Technical Plan Sprint 2 | Medium |
| Resume from gate pause | CLI Design §3 | Medium |
| Duplicate prevention (fingerprint + WIQL + rapidfuzz) | Technical Plan Sprint 2 | Medium |
| Structured bug reports (11 sections) | Technical Plan Sprint 3 | Medium |
| Severity classification | Technical Plan Sprint 3 | Low |
| ~~Test execution phase~~ | ~~CLI Design §2~~ | ✅ Done |
| PII redaction | Technical Plan §4 | Low |
| NDJSON output format | CLI Design §7 | Low |
