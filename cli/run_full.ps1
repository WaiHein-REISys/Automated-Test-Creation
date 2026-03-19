# One-shot full ATC workflow for Windsurf / PowerShell.
# Usage:
#   .\run_full.ps1 -Url "https://ehbads.hrsa.gov/ads/EHBs/EHBs/_workitems/edit/411599"
#   .\run_full.ps1                          # uses url from run.json
#   .\run_full.ps1 -DryRun                  # workspace + prompts only
#   .\run_full.ps1 -Url "..." -DryRun       # workspace + prompts for a specific URL
#   .\run_full.ps1 -MaxDepth 2              # only fetch 2 levels below root
#   .\run_full.ps1 -Url "..." -MaxDepth 1   # root + direct children only
#   .\run_full.ps1 -RunTests                # run tests after pipeline completes
#   .\run_full.ps1 -RunTests -TestTag "Automated"  # run tests by SpecFlow tag
#   .\run_full.ps1 -FilterTags "Automated","SF424"  # only include items with these tags

param(
    [string]$Url,
    [string]$Config = "run.json",
    [switch]$DryRun,
    [int]$MaxDepth = 0,
    [string[]]$FilterTags,
    [switch]$RunTests,
    [string]$TestTag,
    [string]$TestFilter
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

if ($FilterTags) {
    foreach ($tag in $FilterTags) {
        $atcArgs += @("--filter-tag", $tag)
    }
}

if ($RunTests) {
    $atcArgs += "--run-tests"
}

if ($TestTag) {
    $atcArgs += @("--test-tag", $TestTag)
}

if ($TestFilter) {
    $atcArgs += @("--test-filter", $TestFilter)
}

# Delegate to the standard wrapper
$wrapper = Join-Path $ScriptDir "run_atc.ps1"
& $wrapper @atcArgs
exit $LASTEXITCODE
