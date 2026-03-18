# One-shot full ATC workflow for Windsurf / PowerShell.
# Usage:
#   .\run_full.ps1 -Url "https://ehbads.hrsa.gov/ads/EHBs/EHBs/_workitems/edit/411599"
#   .\run_full.ps1                          # uses url from run.json
#   .\run_full.ps1 -DryRun                  # workspace + prompts only
#   .\run_full.ps1 -Url "..." -DryRun       # workspace + prompts for a specific URL
#   .\run_full.ps1 -MaxDepth 2              # only fetch 2 levels below root
#   .\run_full.ps1 -Url "..." -MaxDepth 1   # root + direct children only

param(
    [string]$Url,
    [string]$Config = "run.json",
    [switch]$DryRun,
    [int]$MaxDepth = 0
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $PSCommandPath

# Build the argument list
$atcArgs = @("run", "--config", $Config)

if ($Url) {
    $atcArgs += @("--url", $Url)
}

if ($DryRun) {
    $atcArgs += "--dry-run"
}

if ($MaxDepth -gt 0) {
    $atcArgs += @("--max-depth", $MaxDepth)
}

# Delegate to the standard wrapper
$wrapper = Join-Path $ScriptDir "run_atc.ps1"
& $wrapper @atcArgs
exit $LASTEXITCODE
