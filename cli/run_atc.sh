#!/usr/bin/env bash
# Cross-platform wrapper to run ATC on macOS / Linux.
# Usage: ./run_atc.sh run --config run.json
#        ./run_atc.sh run --config run.json --dry-run
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Prefer uv if available
if command -v uv &>/dev/null; then
    exec uv run python -m atc "$@"
fi

# Fallback: use the venv Python directly
VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python"
if [ -x "$VENV_PYTHON" ]; then
    exec "$VENV_PYTHON" -m atc "$@"
fi

# Last resort: system python3/python
for PY in python3 python; do
    if command -v "$PY" &>/dev/null; then
        if "$PY" -c 'import sys; raise SystemExit(0 if (3, 12) <= sys.version_info[:2] < (3, 14) else 1)' >/dev/null 2>&1; then
            echo "WARNING: No virtual environment found. Run 'python setup_env.py' first." >&2
            exec "$PY" -m atc "$@"
        fi
    fi
done

echo "ERROR: Python 3.12 or 3.13 not found. Install a supported version and run 'python setup_env.py'." >&2
exit 1
