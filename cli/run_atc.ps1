# PowerShell wrapper to run ATC on Windows.
# Usage: .\run_atc.ps1 run --config run.json
#        .\run_atc.ps1 run --config run.json --dry-run

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# Ensure the atc package is importable even if the editable .pth has a stale path
$env:PYTHONPATH = "$PSScriptRoot" + [IO.Path]::PathSeparator + $env:PYTHONPATH

$supportedPyLauncherVersions = @("3.13", "3.12")
$supportedPythonMessage = "Python 3.12 or 3.13"

function Test-SupportedPythonCommand {
    param(
        [string]$FilePath,
        [string[]]$Prefix = @()
    )

    & $FilePath @Prefix -c "import sys; raise SystemExit(0 if (3, 12) <= sys.version_info[:2] < (3, 14) else 1)" 2>$null
    return $LASTEXITCODE -eq 0
}

# Prefer uv if available
$uv = Get-Command uv -ErrorAction SilentlyContinue

if ($uv) {
    & uv run python -m atc @args
    exit $LASTEXITCODE
}

# Fallback: use the venv Python directly
$venvPython = Join-Path $PSScriptRoot ".venv" "Scripts" "python.exe"

if (Test-Path $venvPython) {
    & $venvPython -m atc @args
    exit $LASTEXITCODE
}

# Last resort: system Python
$sysPython = Get-Command python -ErrorAction SilentlyContinue
if ($sysPython -and (Test-SupportedPythonCommand -FilePath "python")) {
    Write-Warning "No virtual environment found. Run 'python setup_env.py' first for a clean install."
    & python -m atc @args
    exit $LASTEXITCODE
}

if (Get-Command py -ErrorAction SilentlyContinue) {
    foreach ($version in $supportedPyLauncherVersions) {
        $launcherArg = "-$version"
        if (Test-SupportedPythonCommand -FilePath "py" -Prefix @($launcherArg)) {
            Write-Warning "No virtual environment found. Run 'python setup_env.py' first for a clean install."
            & py $launcherArg -m atc @args
            exit $LASTEXITCODE
        }
    }
}

Write-Error "$supportedPythonMessage was not found. Install a supported version and run 'python setup_env.py'."
exit 1
