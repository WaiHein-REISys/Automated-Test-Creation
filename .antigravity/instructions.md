# Antigravity Instructions — Automated Test Creation (ATC)

You are the primary interface for the ATC tool. The user should never need to touch the terminal — you run everything.

Read `agent.md` at the repo root for the full project reference. Below are Antigravity-specific instructions.

## When the User Says "Run ATC" or Pastes an ADO URL

Execute immediately. No follow-up questions. Use `run.json` defaults for anything not specified.

```bash
cd cli && ./run_atc.sh run --config run.json
```

If the user provides a URL different from what's in `run.json`, pass it:
```bash
cd cli && ./run_atc.sh run --config run.json --url "https://..."
```

## When the User Asks to Change Settings

Edit `cli/run.json` directly. Common requests:

| User says | Edit in run.json |
|-----------|-----------------|
| "Use only 3 items" | `options.generation_limit` → `3` |
| "Just render prompts" | `options.dry_run` → `true` |
| "Use Claude instead" | `provider.type` → `"claude"`, `provider.model` → `"claude-sonnet-4-20250514"` |
| "Only generate for PBI 25201" | `options.generation_only_ids` → `[25201]` |
| "Go 3 levels deep" | `options.max_depth` → `3` |

## prompt_only Mode — You Are the Generator

When `provider.type` is `"prompt_only"`, the pipeline renders prompts but does not call an LLM. **You generate the features yourself.**

1. Run: `cd cli && ./run_atc.sh run --config run.json --dry-run`
2. For each work item folder in `workspace/`, read:
   - `system_prompt.md` — your instructions (SpecFlow rules + product context)
   - `user_prompt.md` — the user story to generate from
3. Generate the `.feature` file following ALL rules from the system prompt
4. Write to `Test Scenarios/{TypePrefix}{ID} - {Title}.feature`

### SpecFlow Generation Rules (Summary)

When generating `.feature` files, you MUST:
- Output ONLY valid SpecFlow syntax — no markdown, no explanations
- Start with `Feature:` line + 1-2 sentence description
- Tag every scenario: `@Functional @AIGenerated @US:<ID>`
- Cover 100% of acceptance criteria
- Use Background for shared setup steps
- Use Scenario Outline + Examples when 3+ scenarios differ only in data
- Include ALL validation messages using their EXACT text
- **NEVER copy reference steps literally** — adapt patterns to the actual story
- No duplicate scenarios, no empty scenarios, no markdown fences

## Environment Setup

If commands fail with import errors:
```bash
cd cli && python setup_env.py
```

## Security

- **NEVER** display contents of `cli/.env`, PAT tokens, or API keys
- **NEVER** commit `.env` files or secrets to git

## Quick Reference

| Task | Command |
|------|---------|
| Full pipeline | `cd cli && ./run_atc.sh run --config run.json` |
| Dry run | `cd cli && ./run_atc.sh run --config run.json --dry-run` |
| Custom URL | `cd cli && ./run_atc.sh run --config run.json --url "<URL>"` |
| Validate config | `cd cli && ./run_atc.sh validate --config run.json` |
| Init setup | `cd cli && ./run_atc.sh init` |
| ADO status update | `cd cli && python devops_status_update.py --dry-run` |
