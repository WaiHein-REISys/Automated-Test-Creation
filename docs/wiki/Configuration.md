# Configuration

ATC uses two configuration sources: a **run config JSON file** (`run.json`) and **environment variables** (`.env`).

## Run Config (`run.json`)

The run config controls what to process and how. Create one with `python -m atc init` or copy from `configs/runs/example.json`.

### Full schema

```json
{
  "url": "https://dev.azure.com/org/project/_workitems/edit/12345",
  "product_name": "EHB",
  "workspace_dir": "./workspace",
  "target_repo_path": "/path/to/EHB-UI-Automation",
  "branch_name": "dev/DME/feature/EHB",
  "provider": {
    "type": "claude",
    "model": "claude-sonnet-4-20250514",
    "options": {}
  },
  "credentials": {
    "ado_pat": "",
    "anthropic_api_key": "",
    "azure_openai_endpoint": "",
    "azure_openai_api_key": "",
    "azure_openai_deployment": ""
  },
  "options": {
    "dry_run": false,
    "download_attachments": true,
    "include_images_in_prompt": true,
    "max_depth": 0,
    "filter_tags": [],
    "generation_limit": 0,
    "generation_limit_per_feature": 0,
    "generation_only_ids": [],
    "test_execution": {
      "enabled": false,
      "tag": "",
      "filter_expr": "",
      "config": "Release",
      "auto_build": true
    }
  }
}
```

### Field reference

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `url` | Yes | — | ADO work item URL. Org, project, and ID are parsed automatically. Supports cloud and on-prem ADS. See [URL Formats](URL-Formats.md). |
| `product_name` | Yes | — | Product name used as the top-level workspace folder (e.g. `"EHB"`). |
| `workspace_dir` | No | `./workspace` | Local directory where the workspace is built. |
| `target_repo_path` | No | `null` | Path to the target automation repo. If set, generated `.feature` files are copied there after generation. |
| `branch_name` | No | `null` | Git branch name. If set along with `target_repo_path`, ATC creates/switches to this branch and commits generated files. |
| `ado_api_version` | No | `auto` | Azure DevOps REST API version. `"auto"` probes the server (tries 7.1 → 7.0 → 6.0). Set explicitly (e.g. `"7.0"`) for on-prem servers that reject newer versions. |
| `credentials` | No | `{}` | Inline credentials. Values override env vars / `.env`. See [Inline credentials](#inline-credentials). |
| `provider.type` | No | `prompt_only` | AI provider: `claude`, `azure_openai`, `ollama`, `cli_agent`, or `prompt_only`. See [Providers](Providers.md). |
| `provider.model` | No | varies | Model name or deployment name. Depends on provider. |
| `provider.options` | No | `{}` | Provider-specific options (e.g. `endpoint`, `api_version` for Azure OpenAI). |
| `options.dry_run` | No | `false` | Build workspace and render prompts but skip AI generation. |
| `options.download_attachments` | No | `true` | Download work item attachments to `references/` folders. |
| `options.include_images_in_prompt` | No | `true` | Include image attachments in AI prompts for vision-capable providers. |
| `options.max_depth` | No | `0` | Max hierarchy levels below the root to traverse. `0` = unlimited (full tree). See [Hierarchy depth limit](#hierarchy-depth-limit). |
| `options.filter_tags` | No | `[]` | Only include child work items with at least one of these ADO tags (case-insensitive). `[]` = no filtering. See [Tag-based filtering](#tag-based-filtering). |
| `options.generation_limit` | No | `0` | Max total `.feature` files to generate. `0` = unlimited. |
| `options.generation_limit_per_feature` | No | `0` | Max `.feature` files per Feature parent. `0` = unlimited. |
| `options.generation_only_ids` | No | `[]` | Only generate for these work item IDs. `[]` = all. |
| `options.test_execution.enabled` | No | `false` | Run generated tests after the pipeline completes. See [Test execution](#test-execution). |
| `options.test_execution.tag` | No | `""` | SpecFlow tag for test filtering (e.g. `"Automated"`). |
| `options.test_execution.filter_expr` | No | `""` | Raw `dotnet test --filter` expression (overrides tag). |
| `options.test_execution.config` | No | `"Release"` | Build configuration (`Release` or `Debug`). |
| `options.test_execution.auto_build` | No | `true` | Build the project before running tests. |

### Hierarchy depth limit

`max_depth` controls how many levels of child work items are fetched below the root:

| `max_depth` | Behavior |
|-------------|----------|
| `0` | **Unlimited** (default) — traverse the entire tree: Epic → Feature → User Story → sub-tasks, etc. |
| `1` | Root + direct children only. E.g. if root is an Epic, fetch the Epic and its Features but stop there. |
| `2` | Root + children + grandchildren. E.g. Epic → Features → User Stories, but not sub-tasks under stories. |
| `3` | Three levels deep, and so on. |

**Example — fetch only the first two levels:**

```json
{
  "url": "https://ehbads.hrsa.gov/ads/EHBs/EHBs/_workitems/edit/411599",
  "product_name": "EHB",
  "options": {
    "max_depth": 2
  }
}
```

This is useful when:
- The hierarchy is very deep and you only need the top-level stories
- You want a fast preview of the epic structure without fetching all leaves
- The ADO server is slow and you want to reduce API calls

### Tag-based filtering

`filter_tags` lets you prune the work item hierarchy during fetch, keeping only child items that have at least one of the specified ADO tags. The root item is always included regardless of its tags.

- Tags are matched **case-insensitively** against the ADO `System.Tags` field.
- An empty list (`[]`) means no filtering — all children are fetched (default).
- Can be combined with `max_depth` for even more precise control.

**Example — only fetch items tagged "Automated" or "SF424":**

```json
{
  "url": "https://ehbads.hrsa.gov/ads/EHBs/EHBs/_workitems/edit/411599",
  "product_name": "EHB",
  "options": {
    "filter_tags": ["Automated", "SF424"]
  }
}
```

**CLI usage:**
```bash
./run_atc.sh run --config run.json --filter-tag Automated --filter-tag SF424
```

**PowerShell:**
```powershell
.\run_full.ps1 -FilterTags "Automated","SF424"
```

This is useful when:
- The hierarchy has many work items but you only want a subset tagged for automation
- Different teams tag items for different test suites
- You want to generate tests incrementally by tag

### Test execution

When `test_execution.enabled` is `true`, the pipeline adds a **Run Tests** phase after git operations. It uses the standalone EHB Test Runner (`cli/tools/ehb_test_runner.py`) to execute tests via `dotnet test`.

**Key detail:** `target_repo_path` is reused as the `--project` path for the test runner — it should point to the EHB2010 root directory containing `EHB.UI.Automation/`.

**Example:**
```json
{
  "target_repo_path": "C:/Repos/EHB2010",
  "options": {
    "test_execution": {
      "enabled": true,
      "tag": "Automated",
      "config": "Release",
      "auto_build": true
    }
  }
}
```

**CLI usage:**
```bash
./run_atc.sh run --config run.json --run-tests --test-tag Automated
```

**Results:**
- TRX files are written to `./TestResults/` (or `results_dir` if specified)
- ExtentReport HTML is at `{project}/EHB.UI.Automation/bin/{config}/net8.0/Reports/ExtentReport.html`
- The UI pipeline page shows pass/fail counts and expandable failed test details
- Zero external dependencies beyond Python stdlib and .NET SDK

### Inline credentials

The `credentials` section lets you store API keys and tokens directly in `run.json` instead of (or in addition to) environment variables.

**Priority order** (highest first):
1. `credentials.*` fields in `run.json`
2. `ATC_*` environment variables / `.env` file

Only non-empty values override. Leave a field empty (`""`) to fall back to the env var.

| Field | Env var equivalent | Description |
|-------|--------------------|-------------|
| `credentials.ado_pat` | `ATC_ADO_PAT` | Azure DevOps Personal Access Token |
| `credentials.anthropic_api_key` | `ATC_ANTHROPIC_API_KEY` | Anthropic (Claude) API key |
| `credentials.azure_openai_endpoint` | `ATC_AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint URL |
| `credentials.azure_openai_api_key` | `ATC_AZURE_OPENAI_API_KEY` | Azure OpenAI API key |
| `credentials.azure_openai_deployment` | `ATC_AZURE_OPENAI_DEPLOYMENT` | Azure OpenAI deployment name |
| `credentials.azure_openai_api_version` | `ATC_AZURE_OPENAI_API_VERSION` | Azure OpenAI API version |
| `credentials.ollama_url` | `ATC_OLLAMA_URL` | Ollama server URL |
| `credentials.ollama_model` | `ATC_OLLAMA_MODEL` | Ollama model name |
| `credentials.cli_agent_cmd` | `ATC_CLI_AGENT_CMD` | CLI agent command template |

**Example — all credentials in run.json (no .env needed):**

```json
{
  "url": "https://ehbads.hrsa.gov/ads/EHBs/EHBs/_workitems/edit/411599",
  "product_name": "EHB",
  "credentials": {
    "ado_pat": "your-pat-token",
    "anthropic_api_key": "sk-ant-..."
  },
  "provider": {
    "type": "claude"
  }
}
```

> **Security note:** Storing secrets in JSON files is convenient but less secure than environment variables. Ensure `run.json` is listed in `.gitignore` and not committed to version control.

The ATC UI config editor includes password-masked fields for all credentials. Values entered in the UI are saved into the `credentials` section of `run.json`.

### Generation limits

Generation limits let you control how many `.feature` files are produced in a single run:

- **`generation_limit`** — caps the total number of files across the entire run. Useful for testing with a small batch.
- **`generation_limit_per_feature`** — caps files per Feature parent. Useful for spreading generation across features.
- **`generation_only_ids`** — restricts generation to specific work item IDs. All other items still get their workspace and prompts built, but generation is skipped.

These limits can be combined. The executor checks them in order: total limit, ID filter, per-feature limit.

### Validating configuration

```bash
./run_atc.sh validate --config run.json
```

This parses the JSON, validates it against the Pydantic model, and prints the resolved config.

## Environment Variables (`.env`)

All variables use the `ATC_` prefix. Place them in `cli/.env` (loaded automatically via Pydantic Settings) or export them in your shell.

| Variable | Required | Description |
|----------|----------|-------------|
| `ATC_ADO_PAT` | Always | Azure DevOps Personal Access Token (work item read access) |
| `ATC_ADO_API_VERSION` | No | ADO REST API version override (`"auto"`, `"7.1"`, `"7.0"`, `"6.0"`). Overrides `ado_api_version` in `run.json`. |
| `ATC_ANTHROPIC_API_KEY` | If provider = `claude` | Anthropic API key |
| `ATC_AZURE_OPENAI_ENDPOINT` | If provider = `azure_openai` | Azure OpenAI endpoint URL |
| `ATC_AZURE_OPENAI_API_KEY` | If provider = `azure_openai` | Azure OpenAI API key |
| `ATC_AZURE_OPENAI_DEPLOYMENT` | If provider = `azure_openai` | Azure OpenAI deployment name |
| `ATC_AZURE_OPENAI_API_VERSION` | No | API version (default: `2024-12-01-preview`) |
| `ATC_OLLAMA_MODEL` | No | Ollama model name (default: `llama3`) |
| `ATC_OLLAMA_URL` | No | Ollama server URL (default: `http://localhost:11434`) |
| `ATC_CLI_AGENT_CMD` | If provider = `cli_agent` | Shell command template with `{prompt_file}` placeholder |

### `.env.example`

The repository includes `cli/.env.example` with placeholder values for all variables. The setup script copies it to `.env` if one doesn't exist.

## Reference files

The `configs/reference/` directory contains files injected into every AI prompt:

| File | Purpose |
|------|---------|
| `Instructions.txt` | 22 mandatory SpecFlow formatting rules (system prompt) |
| `Common_Steps.txt` | Existing step definitions to reuse |
| `Background_Steps.txt` | Navigation and setup steps for Background sections |

Edit these to customize generation rules for your project. Changes take effect on the next run.

## Prompt templates

Jinja2 templates in `configs/prompts/`:

| Template | Purpose |
|----------|---------|
| `scenario-generation.md.j2` | Main prompt sent to the AI provider. Includes instructions, story context, reference steps, and image paths. |
| `work-item-summary.md.j2` | Template for `*_Summary.md` files in the workspace. |

Template variables: `instructions`, `epic_title`, `feature_title`, `story_id`, `story_title`, `story_description`, `story_acceptance_criteria`, `common_steps`, `background_steps`, `image_paths`.
