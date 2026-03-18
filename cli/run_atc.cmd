@echo off
REM Windows CMD wrapper to run ATC.
REM Usage: run_atc.cmd run --config run.json
REM        run_atc.cmd run --config run.json --dry-run

REM Change to script directory so uv can find pyproject.toml
cd /d "%~dp0"

REM Ensure the atc package is importable even if the editable .pth has a stale path
set "PYTHONPATH=%~dp0;%PYTHONPATH%"

REM Prefer uv if available
where uv >nul 2>&1
if %ERRORLEVEL% equ 0 (
    uv run python -m atc %*
    exit /b %ERRORLEVEL%
)

REM Fallback: use the venv Python directly
if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" -m atc %*
    exit /b %ERRORLEVEL%
)

REM Last resort: system Python
python -c "import sys; raise SystemExit(0 if (3, 12) <= sys.version_info[:2] < (3, 14) else 1)" >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo WARNING: No virtual environment found. Run 'python setup_env.py' first.
    python -m atc %*
    exit /b %ERRORLEVEL%
)

py -3.13 -c "import sys" >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo WARNING: No virtual environment found. Run 'python setup_env.py' first.
    py -3.13 -m atc %*
    exit /b %ERRORLEVEL%
)

py -3.12 -c "import sys" >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo WARNING: No virtual environment found. Run 'python setup_env.py' first.
    py -3.12 -m atc %*
    exit /b %ERRORLEVEL%
)

echo ERROR: Python 3.12 or 3.13 not found. Install a supported version and run 'python setup_env.py'.
exit /b 1
