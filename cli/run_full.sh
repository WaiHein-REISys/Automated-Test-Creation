#!/usr/bin/env bash
# One-shot full ATC workflow for Windsurf / bash.
# Usage:
#   ./run_full.sh --url "https://ehbads.hrsa.gov/ads/EHBs/EHBs/_workitems/edit/411599"
#   ./run_full.sh                            # uses url from run.json
#   ./run_full.sh --dry-run                  # workspace + prompts only
#   ./run_full.sh --url "..." --dry-run      # workspace + prompts for a specific URL
#   ./run_full.sh --max-depth 2              # only fetch 2 levels below root
#   ./run_full.sh --url "..." --max-depth 1  # root + direct children only
#   ./run_full.sh --run-tests                # run tests after pipeline completes
#   ./run_full.sh --run-tests --test-tag Automated  # run tests by SpecFlow tag
#   ./run_full.sh --filter-tag Automated --filter-tag SF424  # tag-based child filtering
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$SCRIPT_DIR/run_atc.sh" run --config run.json "$@"
