@echo off
REM ============================================================================
REM  EHB2010 External Test Orchestrator (Standalone)
REM
REM  Can run from ANY location. Pass --project to point at the EHB2010 root.
REM  Produces machine-readable TRX output for programmatic consumption.
REM
REM  Usage: external-runner.cmd --project C:\path\to\EHB2010 [options]
REM ============================================================================
setlocal enabledelayedexpansion

REM --- Defaults ---
set "PROJECT_ROOT="
set "CONFIG=Release"
set "FILTER="
set "RESULTS_DIR="
set "TIMESTAMP=%date:~-4%%date:~4,2%%date:~7,2%_%time:~0,2%%time:~3,2%%time:~6,2%"
set "TIMESTAMP=%TIMESTAMP: =0%"
set "RUN_ID=%TIMESTAMP%"
set "QUIET=0"
set "SKIP_BUILD=0"

REM --- Parse arguments ---
:parse_args
if "%~1"=="" goto :done_args
if /i "%~1"=="--project"     ( set "PROJECT_ROOT=%~2" & shift & shift & goto :parse_args )
if /i "%~1"=="--tag"         ( set "FILTER=Category=%~2" & shift & shift & goto :parse_args )
if /i "%~1"=="--filter"      ( set "FILTER=%~2" & shift & shift & goto :parse_args )
if /i "%~1"=="--config"      ( set "CONFIG=%~2" & shift & shift & goto :parse_args )
if /i "%~1"=="--output"      ( set "RESULTS_DIR=%~2" & shift & shift & goto :parse_args )
if /i "%~1"=="--run-id"      ( set "RUN_ID=%~2" & shift & shift & goto :parse_args )
if /i "%~1"=="--quiet"       ( set "QUIET=1" & shift & goto :parse_args )
if /i "%~1"=="--skip-build"  ( set "SKIP_BUILD=1" & shift & goto :parse_args )
if /i "%~1"=="--help"        ( goto :show_help )
if /i "%~1"=="-h"            ( goto :show_help )
shift
goto :parse_args
:done_args

REM --- Validate --project ---
if "%PROJECT_ROOT%"=="" (
    echo ERROR: --project is required. Run with --help for usage. 1>&2
    exit /b 1
)

set "CSPROJ=%PROJECT_ROOT%\EHB.UI.Automation\EHB.UI.Automation.EHB2010.csproj"
if not exist "%CSPROJ%" (
    echo ERROR: Cannot find %CSPROJ% 1>&2
    echo        Make sure --project points to the EHB2010 root directory. 1>&2
    exit /b 1
)

REM Default results dir to caller's CWD, not the project dir
if "%RESULTS_DIR%"=="" set "RESULTS_DIR=%CD%\TestResults"
if not exist "%RESULTS_DIR%" mkdir "%RESULTS_DIR%"

set "TRX_FILE=%RESULTS_DIR%\TestResults_%RUN_ID%.trx"
set "EXTENT_REPORT=%PROJECT_ROOT%\EHB.UI.Automation\bin\%CONFIG%\net8.0\Reports\ExtentReport.html"

if %QUIET% equ 0 (
    echo [external-runner] Project:  %CSPROJ%
    echo [external-runner] Filter:   %FILTER%
    echo [external-runner] Results:  %RESULTS_DIR%
    echo [external-runner] Run ID:   %RUN_ID%
)

REM --- Step 1: Build (unless skipped) ---
if %SKIP_BUILD% equ 0 (
    if %QUIET% equ 0 echo [external-runner] Building...
    dotnet build "%CSPROJ%" --configuration %CONFIG% --nologo -v q >nul 2>&1
    if %ERRORLEVEL% neq 0 (
        echo [external-runner] ERROR: Build failed 1>&2
        exit /b 1
    )
)

REM --- Step 2: Run tests with TRX logger ---
set "TEST_CMD=dotnet test "%CSPROJ%" --configuration %CONFIG% --no-build --nologo"
set "TEST_CMD=%TEST_CMD% --logger "trx;LogFileName=TestResults_%RUN_ID%.trx""
set "TEST_CMD=%TEST_CMD% --results-directory "%RESULTS_DIR%""

if not "%FILTER%"=="" (
    set "TEST_CMD=%TEST_CMD% --filter "%FILTER%""
)

if %QUIET% equ 1 (
    %TEST_CMD% >nul 2>&1
) else (
    %TEST_CMD%
)
set "TEST_EXIT=%ERRORLEVEL%"

REM --- Step 3: Output for caller ---
echo TRX_FILE=%TRX_FILE%
echo EXTENT_REPORT=%EXTENT_REPORT%
echo EXIT_CODE=%TEST_EXIT%

exit /b %TEST_EXIT%

REM ============================================================================
:show_help
echo.
echo  EHB2010 External Test Orchestrator (Standalone)
echo.
echo  Runs from any location. Point --project at the EHB2010 directory.
echo.
echo  USAGE:
echo    external-runner.cmd --project ^<path-to-EHB2010^> [options]
echo.
echo  REQUIRED:
echo    --project ^<path^>    Path to the EHB2010 project root directory
echo.
echo  OPTIONS:
echo    --tag ^<tag^>         Run scenarios by SpecFlow tag
echo    --filter ^<expr^>     dotnet test filter expression
echo    --config ^<cfg^>      Build configuration (default: Release)
echo    --output ^<dir^>      Results directory (default: .\TestResults)
echo    --run-id ^<id^>       Unique run identifier for file naming
echo    --quiet              Suppress test output (only emit result vars)
echo    --skip-build         Skip build step (if already built)
echo    -h, --help           Show this help
echo.
echo  OUTPUT:
echo    TRX_FILE=^<path^>       Absolute path to the TRX results file
echo    EXTENT_REPORT=^<path^>  Path to ExtentReport HTML
echo    EXIT_CODE=^<n^>         0 = all passed, non-zero = failures
echo.
echo  EXAMPLES:
echo    external-runner.cmd --project C:\Repos\EHB2010 --tag Automated --quiet
echo    external-runner.cmd --project ..\EHB2010 --run-id run123
echo.
exit /b 0
