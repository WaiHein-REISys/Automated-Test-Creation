# Automated Test Creation — Technical Planning Document

**AI-Driven BDD Test Generation via Windsurf FedRAMP + Azure DevOps**
**Engineering Initiative | 2025**

---

## 1. Objective

Automate end-to-end BDD test creation from Azure DevOps User Stories by integrating an ADO MCP server with the Windsurf FedRAMP-compliant IDE and its Cascade agentic engine. The system generates Gherkin scenarios and test code while maintaining dual human approval gates, two-layer duplicate prevention, and structured bug reporting — all governed by a centralized `agent.md` configuration.

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        AZURE DEVOPS (ADO)                           │
│  ┌──────────┐  ┌───────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  Epics   │  │  Stories  │  │  Bug Items   │  │   Tags       │  │
│  └────┬─────┘  └─────┬─────┘  └──────┬───────┘  └──────┬───────┘  │
└───────┼──────────────┼───────────────┼──────────────────┼──────────┘
        │              │               ▲                  ▲
        ▼              ▼               │                  │
┌───────────────────────────────────────────────────────────────────┐
│                    ADO MCP SERVER                                  │
│  REST API + PAT Auth │ Read Stories │ Update Tags │ Create Bugs   │
└───────────────────────────┬───────────────────────────────────────┘
                            │
                            ▼
┌───────────────────────────────────────────────────────────────────┐
│              WINDSURF FedRAMP IDE + CASCADE AGENT                  │
│                                                                    │
│  ┌─────────────┐    ┌──────────────┐    ┌──────────────────────┐  │
│  │  agent.md   │───▶│  Scenario    │───▶│  Test Code           │  │
│  │  (Config)   │    │  Generator   │    │  Generator           │  │
│  └─────────────┘    │  (Gherkin)   │    │  (xUnit/Cypress/PW)  │  │
│                     └──────┬───────┘    └──────────┬───────────┘  │
│                            │                       │               │
│                     ┌──────▼───────┐        ┌──────▼───────┐      │
│                     │   GATE 1     │        │   GATE 2     │      │
│                     │  QA Review   │        │  Code Review  │      │
│                     └──────────────┘        └──────┬───────┘      │
└─────────────────────────────────────────────────────┼─────────────┘
                                                      │
                            ┌─────────────────────────▼─────────────┐
                            │       UPLOAD & CI PIPELINE             │
                            │  Commit → CI Run → Test Execution      │
                            └─────────────────────┬─────────────────┘
                                                  │ (on failure)
                            ┌─────────────────────▼─────────────────┐
                            │      DUPLICATE PREVENTION              │
                            │  Layer 1: Fingerprint Registry         │
                            │  Layer 2: ADO Work Item Search         │
                            │           (Levenshtein ≥ 85%)          │
                            └─────────────────────┬─────────────────┘
                                                  │ (no match)
                            ┌─────────────────────▼─────────────────┐
                            │    STRUCTURED BUG REPORT (11 Sections) │
                            │  Auto-Severity │ ADO Bug Creation      │
                            └───────────────────────────────────────┘
```

---

## 3. Sprint Breakdown

### Sprint 1 — Foundation (Week 1)

**Goal:** Establish all infrastructure, integrations, and schemas needed before pipeline execution.

| ID | Task | Points | Priority | Technical Notes |
|---|---|---|---|---|
| ATC-001 | ADO REST API ingestion script | 8 | Critical | PowerShell/Python; PAT auth; WIQL query by Epic; tag-based filtering |
| ATC-002 | Local story storage schema | 3 | High | Markdown templates: `epic_summary.md`, `story_{ID}.md` |
| ATC-003 | ADO MCP Server connector | 5 | Critical | MCP protocol for Cascade ↔ ADO; CRUD on work items + tags |
| ATC-004 | Author agent.md configuration | 5 | Critical | Workflow steps, BDD rules, output schema, approval gates, env var refs |
| ATC-005 | agent.md validation service | 5 | High | Parse + validate on startup; hot-reload; descriptive error messages |
| ATC-006 | Repo structure & CI pipeline | 3 | Critical | Azure Pipelines; monorepo: configs/, scenarios/, tests/, logs/, scripts/ |
| ATC-007 | Environment variable contracts | 2 | High | `.env.template` + validation script; REPO_URL, TARGET_PATH, ADO_PAT, etc. |
| ATC-008 | BDD scenario output schema | 3 | Critical | Gherkin conventions; @story-{ID} @epic-{N} tags; edge case rules |
| ATC-009 | Cascade prompt templates | 5 | Critical | Context window strategy; token budget; response parsing contracts |

**Sprint 1 Total: 39 Story Points | 9 Tasks**

**Exit Criteria:**
- Ingestion script fetches & filters stories correctly for a real Epic
- MCP server reads/writes ADO items without auth failures
- agent.md reviewed & approved by QA Lead
- CI pipeline runs on push with linting and test framework passing
- Prompt templates produce consistent Gherkin for 3+ sample stories

---

### Sprint 2 — Core Pipeline (Week 2)

**Goal:** Build the complete generation pipeline with human gates, upload automation, and duplicate prevention.

| ID | Task | Points | Priority | Technical Notes |
|---|---|---|---|---|
| ATC-010 | BDD scenario generation engine | 8 | Critical | Cascade reads story + epic context; outputs `.feature` per story |
| ATC-011 | Gate 1 — scenario review workflow | 5 | Critical | Approve/reject UI; feedback loop; blocks code gen until approved |
| ATC-012 | Test code generation engine | 8 | Critical | xUnit (.NET), Cypress/Playwright (Angular), TestContainers (MSSQL) |
| ATC-013 | Gate 2 — code review workflow | 5 | High | Diff viewer; approve/reject; blocks upload until approved |
| ATC-014 | Upload & repo commit script | 5 | Critical | Env-var driven; PR or direct push; tags ADO story on success |
| ATC-015 | Layer 1 — fingerprint registry | 5 | Critical | JSON/SQLite; fingerprint = class + method + exception + Story ID |
| ATC-016 | Layer 2 — ADO duplicate search | 5 | High | WIQL + Levenshtein ≥ 85%; append comment on match |
| ATC-017 | Pilot end-to-end run | 5 | Critical | Full pipeline on one Epic; validates all integration points |

**Sprint 2 Total: 46 Story Points | 8 Tasks**

**Exit Criteria:**
- Scenarios generated for pilot Epic with full AC coverage
- Both gates (approve/reject) functional with feedback
- Test code compiles and references real project types
- Upload commits to repo and tags ADO story
- Dedup catches at least one simulated duplicate
- Pilot Epic fully processed end-to-end

---

### Sprint 3 — Validation & Bug Reporting (Week 3)

**Goal:** Complete bug reporting subsystem, validate pipeline accuracy, document everything, and plan next iteration.

| ID | Task | Points | Priority | Technical Notes |
|---|---|---|---|---|
| ATC-018 | Structured bug report generator | 8 | Critical | 11 sections with anchored headings; PII redaction on Data Snapshot |
| ATC-019 | Severity auto-classification | 5 | High | Rules by test layer: integration→Sev1, unit/service→Sev2, utility→Sev3, UI→Sev4 |
| ATC-020 | Occurrence history tracking | 3 | Medium | Extends fingerprint registry; first seen / count / last seen |
| ATC-021 | Pipeline integration test suite | 5 | High | Covers all 5 phases; ≥2 test cases per phase |
| ATC-022 | Dedup accuracy validation | 3 | High | Run against real ADO backlog; measure FP/FN rates; tune threshold |
| ATC-023 | Comprehensive pilot report | 3 | High | Metrics + samples + recommendations; exportable as PDF |
| ATC-024 | agent.md configuration guide | 3 | Medium | Section-by-section walkthrough; examples; validation checklist |
| ATC-025 | Retrospective & next iteration | 3 | High | ≥3 config refinements; rank 3-5 next Epics |

**Sprint 3 Total: 33 Story Points | 8 Tasks**

**Exit Criteria:**
- Bug reports created with all 11 sections populated in ADO
- Severity auto-assigned correctly by test layer
- Integration tests cover all 5 pipeline phases and pass
- 85% Levenshtein threshold validated against real backlog
- Pilot report exported as PDF
- 3-5 next Epics identified and ranked for rollout

---

## 4. Dependency Graph

```
ATC-001 (Ingestion) ─────────────────────────────┐
ATC-002 (Storage Schema) ────────────────────────┐│
ATC-003 (MCP Server) ──────────────────────────┐ ││
ATC-004 (agent.md) ──┬─── ATC-005 (Validation) │ ││
                     ├─── ATC-008 (BDD Schema)  │ ││
                     └─── ATC-009 (Prompts) ────┼─┼┤
ATC-006 (Repo/CI) ──────── ATC-015 (Layer 1) ──┤ ││
ATC-007 (Env Vars) ──────── ATC-014 (Upload) ──┤ ││
                                                │ ││
         ┌──────────────────────────────────────┘ ││
         │  ATC-010 (Scenario Engine) ◄───────────┘│
         │       │                                  │
         │  ATC-011 (Gate 1) ◄──────────────────────┘
         │       │
         │  ATC-012 (Code Gen Engine)
         │       │
         │  ATC-013 (Gate 2)
         │       │
         │  ATC-014 (Upload) ◄─── ATC-007
         │       │
         │  ATC-015 (Fingerprint) ◄─── ATC-006
         │       │
         │  ATC-016 (ADO Search) ◄─── ATC-003
         │       │
         │  ATC-017 (Pilot E2E) ◄─── ATC-014 + ATC-015 + ATC-016
         │
         │  ─── Sprint 3 ───
         │
         │  ATC-018 (Bug Reports) ◄─── ATC-016
         │  ATC-019 (Severity) ◄─── ATC-018
         │  ATC-020 (Occurrence) ◄─── ATC-015 + ATC-018
         │  ATC-021 (Integration Tests) ◄─── ATC-017
         │  ATC-022 (Dedup Validation) ◄─── ATC-016 + ATC-017
         │  ATC-023 (Pilot Report) ◄─── ATC-021 + ATC-022
         │  ATC-025 (Retro) ◄─── ATC-023
```

---

## 5. Technology Stack & Dependencies

### Core Toolchain

| Component | Technology | Rationale |
|---|---|---|
| IDE & AI Engine | Windsurf FedRAMP IDE + Cascade Agent | FedRAMP compliance for regulated environments; agentic workflow execution |
| Work Tracking | Azure DevOps REST API + MCP Server | Native integration with existing ADO boards; MCP enables Cascade ↔ ADO communication |
| Agent Configuration | `agent.md` (Markdown) | Externalizes behavior; non-engineer maintainable; zero IDE reconfiguration on change |

### Backend Test Stack (.NET)

| Component | Technology | Rationale |
|---|---|---|
| Unit Tests | xUnit | .NET ecosystem standard; attribute-based test discovery; parallel execution |
| Integration Tests | xUnit + TestContainers | Containerized MSSQL instances; disposable per-test-class; real DB fidelity |
| Mocking | Moq / NSubstitute | Interface-based mocking aligned with DI registrations |
| Assertions | FluentAssertions | Readable assertion syntax; better failure messages for bug reports |

### Frontend Test Stack (Angular)

| Component | Technology | Rationale |
|---|---|---|
| E2E Tests | Cypress or Playwright | Cross-browser support; network stubbing; visual diff capability |
| Component Tests | Cypress Component Testing | Isolated Angular component rendering; Tailwind-compatible |
| API Mocking | cy.intercept / Playwright route | Deterministic API responses for consistent test execution |

### Infrastructure

| Component | Technology | Rationale |
|---|---|---|
| CI Pipeline | Azure Pipelines | Native ADO integration; YAML-based; agent pool compatible |
| Dedup Registry | SQLite (recommended) | Concurrent CI run safe; cross-machine via shared mount; queryable |
| Authentication | ADO PAT (service account pending) | Scoped permissions; audit trail; env-var injected |
| Version Control | Git + Azure Repos | PR-based upload for audit trail (recommended over direct push) |

---

## 6. Key Technical Decisions

### 6.1 Epic-Driven Batching

Stories are ingested per Epic rather than individually. This gives Cascade full feature context across related stories, which improves scenario coherence and reduces redundant test coverage. The ingestion script uses WIQL queries filtered by `Ready for Development` tag and excludes `Test Creation Done` to prevent re-processing.

**Technical reasoning:** Feeding isolated stories produces scenarios that miss cross-story preconditions. Epic-level context allows the AI to recognize shared setup steps, avoid overlapping test coverage, and derive edge cases that span multiple ACs across stories.

### 6.2 BDD-First Two-Stage Generation

Gherkin scenarios are generated *before* test code, with a human gate between them. This separation exists because reviewing plain-English `.feature` files has a much lower expertise barrier than reviewing C# or TypeScript. QA engineers who cannot read code can still validate scenario completeness and AC alignment.

**Technical reasoning:** If scenarios and code were generated simultaneously, the review surface area doubles and requires both QA and dev expertise in a single gate. Separating them creates a low-friction first gate (QA reviews English) and a focused second gate (dev reviews code against already-approved scenarios).

### 6.3 Two-Layer Duplicate Prevention

Layer 1 (code-side fingerprinting) catches structural duplicates before any network call. Layer 2 (ADO search) catches manually-filed bugs that share the same root cause but have different titles. The 85% Levenshtein threshold balances recall against false positives.

**Technical reasoning:** ADO's built-in search is title-based and misses bugs filed under different phrasing. Code-side fingerprinting is deterministic but can't see manually-created items. The two layers are complementary: Layer 1 handles high-frequency CI failures cheaply; Layer 2 handles the long tail of human-filed bugs.

### 6.4 Structured Bug Reports (11 Sections)

Bug reports are intentionally over-specified at creation time. Each section targets a specific audience: QA gets reproduction steps and environment context; SWE gets stack traces, data snapshots, and root cause hypotheses. This eliminates the "can you give me more info" cycle.

**Technical reasoning:** The mean time to resolution (MTTR) bottleneck is not the fix — it's the investigation. By front-loading all diagnostic data into the initial bug report, the first engineer who opens the item can start debugging immediately. The root cause hypotheses (AI-generated from stack context) further compress the investigation phase.

---

## 7. Risk Register

| Risk | Impact | Mitigation |
|---|---|---|
| ADO PAT permissions insufficient for bug creation | Pipeline halts at bug reporting | Validate PAT scopes in Sprint 1; document minimum required permissions |
| Cascade prompt drift producing inconsistent Gherkin | Scenario quality degrades over time | agent.md enforces strict formatting; prompt templates version-controlled |
| 85% Levenshtein threshold too aggressive/lenient | False positives flood backlog or duplicates slip through | Sprint 3 spike (ATC-022) validates threshold against real data before go-live |
| TestContainers MSSQL startup time slows CI | Integration tests timeout | Configure container reuse; parallelize test classes; set generous CI timeout |
| FedRAMP compliance constraints limit Cascade capabilities | Reduced AI quality in regulated environment | Validate all prompt templates within FedRAMP boundary in Sprint 1 |
| agent.md becomes stale as workflow evolves | Agents behave incorrectly | Assign maintainer (QA Lead); version-control with PR reviews |

---

## 8. Open Decisions

| # | Decision | Options | Recommendation | Owner |
|---|---|---|---|---|
| 1 | PAT Strategy | Dedicated service-account PAT vs. scoped developer PATs | Service-account PAT for auditability | Engineering Lead + IAM |
| 2 | Branch Strategy | PR-based upload vs. direct branch push | PR-based for audit trail | Engineering Lead |
| 3 | Dedup Storage | JSON file vs. SQLite | SQLite for concurrent CI safety | Engineering Lead |
| 4 | Similarity Threshold | Fixed 85% vs. per-project tunable | Per-project tunable with 85% default | QA Lead |
| 5 | PII Redaction | Regex-based vs. AI-classified | Regex for deterministic compliance | Security + QA Lead |
| 6 | Test Framework Scope | xUnit only vs. xUnit + Cypress + Playwright | Full stack coverage from Sprint 2 | Engineering Lead |
| 7 | agent.md Ownership | QA Lead vs. Engineering Lead | QA Lead (primary consumer) | Team decision |

---

## 9. Success Metrics

| Metric | Target | Measurement |
|---|---|---|
| Time from story ready → test coverage | < 2 hours (from days) | ADO tag timestamps |
| BDD scenario AC coverage | ≥ 95% of acceptance criteria mapped | Manual audit per sprint |
| Generated test compilation rate | 100% compile on first generation | CI build results |
| Duplicate bug reduction | ≥ 80% fewer duplicates in ADO backlog | Pre/post comparison over 2 sprints |
| Bug report MTTR improvement | ≥ 30% reduction | ADO work item analytics |
| Gate 1 first-pass approval rate | ≥ 70% (improving over time) | Gate 1 approve/reject ratio |

---

*This document is a living reference. All decisions, thresholds, and workflow rules are subject to team review and retrospective refinement.*
