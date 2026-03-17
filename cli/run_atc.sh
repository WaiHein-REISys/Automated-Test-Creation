#!/usr/bin/env bash
# Wrapper to run ATC reliably — avoids the broken hatchling editable entry point.
# Usage: ./run_atc.sh run --config run.json
exec uv run python -m atc "$@"
