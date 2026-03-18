# ATC Wiki — Automated Test Creation

Welcome to the ATC documentation wiki. ATC is a Python CLI tool that generates BDD/SpecFlow `.feature` files from Azure DevOps work items with a single command.

## Pages

| Page | Description |
|------|-------------|
| [Getting Started](Getting-Started.md) | Installation and first run on any OS |
| [Configuration](Configuration.md) | Run config (`run.json`), environment variables, and options |
| [Providers](Providers.md) | AI provider setup: Claude, Azure OpenAI, Ollama, CLI Agent, Prompt Only |
| [URL Formats](URL-Formats.md) | Supported Azure DevOps URL formats including on-prem ADS |
| [Architecture](Architecture.md) | Project structure, pipeline phases, domain models, and extension points |
| [Cross-Platform Support](Cross-Platform-Support.md) | Windows, macOS, and Linux specifics |
| [Windsurf Integration](Windsurf-Integration.md) | Running ATC through Windsurf Cascade with minimum interaction |
| [Troubleshooting](Troubleshooting.md) | Common issues and fixes |
| [Changelog](Changelog.md) | Notable changes and enhancement history |

## Design Documents

These are the original design references stored alongside the wiki:

- [CLI Design](../Automated_Test_Creation_CLI_Design.md) — single-command CLI architecture, MCP server spec, gate workflow
- [Technical Plan](../Automated_Test_Creation_Technical_Plan.md) — 3-sprint plan, success metrics, architecture overview
- [Tool Design](../Automated_Test_Creation_Tool_Design.md) — .NET modular monolith alternative, data model, state machine

## Quick Links

```bash
# Setup (any OS)
cd cli && python setup_env.py

# Run pipeline
./run_atc.sh run --config run.json                    # macOS / Linux
.\run_atc.ps1 run --config run.json                   # Windows PowerShell
run_atc.cmd run --config run.json                     # Windows CMD

# Dry run (workspace + prompts only, no AI generation)
./run_atc.sh run --config run.json --dry-run

# Override ADO URL
./run_atc.sh run --config run.json --url "https://..."
```
