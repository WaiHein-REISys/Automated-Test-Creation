[CmdletBinding()]
param(
    [ValidateSet("prompt_only", "claude", "azure_openai", "ollama", "cli_agent")]
    [string]$Provider = "prompt_only",
    [switch]$IncludeDevTools,
    [switch]$Force,
    [string]$AdoPat,
    [string]$AdoUrl,
    [string]$ProductName = "EHB",
    [string]$TargetRepoPath,
    [string]$BranchName,
    [string]$AnthropicApiKey,
    [string]$AzureOpenAiEndpoint,
    [string]$AzureOpenAiApiKey,
    [string]$AzureOpenAiDeployment = "gpt-4o",
    [string]$AzureOpenAiApiVersion = "2024-12-01-preview",
    [string]$OllamaModel = "llama3",
    [string]$OllamaUrl = "http://localhost:11434",
    [string]$CliAgentCommand = "windsurf generate --prompt {prompt_file}"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$script:RepoRoot = Split-Path -Parent $PSCommandPath
$script:CliRoot = Join-Path $script:RepoRoot "cli"
$script:IsDotSourced = $MyInvocation.InvocationName -eq "."
$script:SupportedPyLauncherVersions = @("3.13", "3.12")
$script:SupportedPythonMessage = "Python 3.12 or 3.13"

function Write-Step {
    param([string]$Message)

    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-Info {
    param([string]$Message)

    Write-Host "  - $Message" -ForegroundColor DarkGray
}

function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,
        [string[]]$Arguments = @(),
        [string]$WorkingDirectory = $script:RepoRoot
    )

    Write-Info ("Running: " + (($FilePath) + " " + ($Arguments -join " ")).Trim())

    Push-Location $WorkingDirectory
    try {
        if ($Arguments.Count -gt 0) {
            & $FilePath @Arguments
        }
        else {
            & $FilePath
        }

        if ($LASTEXITCODE -ne 0) {
            throw "Command failed with exit code $LASTEXITCODE: $FilePath $($Arguments -join ' ')"
        }
    }
    finally {
        Pop-Location
    }
}

function Get-PythonCommand {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        foreach ($version in $script:SupportedPyLauncherVersions) {
            $launcherArg = "-$version"
            & py $launcherArg -c "import sys" 2>$null
            if ($LASTEXITCODE -eq 0) {
                return @{
                    FilePath = "py"
                    Prefix = @($launcherArg)
                }
            }
        }
    }

    foreach ($candidate in @("python", "python3")) {
        $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($cmd) {
            & $candidate -c "import sys; raise SystemExit(0 if (3, 12) <= sys.version_info[:2] < (3, 14) else 1)" 2>$null
            if ($LASTEXITCODE -eq 0) {
                return @{
                    FilePath = $candidate
                    Prefix = @()
                }
            }
        }
    }

    throw "$script:SupportedPythonMessage is required. Install a supported version and rerun this script."
}

function Resolve-SetupExtras {
    $extras = [System.Collections.Generic.List[string]]::new()

    switch ($Provider) {
        "claude" { $extras.Add("claude") }
        "azure_openai" { $extras.Add("azure-openai") }
    }

    if ($IncludeDevTools) {
        $extras.Add("dev")
    }

    return $extras.ToArray()
}

function Get-ProviderConfig {
    switch ($Provider) {
        "claude" {
            return @{
                type = "claude"
                model = "claude-sonnet-4-20250514"
                options = @{}
            }
        }
        "azure_openai" {
            return @{
                type = "azure_openai"
                model = $AzureOpenAiDeployment
                options = @{
                    endpoint = $AzureOpenAiEndpoint
                    api_version = $AzureOpenAiApiVersion
                }
            }
        }
        "ollama" {
            return @{
                type = "ollama"
                model = $OllamaModel
                options = @{}
            }
        }
        "cli_agent" {
            return @{
                type = "cli_agent"
                model = ""
                options = @{
                    command = $CliAgentCommand
                }
            }
        }
        default {
            return @{
                type = "prompt_only"
                model = ""
                options = @{}
            }
        }
    }
}

function Build-EnvFileContent {
    $adoPatValue = if ($AdoPat) { $AdoPat } else { "your-ado-personal-access-token" }
    $anthropicKeyValue = if ($AnthropicApiKey) { $AnthropicApiKey } else { "sk-ant-..." }
    $azureEndpointValue = if ($AzureOpenAiEndpoint) { $AzureOpenAiEndpoint } else { "https://your-resource-name.openai.azure.com" }
    $azureApiKeyValue = if ($AzureOpenAiApiKey) { $AzureOpenAiApiKey } else { "your-key1-or-key2-here" }
    $azureDeploymentValue = if ($AzureOpenAiDeployment) { $AzureOpenAiDeployment } else { "gpt-4o" }
    $azureApiVersionValue = if ($AzureOpenAiApiVersion) { $AzureOpenAiApiVersion } else { "2024-12-01-preview" }
    $ollamaModelValue = if ($OllamaModel) { $OllamaModel } else { "llama3" }
    $ollamaUrlValue = if ($OllamaUrl) { $OllamaUrl } else { "http://localhost:11434" }
    $cliAgentCommandValue = if ($CliAgentCommand) { $CliAgentCommand } else { "windsurf generate --prompt {prompt_file}" }
    $cliAgentCommandEnvValue = $cliAgentCommandValue.Replace('"', '\"')

    $lines = @(
        "# Azure DevOps"
        "ATC_ADO_PAT=$adoPatValue"
        ""
        "# Claude"
        "ATC_ANTHROPIC_API_KEY=$anthropicKeyValue"
        ""
        "# Azure OpenAI"
        "ATC_AZURE_OPENAI_ENDPOINT=$azureEndpointValue"
        "ATC_AZURE_OPENAI_API_KEY=$azureApiKeyValue"
        "ATC_AZURE_OPENAI_DEPLOYMENT=$azureDeploymentValue"
        "ATC_AZURE_OPENAI_API_VERSION=$azureApiVersionValue"
        ""
        "# Ollama"
        "ATC_OLLAMA_MODEL=$ollamaModelValue"
        "ATC_OLLAMA_URL=$ollamaUrlValue"
        ""
        "# CLI Agent"
        "ATC_CLI_AGENT_CMD=""$cliAgentCommandEnvValue"""
        ""
    )

    return ($lines -join [Environment]::NewLine)
}

function Ensure-EnvFile {
    $envPath = Join-Path $script:CliRoot ".env"

    if ((Test-Path $envPath) -and -not $Force) {
        Write-Info "Keeping existing .env at $envPath"
        return $envPath
    }

    Write-Step "Writing cli/.env"
    [System.IO.File]::WriteAllText($envPath, (Build-EnvFileContent))
    Write-Info "Created $envPath"
    return $envPath
}

function Ensure-RunConfig {
    $templatePath = Join-Path $script:CliRoot "configs/runs/example.json"
    $runConfigPath = Join-Path $script:CliRoot "run.json"

    if ((Test-Path $runConfigPath) -and -not $Force) {
        Write-Info "Keeping existing run.json at $runConfigPath"
        return $runConfigPath
    }

    Write-Step "Writing cli/run.json"
    $config = Get-Content -Raw -Path $templatePath | ConvertFrom-Json
    $config.url = if ($AdoUrl) { $AdoUrl } else { "https://dev.azure.com/org/project/_workitems/edit/12345" }
    $config.product_name = $ProductName
    $config.target_repo_path = if ($TargetRepoPath) { $TargetRepoPath } else { $null }
    $config.branch_name = if ($BranchName) { $BranchName } else { $null }
    $config.provider = [pscustomobject](Get-ProviderConfig)

    $json = $config | ConvertTo-Json -Depth 10
    [System.IO.File]::WriteAllText($runConfigPath, $json + [Environment]::NewLine)
    Write-Info "Created $runConfigPath"
    return $runConfigPath
}

function Invoke-SetupEnv {
    param([hashtable]$PythonCommand)

    Write-Step "Installing dependencies with cli/setup_env.py"
    $args = @()
    $args += $PythonCommand.Prefix
    $args += @("setup_env.py")

    $extras = Resolve-SetupExtras
    if ($extras.Count -gt 0) {
        $args += "--extras"
        $args += $extras
    }

    Invoke-Native -FilePath $PythonCommand.FilePath -Arguments $args -WorkingDirectory $script:CliRoot
}

function Invoke-AtcInit {
    Write-Step "Bootstrapping ATC defaults"

    $uv = Get-Command uv -ErrorAction SilentlyContinue
    if ($uv) {
        Invoke-Native -FilePath "uv" -Arguments @("run", "python", "-m", "atc", "init") -WorkingDirectory $script:CliRoot
        return
    }

    $venvPython = Join-Path $script:CliRoot ".venv/Scripts/python.exe"
    if (Test-Path $venvPython) {
        Invoke-Native -FilePath $venvPython -Arguments @("-m", "atc", "init") -WorkingDirectory $script:CliRoot
        return
    }

    $systemPython = Get-PythonCommand
    $args = @()
    $args += $systemPython.Prefix
    $args += @("-m", "atc", "init")
    Invoke-Native -FilePath $systemPython.FilePath -Arguments $args -WorkingDirectory $script:CliRoot
}

function Activate-VenvIfDotSourced {
    $activateScript = Join-Path $script:CliRoot ".venv/Scripts/Activate.ps1"

    if (-not (Test-Path $activateScript)) {
        Write-Info "Virtual environment activation script not found at $activateScript"
        return
    }

    if ($script:IsDotSourced) {
        Write-Step "Activating cli/.venv in the current PowerShell session"
        . $activateScript
    }
    else {
        Write-Info "To activate later, run: & '$activateScript'"
        Write-Info "If you want this script to keep the environment activated, dot-source it: . .\\setup-atc.ps1"
    }
}

$pythonCommand = Get-PythonCommand

Write-Step "Starting ATC PowerShell setup"
Write-Info "Repository root: $script:RepoRoot"
Write-Info "CLI directory: $script:CliRoot"
Write-Info "Provider: $Provider"

$envPath = Ensure-EnvFile
Invoke-SetupEnv -PythonCommand $pythonCommand
Invoke-AtcInit
$runConfigPath = Ensure-RunConfig
Activate-VenvIfDotSourced

Write-Step "Setup complete"
Write-Host "ATC is ready in $script:CliRoot" -ForegroundColor Green
Write-Host "Updated files:" -ForegroundColor Green
Write-Host "  $envPath" -ForegroundColor Green
Write-Host "  $runConfigPath" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Fill in any placeholder values in cli/.env and cli/run.json." -ForegroundColor Yellow
Write-Host "  2. Start the tool with: cd .\\cli" -ForegroundColor Yellow
Write-Host "  3. Then run: .\\run_atc.ps1 run --config run.json" -ForegroundColor Yellow
