# Automated Test Creation Tool Design

## 1. Recommended Product Shape

Build this as a **modular monolith** first, not a set of microservices.

That keeps the first release simpler while still matching the structure in the planning document:

- one control-plane web app for review, approvals, and monitoring
- one worker process for long-running pipeline steps
- one shared data store for workflow state, approvals, fingerprints, and audit history
- one artifact workspace on disk for stories, scenarios, prompts, generated code, logs, and bug reports

This design preserves the planned separation of concerns without forcing distributed-system overhead before it is justified.

## 2. Technology Recommendation

Use **.NET 10 / ASP.NET Core 10** for the host application and worker.

Recommended app model:

- **Razor Pages** for Gate 1 and Gate 2 review screens
- **Minimal APIs** for orchestration endpoints and machine-to-machine actions
- **BackgroundService** for queued pipeline execution
- **SQLite** for metadata, approvals, dedup state, and audit history
- **filesystem workspace** for generated artifacts and versioned prompt/config files

Why this stack fits the source document:

- it aligns with the .NET-heavy engineering environment already assumed by the testing plan
- it supports an internal line-of-business workflow UI cleanly
- it keeps ADO integration, approval flows, and dedup logic in one operational boundary
- it is easier to secure and deploy into Azure DevOps-oriented enterprise environments

## 3. System Boundaries

The tool should act as the **control plane** around Windsurf/Cascade, not as a replacement for it.

External systems:

- Azure DevOps: source of epics/stories and destination for tags, comments, and bugs
- Windsurf FedRAMP + Cascade: generation engine for scenarios, code, and bug hypotheses
- Git/Azure Repos: destination for generated test artifacts
- CI pipeline: executes published tests and returns pass/fail outcomes

Internal responsibilities:

- ingestion and filtering
- artifact organization
- approval gating
- pipeline state management
- duplicate prevention
- structured bug reporting
- auditability

## 4. High-Level Architecture

```text
┌──────────────────────────────────────────────────────────────┐
│ ATC.Web                                                     │
│ Razor Pages UI + Minimal APIs                               │
│                                                              │
│ - Epic/story dashboard                                       │
│ - Gate 1 scenario review                                     │
│ - Gate 2 code review                                         │
│ - Run status + audit views                                   │
│ - Manual retry/reject actions                                │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│ ATC.Worker                                                  │
│ Background pipeline executor                                │
│                                                              │
│ - ingest stories                                             │
│ - prepare Cascade prompts                                    │
│ - persist generated artifacts                                │
│ - wait/resume after approvals                                │
│ - publish to repo                                            │
│ - perform dedup                                              │
│ - create/append ADO bugs                                     │
└───────────────┬───────────────────────────┬──────────────────┘
                │                           │
                ▼                           ▼
┌──────────────────────────────┐   ┌───────────────────────────┐
│ SQLite                       │   │ Workspace Filesystem      │
│                              │   │                           │
│ - runs                       │   │ - configs/agent.md        │
│ - stories                    │   │ - epics/                  │
│ - approvals                  │   │ - scenarios/              │
│ - fingerprints               │   │ - generated-tests/        │
│ - bugs                       │   │ - bug-reports/            │
│ - audit log                  │   │ - prompts/                │
└──────────────────────────────┘   └───────────────────────────┘
```

## 5. Recommended Solution Structure

```text
src/
  Atc.Web/
  Atc.Worker/
  Atc.Core/
  Atc.Infrastructure/
  Atc.Contracts/

tests/
  Atc.Core.Tests/
  Atc.Infrastructure.Tests/
  Atc.Web.Tests/
  Atc.Pipeline.Tests/

configs/
  agent.md
  agent.schema.json
  prompts/
    scenario-generation.md
    code-generation.md
    bug-hypothesis.md
  environments/
    local.json
    ci.json

workspace/
  epics/
    {epicId}/
      epic-summary.md
      stories/
        {storyId}/
          story.md
          scenario.feature
          scenario-review.json
          code-review.json
          generation/
            scenario-prompt.md
            code-prompt.md
          output/
            tests/
            logs/
            bug-report.md

data/
  atc.db

scripts/
  bootstrap.ps1
  ingest-epic.ps1
  run-pipeline.ps1
```

## 6. Core Modules

### 6.1 Atc.Web

Responsibilities:

- dashboard for epics, stories, and pipeline runs
- Gate 1 scenario review UI
- Gate 2 code review UI
- manual actions: approve, reject, retry, stop, reopen
- health, diagnostics, and audit views

Recommended UI scope:

- keep it internal-only and workflow-focused
- do not build a large custom SPA for the first version
- use server-rendered pages with targeted JS only where diffs or side-by-side comparisons need it

### 6.2 Atc.Worker

Responsibilities:

- execute pipeline jobs from a queue table
- resume work after approval events
- call ADO, git, and CI integrations
- perform duplicate checks and bug creation

Recommendation:

- start with a separate worker host even if it shares the same codebase
- this avoids tying long-running pipeline work to the web request lifecycle

### 6.3 Atc.Core

Pure application/domain logic:

- workflow state machine
- approval rules
- story eligibility rules
- scenario/code artifact metadata
- fingerprint generation
- severity classification
- duplicate matching policies

### 6.4 Atc.Infrastructure

Adapters and implementations:

- ADO client
- git/publish client
- CI result reader
- SQLite repositories
- filesystem artifact store
- prompt renderer
- agent.md loader/validator

### 6.5 Atc.Contracts

Shared DTOs and contracts:

- API request/response models
- run event models
- approval payloads
- bug report section models

## 7. Workflow State Machine

Track workflow at the **story level**. Epic runs are just grouped story runs.

Suggested states:

1. `Discovered`
2. `Eligible`
3. `Ingested`
4. `ScenarioGenerating`
5. `ScenarioGenerated`
6. `ScenarioChangesRequested`
7. `ScenarioApproved`
8. `CodeGenerating`
9. `CodeGenerated`
10. `CodeChangesRequested`
11. `CodeApproved`
12. `Publishing`
13. `Published`
14. `Executing`
15. `Passed`
16. `Failed`
17. `DuplicateDetected`
18. `BugCreated`
19. `Completed`
20. `Blocked`

Important rule:

- only `ScenarioApproved` stories may enter code generation
- only `CodeApproved` stories may publish
- `Failed` branches into dedup and bug reporting

## 8. Primary Data Model

Use SQLite tables roughly like this:

### `epics`

- `id`
- `ado_epic_id`
- `title`
- `state`
- `last_ingested_utc`

### `stories`

- `id`
- `ado_story_id`
- `epic_id`
- `title`
- `tags_json`
- `acceptance_criteria_markdown`
- `workflow_state`
- `assigned_test_stack`
- `artifact_root`
- `last_transition_utc`

### `pipeline_runs`

- `id`
- `story_id`
- `run_type`
- `status`
- `started_utc`
- `completed_utc`
- `triggered_by`

### `artifacts`

- `id`
- `story_id`
- `artifact_type`
- `path`
- `content_hash`
- `version_number`
- `created_utc`

### `approvals`

- `id`
- `story_id`
- `gate_type`
- `decision`
- `reviewer`
- `comments`
- `decided_utc`

### `fingerprints`

- `id`
- `story_id`
- `fingerprint_key`
- `class_name`
- `method_name`
- `exception_signature`
- `first_seen_utc`
- `last_seen_utc`
- `occurrence_count`

### `bugs`

- `id`
- `story_id`
- `ado_bug_id`
- `fingerprint_id`
- `similarity_score`
- `action_taken`
- `created_utc`

### `audit_events`

- `id`
- `entity_type`
- `entity_id`
- `event_type`
- `payload_json`
- `created_utc`

## 9. Filesystem Artifact Strategy

Store large or reviewable artifacts on disk, not in SQLite.

Put these on disk:

- original story snapshots
- generated `.feature` files
- generated test code
- prompt inputs/outputs
- CI logs
- structured bug reports
- diff snapshots

Put these in SQLite:

- current workflow state
- hashes
- paths
- reviewer decisions
- dedup records
- audit events

This split keeps the database small and queryable while preserving full artifact history.

## 10. API Surface

Minimal API route groups are enough for the first version.

Suggested endpoints:

### Ingestion

- `POST /api/epics/{epicId}/ingest`
- `GET /api/epics/{epicId}`
- `GET /api/epics/{epicId}/stories`

### Scenario pipeline

- `POST /api/stories/{storyId}/generate-scenarios`
- `POST /api/stories/{storyId}/scenario-approval`
- `POST /api/stories/{storyId}/scenario-regenerate`

### Code pipeline

- `POST /api/stories/{storyId}/generate-code`
- `POST /api/stories/{storyId}/code-approval`
- `POST /api/stories/{storyId}/code-regenerate`

### Publish and execution

- `POST /api/stories/{storyId}/publish`
- `POST /api/stories/{storyId}/execute`
- `GET /api/runs/{runId}`

### Failure handling

- `POST /api/runs/{runId}/deduplicate`
- `POST /api/runs/{runId}/create-bug`
- `GET /api/stories/{storyId}/bugs`

### Operations

- `GET /health/live`
- `GET /health/ready`
- `GET /api/audit/{entityType}/{entityId}`

## 11. Queue and Execution Model

Do not use a separate broker for the MVP.

Use a SQLite-backed `job_queue` table with these fields:

- `id`
- `job_type`
- `payload_json`
- `status`
- `available_utc`
- `attempt_count`
- `locked_by`
- `locked_utc`

Worker behavior:

- poll for available jobs
- acquire one job transactionally
- execute one phase at a time
- persist state transition after every phase
- enqueue follow-up jobs rather than performing the entire story run in one long transaction

This makes restart behavior and manual recovery much simpler.

## 12. Gate 1 and Gate 2 Design

### Gate 1: Scenario Review

The UI should show:

- story title and acceptance criteria
- generated `.feature` file
- traceability view: AC item -> matching scenario lines
- reviewer actions: approve, reject, request revision

Reject payload should require:

- category
- comment
- optional line references

### Gate 2: Code Review

The UI should show:

- approved `.feature` file beside generated code
- file diffs for changed tests
- target repo path
- reviewer actions: approve, reject, request revision

This second gate should confirm:

- naming conventions
- test stack selection
- maintainability
- repository placement
- missing fixtures or dependencies

## 13. Duplicate Prevention Design

### Layer 1: Fingerprint Registry

Fingerprint format:

```text
{test_class}|{test_method}|{exception_type}|{normalized_failure_site}|{story_id}
```

Normalization rules:

- trim environment-specific file paths
- trim generated line numbers where unstable
- normalize repeated whitespace
- include story ID to avoid over-collapsing unrelated failures

### Layer 2: ADO Search

Search inputs:

- bug title candidate
- normalized failure summary
- stack trace summary
- story ID
- epic ID

Scoring:

- default threshold `0.85`
- allow override in `agent.md`
- append comment to existing bug when threshold is met
- create new bug only when both layers miss

## 14. Structured Bug Report Model

Use one renderer that produces both:

- Markdown artifact for local history
- ADO-formatted content for work item creation

Recommended sections:

1. Summary
2. Failing Story and Epic
3. Environment
4. Test Type and Severity
5. Steps to Reproduce
6. Expected Result
7. Actual Result
8. Failure Evidence
9. Data Snapshot
10. Root Cause Hypotheses
11. Occurrence History

Implementation note:

- perform deterministic PII redaction before any artifact is persisted

## 15. `agent.md` Design

Treat `agent.md` as the primary policy file.

Recommended sections:

- ADO connection settings
- story eligibility rules
- scenario generation rules
- code generation rules
- review gate policies
- target repo mapping
- duplicate threshold settings
- bug report rules
- severity mapping
- security/redaction rules

Recommendation:

- parse markdown sections into a strongly typed options model
- validate at startup
- reject startup when required sections are missing
- support reload-on-change for local development only

## 16. Security and Compliance

Minimum controls:

- keep PAT and repo credentials in environment variables or secret store only
- never persist secrets into artifact files
- redact known PII patterns before writing bug artifacts
- record reviewer identity on every gate decision
- prefer PR-based publishing over direct push
- expose internal UI behind enterprise authentication if deployed centrally

## 17. Suggested MVP Delivery Order

Build in this order:

1. solution skeleton and SQLite schema
2. ADO ingestion and story workspace materialization
3. `agent.md` loader and validator
4. scenario generation job flow
5. Gate 1 UI
6. code generation job flow
7. Gate 2 UI
8. repo publish step
9. test result ingestion
10. dedup engine
11. bug report creation

This sequence matches the sprint dependencies in the planning document while keeping each increment usable.

## 18. What Not to Do in Version 1

Avoid these early:

- microservices
- distributed message brokers
- a heavy SPA frontend
- multiple databases
- real-time streaming unless reviewers truly need live updates
- AI-based PII detection for compliance-sensitive data

Those add complexity faster than they add value for the initial rollout.

## 19. Final Recommendation

If the goal is to realize the structure in the planning document with the least implementation risk, build:

- **one ASP.NET Core web app** for UI and APIs
- **one worker host** for pipeline execution
- **one SQLite database** for state and auditability
- **one workspace directory model** for all generated artifacts
- **one policy file (`agent.md`)** to drive behavior

That gives you the exact workflow the document describes: epic ingestion, BDD-first generation, two approval gates, controlled publishing, two-layer dedup, and structured bug reporting, without overengineering the first release.
