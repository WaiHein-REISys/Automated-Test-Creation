#!/bin/bash
# ============================================================================
#  EHB2010 External Test Orchestrator (Standalone)
#
#  Can run from ANY location. Pass --project to point at the EHB2010 root.
#  Produces machine-readable TRX output for programmatic consumption.
#
#  Usage: ./external-runner.sh --project /path/to/EHB2010 [options]
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT=""
CONFIG="Release"
FILTER=""
RESULTS_DIR=""
RUN_ID=$(date +"%Y%m%d_%H%M%S")
QUIET=0
SKIP_BUILD=0

show_help() {
    cat <<'HELP'
  EHB2010 External Test Orchestrator (Standalone)

  Runs from any location. Point --project at the EHB2010 directory.

  USAGE:
    ./external-runner.sh --project <path-to-EHB2010> [options]

  REQUIRED:
    --project <path>    Path to the EHB2010 project root directory
                        (contains EHB.UI.Automation/ subfolder)

  OPTIONS:
    --tag <tag>         Run scenarios by SpecFlow tag
    --filter <expr>     dotnet test filter expression
    --config <cfg>      Build configuration (default: Release)
    --output <dir>      Results directory (default: ./TestResults in CWD)
    --run-id <id>       Unique run identifier for file naming
    --quiet             Suppress test output (only emit result vars)
    --skip-build        Skip build step (if already built)
    -h, --help          Show this help

  OUTPUT:
    Prints key=value lines to stdout for the calling process:
      TRX_FILE=<path>     Absolute path to the TRX results file
      EXTENT_REPORT=<path> Path to ExtentReport HTML (if generated)
      EXIT_CODE=<n>       0 = all passed, non-zero = failures

  EXAMPLES:
    # From a completely different repo/directory
    ./external-runner.sh --project /opt/repos/EHB2010 --tag Automated --quiet
    ./external-runner.sh --project C:/Projects/EHB2010 --run-id run123
    ./external-runner.sh --project ../Enterprise-EHBsAutomation/EHB2010 --filter "FullyQualifiedName~SF424Short"
HELP
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --project)    PROJECT_ROOT="$2"; shift 2 ;;
        --tag)        FILTER="Category=$2"; shift 2 ;;
        --filter)     FILTER="$2"; shift 2 ;;
        --config)     CONFIG="$2"; shift 2 ;;
        --output)     RESULTS_DIR="$2"; shift 2 ;;
        --run-id)     RUN_ID="$2"; shift 2 ;;
        --quiet)      QUIET=1; shift ;;
        --skip-build) SKIP_BUILD=1; shift ;;
        -h|--help)    show_help ;;
        *)            shift ;;
    esac
done

# --- Validate --project ---
if [[ -z "$PROJECT_ROOT" ]]; then
    echo "ERROR: --project is required. Run with --help for usage." >&2
    exit 1
fi

# Resolve to absolute path
PROJECT_ROOT="$(cd "$PROJECT_ROOT" && pwd)"

CSPROJ="$PROJECT_ROOT/EHB.UI.Automation/EHB.UI.Automation.EHB2010.csproj"
if [[ ! -f "$CSPROJ" ]]; then
    echo "ERROR: Cannot find $CSPROJ" >&2
    echo "       Make sure --project points to the EHB2010 root directory." >&2
    exit 1
fi

# Default results dir to CWD (caller's directory), not the project dir
if [[ -z "$RESULTS_DIR" ]]; then
    RESULTS_DIR="$(pwd)/TestResults"
fi
mkdir -p "$RESULTS_DIR"
RESULTS_DIR="$(cd "$RESULTS_DIR" && pwd)"

TRX_FILE="$RESULTS_DIR/TestResults_${RUN_ID}.trx"
EXTENT_REPORT="$PROJECT_ROOT/EHB.UI.Automation/bin/$CONFIG/net8.0/Reports/ExtentReport.html"

if [[ $QUIET -eq 0 ]]; then
    echo "[external-runner] Project:  $CSPROJ"
    echo "[external-runner] Filter:   ${FILTER:-<all>}"
    echo "[external-runner] Results:  $RESULTS_DIR"
    echo "[external-runner] Run ID:   $RUN_ID"
fi

# --- Build (unless skipped) ---
if [[ $SKIP_BUILD -eq 0 ]]; then
    [[ $QUIET -eq 0 ]] && echo "[external-runner] Building..."
    dotnet build "$CSPROJ" --configuration "$CONFIG" --nologo -v q > /dev/null 2>&1
fi

# --- Run tests ---
TEST_ARGS=(
    dotnet test "$CSPROJ"
    --configuration "$CONFIG"
    --no-build
    --nologo
    --logger "trx;LogFileName=TestResults_${RUN_ID}.trx"
    --results-directory "$RESULTS_DIR"
)

if [[ -n "$FILTER" ]]; then
    TEST_ARGS+=(--filter "$FILTER")
fi

set +e
if [[ $QUIET -eq 1 ]]; then
    "${TEST_ARGS[@]}" > /dev/null 2>&1
else
    "${TEST_ARGS[@]}"
fi
TEST_EXIT=$?
set -e

# --- Output for caller ---
echo "TRX_FILE=$TRX_FILE"
echo "EXTENT_REPORT=$EXTENT_REPORT"
echo "EXIT_CODE=$TEST_EXIT"

exit $TEST_EXIT
