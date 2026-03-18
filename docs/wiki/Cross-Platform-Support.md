# Cross-Platform Support

ATC runs on Windows, macOS, and Linux. This page documents platform-specific behavior and the tooling that enables cross-platform support.

## Setup scripts

| Script | Platform | Location | Purpose |
|--------|----------|----------|---------|
| `setup_env.py` | All | `cli/` | Installs dependencies. Uses uv if available, falls back to venv + pip. |
| `setup-atc.ps1` | Windows | repo root | One-shot PowerShell setup: installs deps, runs init, creates `.env` and `run.json`. |

### `setup_env.py` behavior by platform

| Step | uv available | uv unavailable |
|------|-------------|----------------|
| Python check | Verifies 3.12 or 3.13 | Same |
| Environment | `uv sync --python 3.12` | `python -m venv .venv` + `pip install -e .` |
| `.env` creation | Copies `.env.example` if `.env` doesn't exist | Same |
| Activation hint | `uv run python -m atc` | Platform-specific activate command |

### `setup-atc.ps1` options

```powershell
.\setup-atc.ps1 -Provider prompt_only              # basic setup
.\setup-atc.ps1 -Provider claude -IncludeDevTools   # claude + dev tools
.\setup-atc.ps1 -AdoPat "token" -AdoUrl "https://..." -Force  # full setup, overwrite existing
```

Parameters: `-Provider`, `-IncludeDevTools`, `-Force`, `-AdoPat`, `-AdoUrl`, `-ProductName`, `-TargetRepoPath`, `-BranchName`, plus provider-specific keys (`-AnthropicApiKey`, `-AzureOpenAiEndpoint`, etc.).

Dot-source the script to keep the venv activated: `. .\setup-atc.ps1 -Provider prompt_only`

## Run wrapper scripts

All wrappers follow the same fallback chain:

1. Try `uv run python -m atc`
2. Try `.venv/bin/python -m atc` (or `.venv\Scripts\python.exe` on Windows)
3. Try system `python3`/`python` (with version check for 3.12–3.13)
4. On Windows: try the `py` launcher with `-3.13` and `-3.12`
5. Error if nothing found

| Script | Platform | Usage |
|--------|----------|-------|
| `run_atc.sh` | macOS / Linux | `./run_atc.sh run --config run.json` |
| `run_atc.ps1` | Windows PowerShell | `.\run_atc.ps1 run --config run.json` |
| `run_atc.cmd` | Windows CMD | `run_atc.cmd run --config run.json` |
| `run_full.sh` | macOS / Linux | `./run_full.sh --url "https://..."` (shortcut) |
| `run_full.ps1` | Windows PowerShell | `.\run_full.ps1 -Url "https://..."` (shortcut) |

## Git client

`cli/atc/infra/git.py` finds the git executable cross-platform:

1. `shutil.which("git")` — standard PATH lookup (works on all OSes)
2. On Windows, if git isn't on PATH, checks common install locations:
   - `C:\Program Files\Git\cmd\git.exe`
   - `C:\Program Files (x86)\Git\cmd\git.exe`
3. Raises `FileNotFoundError` with a clear message if git isn't found

## Environment variables

Setting environment variables differs by platform:

```bash
# Linux / macOS (bash/zsh)
export ATC_ADO_PAT="your-pat-token"

# Windows PowerShell
$env:ATC_ADO_PAT = "your-pat-token"

# Windows CMD
set ATC_ADO_PAT=your-pat-token
```

**Recommended:** Use the `.env` file instead, which works identically on all platforms. It is loaded automatically by Pydantic Settings.

## Path handling

ATC uses `pathlib.Path` throughout, which handles Windows backslash vs. Unix forward-slash differences automatically. The workspace builder sanitizes folder and file names by replacing `<>:"/\|?*` with hyphens, ensuring valid paths on all OSes.

## Known platform issues

### Windows: `uv` may not work

If `uv` fails on Windows, `setup_env.py` automatically falls back to `venv + pip`. You can also install manually:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

### Windows: PowerShell execution policy

If `.ps1` scripts are blocked:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Or bypass for a single session:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

### Windows: `ModuleNotFoundError`

Always use `python -m atc` or wrapper scripts. Never use `uv run atc` — the hatchling editable install `.pth` files aren't reliably processed on Windows.

### macOS: `python` vs `python3`

On macOS, `python` may point to an older system Python. The wrapper scripts check `python3` first. Use `setup_env.py` which handles this automatically.

## Future enhancements

- Docker container for fully reproducible cross-platform execution
- GitHub Actions CI matrix testing (Windows, macOS, Ubuntu)
- Homebrew formula for macOS
- Windows MSI or Chocolatey package
