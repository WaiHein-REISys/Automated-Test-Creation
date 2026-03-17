# Automated Test Creation — CLI & IDE Agent Design

**Single-Command Architecture Driven by JSON Configuration**

---

## 1. Product Shape

Build this as a **single-command CLI tool** that reads all instructions from a JSON run configuration file.

The primary interface is one command:

```bash
atc run --config run.json
```

This replaces the multi-command workflow from the previous design. Instead of requiring the operator to type `atc ingest`, then `atc generate scenarios`, then `atc approve`, then `atc generate code`, etc., the tool reads a JSON file that declares:

- which epics/stories to process
- how to handle each gate (auto-approve, skip, or pause for review)
- which pipeline phases to execute
- output and publishing preferences
- reviewer identity

The tool then executes the entire pipeline end-to-end in a single invocation. No interactive prompts. No multi-step command sequences.

Secondary interfaces remain available:

- `atc serve` — MCP server mode for IDE agent integration
- `atc status --config run.json` — inspect current state without executing
- `atc init` — one-time workspace and database setup

## 2. Technology Stack

Use **Python 3.12+** as the implementation language.

| Component | Technology | Rationale |
|---|---|---|
| CLI framework | **Typer** | Minimal command surface; type-annotated arguments |
| Terminal output | **Rich** | Progress bars, tables, panels, syntax highlighting during run |
| MCP server | **mcp** (Anthropic Python SDK) | Native MCP protocol; IDE agents trigger runs via tools |
| HTTP client | **httpx** | Async ADO REST API calls; connection pooling; timeout control |
| Database | **SQLite** via **sqlite3** (stdlib) | Zero-dependency; single-file state; concurrent-read safe for CI |
| Database migrations | **Alembic** or raw SQL versioned scripts | Schema evolution without ORM overhead |
| Template rendering | **Jinja2** | Prompt templates, bug report rendering, Gherkin scaffolding |
| Similarity matching | **rapidfuzz** | Levenshtein scoring for Layer 2 dedup; C-accelerated |
| Configuration | **Pydantic** | Strongly-typed JSON config + agent.md parsing; validation with clear errors |
| Testing | **pytest** | Standard Python test runner; fixtures; parametrize for edge cases |
| Packaging | **uv** | Fast dependency resolution; lockfile; single `uv run atc` invocation |

## 3. System Boundaries

The tool is the **control plane** around Windsurf/Cascade.

External systems:

- Azure DevOps: source of epics/stories; destination for tags, comments, bugs
- Windsurf FedRAMP + Cascade: generation engine (invoked via IDE, not via API)
- Git/Azure Repos: destination for generated test artifacts
- CI pipeline: executes published tests; returns pass/fail

Internal responsibilities:

- ingestion and filtering
- artifact organization
- approval gating (configurable per run)
- pipeline state management
- duplicate prevention
- structured bug reporting
- auditability

The tool does **not** call Cascade programmatically. It prepares prompt files and artifact context that the engineer or IDE agent feeds to Cascade. The tool then ingests the generation output and manages the rest of the lifecycle.

## 4. Run Configuration File (`run.json`)

This is the central input to the tool. One file drives the entire execution.

### 4.1 Full Schema

```json
{
  "$schema": "./configs/run.schema.json",

  "epics": [12345],
  "stories": [],

  "phases": {
    "ingest": true,
    "generate_scenarios": true,
    "gate_1": "auto_approve",
    "generate_code": true,
    "gate_2": "auto_approve",
    "publish": true,
    "execute": false,
    "dedup": true,
    "bug_report": true
  },

  "gates": {
    "gate_1": {
      "mode": "auto_approve",
      "reviewer": "qa-bot"
    },
    "gate_2": {
      "mode": "auto_approve",
      "reviewer": "dev-bot"
    }
  },

  "publish": {
    "strategy": "pr",
    "branch_prefix": "atc/",
    "base_branch": "main",
    "auto_merge": false
  },

  "output": {
    "format": "rich",
    "log_file": "logs/run-{timestamp}.log",
    "artifact_dir": "workspace"
  },

  "options": {
    "dry_run": false,
    "resume": true,
    "fail_fast": false,
    "concurrency": 1,
    "tag_ado_on_complete": true
  }
}
```

### 4.2 Field Reference

#### `epics` / `stories`

What to process. Specify one or both:

- `"epics": [12345]` — ingest and process all eligible stories from these epics
- `"stories": [67890, 67891]` — process specific stories (skips ingestion, stories must already exist in workspace)
- both — ingest epics first, then filter to only the listed stories

#### `phases`

Which pipeline phases to execute. Set `false` to skip a phase entirely. Each phase depends on prior phases completing:

| Phase | Type | Description |
|---|---|---|
| `ingest` | `bool` | Fetch stories from ADO, materialize to workspace |
| `generate_scenarios` | `bool` | Render prompt, write .feature files |
| `gate_1` | `"auto_approve"` / `"pause"` / `"skip"` | Scenario review gate |
| `generate_code` | `bool` | Generate test code from approved scenarios |
| `gate_2` | `"auto_approve"` / `"pause"` / `"skip"` | Code review gate |
| `publish` | `bool` | Commit and push/PR to target repo |
| `execute` | `bool` | Trigger CI pipeline and wait for results |
| `dedup` | `bool` | Run duplicate detection on failures |
| `bug_report` | `bool` | Create ADO bug work items for new failures |

#### `gates`

Gate behavior configuration:

- **`auto_approve`** — record approval automatically, continue immediately. Use for trusted re-runs or when the IDE agent is handling review.
- **`pause`** — write artifacts to workspace, print file paths and review summary, exit with code `10` (Gate 1) or `11` (Gate 2). The operator reviews, then re-runs with `"resume": true` to continue from where it stopped.
- **`skip`** — skip the gate entirely, do not record an approval event.

The `reviewer` field is recorded in the approval audit log.

#### `publish`

- `"strategy": "pr"` — create a feature branch and open a pull request
- `"strategy": "push"` — push directly to base branch
- `"branch_prefix"` — e.g., `"atc/"` produces branches like `atc/story-67890`
- `"auto_merge"` — if `true`, auto-complete the PR after creation (requires ADO permissions)

#### `options`

- `dry_run` — simulate the full pipeline without writing to ADO or git
- `resume` — pick up where the last run stopped (reads state from SQLite). When `false`, resets story states and starts fresh.
- `fail_fast` — stop on first story failure. When `false`, continue processing remaining stories and report all failures at the end.
- `concurrency` — number of stories to process in parallel (default `1` for sequential). Parallelism applies to independent stories within an epic; gates still serialize.
- `tag_ado_on_complete` — add `Test Creation Done` tag to ADO stories when pipeline completes successfully.

### 4.3 Minimal Configurations

**Full auto-pilot (CI/CD integration):**

```json
{
  "epics": [12345],
  "phases": {
    "ingest": true,
    "generate_scenarios": true,
    "gate_1": "auto_approve",
    "generate_code": true,
    "gate_2": "auto_approve",
    "publish": true,
    "execute": true,
    "dedup": true,
    "bug_report": true
  },
  "gates": {
    "gate_1": { "mode": "auto_approve", "reviewer": "ci-pipeline" },
    "gate_2": { "mode": "auto_approve", "reviewer": "ci-pipeline" }
  }
}
```

**Generate scenarios only, pause for human review:**

```json
{
  "epics": [12345],
  "phases": {
    "ingest": true,
    "generate_scenarios": true,
    "gate_1": "pause",
    "generate_code": false,
    "gate_2": "skip",
    "publish": false
  },
  "gates": {
    "gate_1": { "mode": "pause", "reviewer": "jane.doe" }
  }
}
```

**Resume after Gate 1 review, continue through code gen and publish:**

```json
{
  "epics": [12345],
  "phases": {
    "ingest": false,
    "generate_scenarios": false,
    "gate_1": "auto_approve",
    "generate_code": true,
    "gate_2": "auto_approve",
    "publish": true
  },
  "gates": {
    "gate_1": { "mode": "auto_approve", "reviewer": "jane.doe" },
    "gate_2": { "mode": "auto_approve", "reviewer": "john.smith" }
  },
  "options": { "resume": true }
}
```

**Dry run a single story:**

```json
{
  "stories": [67890],
  "phases": {
    "ingest": false,
    "generate_scenarios": true,
    "gate_1": "auto_approve",
    "generate_code": true,
    "gate_2": "auto_approve",
    "publish": false
  },
  "options": { "dry_run": true }
}
```

### 4.4 Template Configs

Ship these as starter templates in `configs/runs/`:

```
configs/runs/
  full-auto.json           # All phases, auto-approve, publish with PR
  scenarios-only.json      # Ingest + generate scenarios, pause at Gate 1
  resume-after-review.json # Resume from Gate 1, generate code, publish
  dry-run.json             # Full pipeline, dry_run: true
  single-story.json        # Process one story, all phases
  ci-pipeline.json         # Optimized for CI: json output, fail-fast
```

## 5. High-Level Architecture

```text
┌──────────────────────────────────────────────────────────────────────┐
│  run.json                                                            │
│  (declares epics, phases, gate modes, publish strategy, options)     │
└──────────────────────────────────┬───────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│  atc run --config run.json                                           │
│                                                                      │
│  Pipeline Executor                                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────┐  ┌──────────┐  ┌──────────┐  │
│  │ Ingest   │→ │ Scenario │→ │Gate 1│→ │ Code Gen │→ │  Gate 2  │  │
│  │          │  │   Gen    │  │      │  │          │  │          │  │
│  └──────────┘  └──────────┘  └──────┘  └──────────┘  └──────────┘  │
│       │                                                     │        │
│       │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│       └→ │ Publish  │→ │ Execute  │→ │  Dedup   │→ │Bug Report│    │
│          └──────────┘  └──────────┘  └──────────┘  └──────────┘    │
│                                                                      │
│  Shared: core logic, ADO client, git client, workspace, db          │
└─────────────┬────────────────────────────────┬───────────────────────┘
              │                                │
              ▼                                ▼
┌──────────────────────────┐    ┌──────────────────────────────────────┐
│ SQLite (data/atc.db)     │    │ Workspace Filesystem                 │
│                          │    │                                      │
│ - epics                  │    │ workspace/epics/{epicId}/            │
│ - stories                │    │   epic-summary.md                    │
│ - pipeline_runs          │    │   stories/{storyId}/                 │
│ - approvals              │    │     story.md                         │
│ - fingerprints           │    │     scenario.feature                 │
│ - bugs                   │    │     generated-tests/                 │
│ - audit_events           │    │     prompts/                         │
│                          │    │     bug-report.md                    │
└──────────────────────────┘    └──────────────────────────────────────┘
```

## 6. CLI Surface

### 6.1 Primary Command

```bash
# The one command that does everything
atc run --config run.json

# With overrides
atc run --config run.json --dry-run
atc run --config run.json --format json
atc run --config run.json --resume
```

### 6.2 Utility Commands

```bash
# One-time setup
atc init

# Inspect state without executing
atc status --config run.json
atc status --epic 12345
atc status --story 67890

# Validate configuration before running
atc validate --config run.json

# MCP server mode for IDE agents
atc serve

# Generate a starter run.json from a template
atc new-config --template full-auto --epic 12345 --output run.json
```

### 6.3 Exit Codes

| Code | Meaning |
|---|---|
| `0` | Pipeline completed successfully |
| `1` | Pipeline failed (errors in one or more stories) |
| `2` | Configuration or validation error |
| `10` | Paused at Gate 1 — review scenarios, then re-run with resume |
| `11` | Paused at Gate 2 — review code, then re-run with resume |
| `3` | Dry run completed (no side effects) |

Exit codes `10` and `11` are not errors. They signal that the tool paused intentionally and the operator should review artifacts before resuming.

### 6.4 Output During Execution

When `--format rich` (default), the tool prints a live progress view:

```
ATC Pipeline — Epic #12345: Authentication Module
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 Story #67890  User can reset password    ████████████████████ 5/5  ✓ Published
 Story #67891  Login lockout after 3 fa…  ████████░░░░░░░░░░░ 3/5  ⏸ Gate 1
 Story #67892  OAuth2 provider integrat…  ░░░░░░░░░░░░░░░░░░░ 0/5  ⏳ Queued

Gate 1 paused for Story #67891:
  Scenario:  workspace/epics/12345/stories/67891/scenario.feature
  Review and re-run with: atc run --config run.json --resume
```

When `--format json`, each phase completion emits a JSON line to stdout:

```json
{"event":"phase_complete","story_id":67890,"phase":"generate_scenarios","status":"ok","artifact":"workspace/epics/12345/stories/67890/scenario.feature","timestamp":"2026-03-16T14:30:00Z"}
{"event":"gate_paused","story_id":67891,"gate":"gate_1","artifact":"workspace/epics/12345/stories/67891/scenario.feature","timestamp":"2026-03-16T14:30:05Z"}
```

When `--format plain`:

```
[OK] Story #67890 — generate_scenarios — workspace/epics/12345/stories/67890/scenario.feature
[OK] Story #67890 — gate_1 — auto_approved by qa-bot
[PAUSE] Story #67891 — gate_1 — review workspace/epics/12345/stories/67891/scenario.feature
```

## 7. Pipeline Executor Design

### 7.1 Execution Model

The executor reads `run.json`, loads state from SQLite, and processes stories through the configured phases.

```python
async def execute_pipeline(config: RunConfig, db: Database, ws: Workspace):
    stories = resolve_stories(config, db)

    for story in stories:
        current_state = db.get_story_state(story.id)

        for phase in config.active_phases():
            if phase.should_skip(current_state):
                continue

            if phase.is_gate and phase.mode == "pause":
                emit_pause(story, phase)
                db.save_state(story.id, phase.paused_state)
                return ExitCode.GATE_1_PAUSED if phase.name == "gate_1" else ExitCode.GATE_2_PAUSED

            result = await phase.execute(story, db, ws)
            db.transition(story.id, result.new_state)
            emit_progress(story, phase, result)

            if result.failed and config.options.fail_fast:
                return ExitCode.FAILED

    return ExitCode.SUCCESS
```

### 7.2 Phase Implementations

Each phase is a function that takes a story context and returns a result:

| Phase | Input | Output | Side Effects |
|---|---|---|---|
| `ingest` | ADO epic ID | Story records + workspace files | Writes to SQLite + workspace |
| `generate_scenarios` | Story context + epic summary | `.feature` file + prompt log | Writes to workspace |
| `gate_1` | Generated scenario | Approval record | Writes to SQLite |
| `generate_code` | Approved scenario + story context | Test code files + prompt log | Writes to workspace |
| `gate_2` | Generated code | Approval record | Writes to SQLite |
| `publish` | Approved code | Git branch + PR URL | Pushes to remote repo |
| `execute` | Published branch | CI run result | Triggers CI, polls for completion |
| `dedup` | Failed test result | Match/no-match decision | Reads/writes fingerprints in SQLite |
| `bug_report` | Failure with no dedup match | ADO bug work item | Creates bug in ADO |

### 7.3 Resume Behavior

When `options.resume` is `true`:

1. Load all story states from SQLite
2. For each story, determine the last completed phase
3. Skip all phases up to and including the last completed one
4. If a story is in a `paused` state (e.g., `scenario_generated` waiting for Gate 1), the gate's configured mode in the current `run.json` determines what happens:
   - `"auto_approve"` — approve and continue
   - `"pause"` — pause again (no-op, still waiting)
   - `"skip"` — skip the gate and continue

This means the resume workflow is:

1. First run with `gate_1: "pause"` → tool exits with code `10`
2. Human reviews scenario files in editor
3. Second run with `gate_1: "auto_approve"` and `resume: true` → tool picks up from Gate 1, approves, continues

## 8. MCP Server Mode

```bash
atc serve
```

The MCP server exposes a single primary tool plus utility tools:

### 8.1 MCP Tools

```json
{
  "name": "run_pipeline",
  "description": "Execute the ATC pipeline with the given configuration",
  "inputSchema": {
    "type": "object",
    "properties": {
      "config": {
        "type": "object",
        "description": "Run configuration (same schema as run.json)"
      }
    },
    "required": ["config"]
  }
}
```

```json
{
  "name": "get_status",
  "description": "Get current pipeline status for an epic or story",
  "inputSchema": {
    "type": "object",
    "properties": {
      "epic_id": { "type": "integer" },
      "story_id": { "type": "integer" }
    }
  }
}
```

```json
{
  "name": "validate_config",
  "description": "Validate a run configuration without executing",
  "inputSchema": {
    "type": "object",
    "properties": {
      "config": { "type": "object" }
    },
    "required": ["config"]
  }
}
```

### 8.2 MCP Resources

- `atc://stories/{storyId}` — current story state and metadata
- `atc://stories/{storyId}/scenario` — generated .feature content
- `atc://stories/{storyId}/code` — generated test code
- `atc://stories/{storyId}/bug-report` — structured bug report
- `atc://epics/{epicId}/status` — epic-level pipeline status
- `atc://config/agent` — current agent.md configuration
- `atc://runs/latest` — latest run result summary

### 8.3 IDE Agent Workflow

An IDE agent can drive the entire pipeline with two tool calls:

```
Agent: [calls run_pipeline with config { epics: [12345], gate_1: "pause" }]
Tool:  returns { status: "paused", gate: "gate_1", stories: [{id: 67890, artifact: "..."}] }
Agent: [reads atc://stories/67890/scenario, presents to human, gets approval]
Agent: [calls run_pipeline with config { epics: [12345], gate_1: "auto_approve", resume: true }]
Tool:  returns { status: "completed", stories: [{id: 67890, published: true}] }
```

### 8.4 MCP Configuration

```json
{
  "mcpServers": {
    "atc": {
      "command": "uv",
      "args": ["run", "atc", "serve"],
      "cwd": "/path/to/atc-project"
    }
  }
}
```

## 9. Project Structure

```text
atc/
├── pyproject.toml
├── uv.lock
├── alembic.ini
├── src/
│   └── atc/
│       ├── __init__.py
│       ├── main.py                 # Typer app: run, init, status, validate, serve, new-config
│       ├── executor.py             # Pipeline executor (reads config, drives phases)
│       ├── phases/
│       │   ├── __init__.py
│       │   ├── ingest.py           # ADO ingestion phase
│       │   ├── scenario_gen.py     # Scenario generation phase
│       │   ├── code_gen.py         # Code generation phase
│       │   ├── gate.py             # Gate logic (auto_approve / pause / skip)
│       │   ├── publish.py          # Git publish phase
│       │   ├── execute.py          # CI trigger and poll phase
│       │   ├── dedup.py            # Duplicate detection phase
│       │   └── bug_report.py       # Bug report creation phase
│       ├── core/
│       │   ├── models.py           # Domain models (Story, Epic, Run, Approval, Bug)
│       │   ├── state.py            # Workflow state machine and transitions
│       │   ├── fingerprint.py      # Fingerprint generation and matching
│       │   ├── severity.py         # Severity auto-classification
│       │   └── eligibility.py      # Story eligibility rules
│       ├── infra/
│       │   ├── ado.py              # Azure DevOps REST API client
│       │   ├── git.py              # Git operations (branch, commit, PR)
│       │   ├── db.py               # SQLite connection and repositories
│       │   ├── workspace.py        # Filesystem artifact store
│       │   ├── config.py           # agent.md + run.json parser (Pydantic)
│       │   └── prompts.py          # Jinja2 prompt template renderer
│       ├── mcp/
│       │   ├── server.py           # MCP server setup
│       │   ├── tools.py            # MCP tool definitions
│       │   └── resources.py        # MCP resource definitions
│       └── output/
│           ├── rich.py             # Rich terminal formatters + progress
│           ├── json.py             # JSON-lines event emitter
│           └── plain.py            # Plain text log formatter
├── migrations/
│   └── versions/
├── configs/
│   ├── agent.md                    # Policy file
│   ├── agent.schema.json           # JSON Schema for agent.md
│   ├── run.schema.json             # JSON Schema for run.json
│   ├── runs/                       # Starter run config templates
│   │   ├── full-auto.json
│   │   ├── scenarios-only.json
│   │   ├── resume-after-review.json
│   │   ├── dry-run.json
│   │   ├── single-story.json
│   │   └── ci-pipeline.json
│   └── prompts/
│       ├── scenario-generation.md.j2
│       ├── code-generation.md.j2
│       └── bug-hypothesis.md.j2
├── tests/
│   ├── conftest.py
│   ├── test_executor.py
│   ├── test_state.py
│   ├── test_fingerprint.py
│   ├── test_dedup.py
│   ├── test_severity.py
│   ├── test_eligibility.py
│   ├── test_config.py
│   ├── test_workspace.py
│   ├── test_phases.py
│   └── test_mcp_tools.py
├── workspace/
└── data/
```

## 10. Core Module Design

### 10.1 `core/state.py` — Workflow State Machine

```python
class StoryState(str, Enum):
    DISCOVERED = "discovered"
    ELIGIBLE = "eligible"
    INGESTED = "ingested"
    SCENARIO_GENERATING = "scenario_generating"
    SCENARIO_GENERATED = "scenario_generated"
    SCENARIO_CHANGES_REQUESTED = "scenario_changes_requested"
    SCENARIO_APPROVED = "scenario_approved"
    CODE_GENERATING = "code_generating"
    CODE_GENERATED = "code_generated"
    CODE_CHANGES_REQUESTED = "code_changes_requested"
    CODE_APPROVED = "code_approved"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    EXECUTING = "executing"
    PASSED = "passed"
    FAILED = "failed"
    DUPLICATE_DETECTED = "duplicate_detected"
    BUG_CREATED = "bug_created"
    COMPLETED = "completed"
    BLOCKED = "blocked"

TRANSITIONS: dict[StoryState, set[StoryState]] = {
    StoryState.DISCOVERED: {StoryState.ELIGIBLE, StoryState.BLOCKED},
    StoryState.ELIGIBLE: {StoryState.INGESTED},
    StoryState.INGESTED: {StoryState.SCENARIO_GENERATING},
    StoryState.SCENARIO_GENERATING: {StoryState.SCENARIO_GENERATED, StoryState.BLOCKED},
    StoryState.SCENARIO_GENERATED: {StoryState.SCENARIO_APPROVED, StoryState.SCENARIO_CHANGES_REQUESTED},
    StoryState.SCENARIO_CHANGES_REQUESTED: {StoryState.SCENARIO_GENERATING},
    StoryState.SCENARIO_APPROVED: {StoryState.CODE_GENERATING},
    StoryState.CODE_GENERATING: {StoryState.CODE_GENERATED, StoryState.BLOCKED},
    StoryState.CODE_GENERATED: {StoryState.CODE_APPROVED, StoryState.CODE_CHANGES_REQUESTED},
    StoryState.CODE_CHANGES_REQUESTED: {StoryState.CODE_GENERATING},
    StoryState.CODE_APPROVED: {StoryState.PUBLISHING},
    StoryState.PUBLISHING: {StoryState.PUBLISHED, StoryState.BLOCKED},
    StoryState.PUBLISHED: {StoryState.EXECUTING},
    StoryState.EXECUTING: {StoryState.PASSED, StoryState.FAILED},
    StoryState.FAILED: {StoryState.DUPLICATE_DETECTED, StoryState.BUG_CREATED},
    StoryState.DUPLICATE_DETECTED: {StoryState.COMPLETED},
    StoryState.BUG_CREATED: {StoryState.COMPLETED},
    StoryState.PASSED: {StoryState.COMPLETED},
}
```

### 10.2 `infra/config.py` — Configuration Models

Two configuration layers:

**RunConfig** — per-run settings from `run.json`:

```python
class GateConfig(BaseModel):
    mode: Literal["auto_approve", "pause", "skip"] = "auto_approve"
    reviewer: str = "system"

class PhaseConfig(BaseModel):
    ingest: bool = True
    generate_scenarios: bool = True
    gate_1: Literal["auto_approve", "pause", "skip"] = "auto_approve"
    generate_code: bool = True
    gate_2: Literal["auto_approve", "pause", "skip"] = "auto_approve"
    publish: bool = True
    execute: bool = False
    dedup: bool = True
    bug_report: bool = True

class PublishConfig(BaseModel):
    strategy: Literal["pr", "push"] = "pr"
    branch_prefix: str = "atc/"
    base_branch: str = "main"
    auto_merge: bool = False

class RunOptions(BaseModel):
    dry_run: bool = False
    resume: bool = True
    fail_fast: bool = False
    concurrency: int = 1
    tag_ado_on_complete: bool = True

class RunConfig(BaseModel):
    epics: list[int] = []
    stories: list[int] = []
    phases: PhaseConfig = PhaseConfig()
    gates: dict[str, GateConfig] = {}
    publish: PublishConfig = PublishConfig()
    output: OutputConfig = OutputConfig()
    options: RunOptions = RunOptions()
```

**AgentConfig** — global policy from `agent.md` (unchanged):

```python
class AgentConfig(BaseModel):
    ado_connection: AdoConnectionSettings
    story_eligibility: StoryEligibilityRules
    scenario_generation: ScenarioGenerationRules
    code_generation: CodeGenerationRules
    review_gates: ReviewGatePolicies
    target_repo: TargetRepoMapping
    dedup: DedupSettings
    bug_report: BugReportRules
    severity: SeverityMapping
    redaction: RedactionRules
```

### 10.3 Other Core Modules

Same as previous design:

- `core/fingerprint.py` — fingerprint format: `{test_class}|{test_method}|{exception_type}|{normalized_failure_site}|{story_id}`
- `core/severity.py` — integration→Sev1, unit/service→Sev2, utility/component→Sev3, ui/e2e→Sev4
- `core/eligibility.py` — WIQL filter by `Ready for Development`, exclude `Test Creation Done`
- `infra/workspace.py` — typed accessors for artifact paths
- `infra/prompts.py` — Jinja2 template rendering

## 11. Data Model

SQLite tables (unchanged):

- `epics` — id, ado_epic_id, title, state, last_ingested_utc
- `stories` — id, ado_story_id, epic_id, title, tags_json, acceptance_criteria_markdown, workflow_state, assigned_test_stack, artifact_root, last_transition_utc
- `pipeline_runs` — id, story_id, run_type, status, started_utc, completed_utc, triggered_by
- `artifacts` — id, story_id, artifact_type, path, content_hash, version_number, created_utc
- `approvals` — id, story_id, gate_type, decision, reviewer, comments, decided_utc
- `fingerprints` — id, story_id, fingerprint_key, class_name, method_name, exception_signature, first_seen_utc, last_seen_utc, occurrence_count
- `bugs` — id, story_id, ado_bug_id, fingerprint_id, similarity_score, action_taken, created_utc
- `audit_events` — id, entity_type, entity_id, event_type, payload_json, created_utc

## 12. Environment Variables

```bash
# Required
ATC_ADO_ORG=https://dev.azure.com/myorg
ATC_ADO_PROJECT=MyProject
ATC_ADO_PAT=***
ATC_REPO_URL=https://dev.azure.com/myorg/MyProject/_git/MyRepo
ATC_TARGET_PATH=tests/

# Optional
ATC_DB_PATH=data/atc.db
ATC_WORKSPACE=workspace/
ATC_CONFIG=configs/agent.md
ATC_LOG_LEVEL=INFO
```

Validated via Pydantic Settings. `.env` file supported.

## 13. Structured Bug Report

Same 11-section model (Summary, Failing Story/Epic, Environment, Test Type/Severity, Steps to Reproduce, Expected Result, Actual Result, Failure Evidence, Data Snapshot, Root Cause Hypotheses, Occurrence History). Rendered by Jinja2 into Markdown artifact and ADO-formatted HTML. PII redaction via regex before any write.

## 14. Build and Development Commands

```bash
uv sync                                           # Install dependencies
uv run atc run --config configs/runs/full-auto.json  # Run pipeline
uv run atc serve                                   # Start MCP server
uv run atc status --epic 12345                     # Check status
uv run atc validate --config run.json              # Validate config
uv run atc new-config --template full-auto --epic 12345  # Generate config

uv run pytest                                      # Run all tests
uv run pytest tests/test_executor.py               # Single file
uv run pytest -k "test_resume_from_gate"           # Single test
uv run mypy src/                                   # Type check
uv run ruff check src/ tests/                      # Lint
uv run ruff format src/ tests/                     # Format
uv run alembic upgrade head                        # Migrations
```

## 15. Delivery Order

1. Project skeleton: pyproject.toml, Typer app with `run`/`init`/`status`/`validate` commands, SQLite schema
2. `run.json` schema + Pydantic models + `validate` command
3. `agent.md` parser and validator
4. Pipeline executor framework (phase loop, state transitions, resume logic)
5. Ingest phase (ADO client + workspace materialization)
6. Scenario generation phase (Jinja2 prompts + .feature output)
7. Gate phase (auto_approve / pause / skip logic)
8. Code generation phase
9. Publish phase (git branch + PR)
10. Execute phase (CI trigger + poll)
11. Dedup phase (fingerprint + ADO search)
12. Bug report phase
13. Output formatters (rich, json, plain)
14. `new-config` command + template configs
15. MCP server mode
16. `run.schema.json` for editor autocomplete

## 16. What This Design Changes

| Aspect | Previous CLI Design | Single-Command Design |
|---|---|---|
| Primary interface | ~15 discrete commands | `atc run --config run.json` |
| Configuration | CLI flags and arguments | JSON file (versionable, shareable, repeatable) |
| Gate handling | Interactive `atc approve` / `atc reject` | Configured in JSON: auto_approve / pause / skip |
| Resume | `--from-state` flag | `"resume": true` in JSON + state in SQLite |
| Batch processing | `atc run <epic>` with interactive pauses | Single run.json drives all stories through all phases |
| CI integration | Shell scripts calling multiple commands | One command with `--format json` |
| Reproducibility | Depends on command history | run.json is the complete specification |

## 17. What Not to Do in Version 1

- Do not add a web UI
- Do not add a daemon mode or background worker
- Do not use an ORM
- Do not build custom diff rendering
- Do not implement Cascade API integration (prompt preparation only)
- Do not add interactive prompts within `atc run` — gate behavior is always declared in JSON
- Do not support YAML or TOML config — JSON with schema is sufficient and enables editor autocomplete
