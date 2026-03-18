# Troubleshooting

Common issues and their solutions.

## Installation issues

### `ModuleNotFoundError: No module named 'atc'`

**Cause:** hatchling editable installs via `uv` don't reliably process `.pth` files.

**Fix:** Always use `python -m atc` or the wrapper scripts:

```bash
# These always work:
./run_atc.sh run --config run.json          # macOS / Linux
.\run_atc.ps1 run --config run.json         # Windows PowerShell
run_atc.cmd run --config run.json           # Windows CMD
uv run python -m atc run --config run.json  # Direct

# This may fail — do not use:
uv run atc run --config run.json
```

### `uv` not working on Windows

**Cause:** `uv` may not install correctly or may not be on PATH on some Windows environments.

**Fix:** Use the pip fallback:

```bash
python setup_env.py    # auto-detects and uses pip if uv is unavailable
```

Or install manually:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m atc --help
```

### PowerShell execution policy error

**Cause:** Windows blocks `.ps1` scripts by default.

**Fix:**

```powershell
# For current user (persistent):
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned

# For current session only:
Set-ExecutionPolicy -Scope Process Bypass
```

### `Python not found` or wrong version

**Cause:** Wrapper scripts require Python 3.12 or 3.13.

**Fix:**
- Install Python 3.12 or 3.13 from [python.org](https://www.python.org/downloads/)
- On Windows, the wrapper scripts also check the `py` launcher (`py -3.13`, `py -3.12`)
- Verify: `python --version` or `python3 --version`

### `git executable not found`

**Cause:** Git is not installed or not on PATH.

**Fix:**
- Install Git from [git-scm.com](https://git-scm.com/downloads)
- On Windows, the git client checks common install paths (`C:\Program Files\Git\cmd\git.exe`) automatically
- Verify: `git --version`

## Configuration issues

### `Error: No ADO URL provided`

**Cause:** Neither `--url` flag nor `url` field in `run.json` is set.

**Fix:** Either:
- Add `"url": "https://..."` to your `run.json`
- Pass `--url "https://..."` on the command line

### `Cannot parse ADO URL` / `Unrecognized ADO URL format`

**Cause:** The URL doesn't match any known format.

**Fix:**
- Check the URL contains `_workitems/edit/{id}`, `_backlogs/...?workitem={id}`, or `_queries/...?workitem={id}`
- For on-prem ADS URLs, ensure at least two path segments before `_workitems` (collection and project)
- See [URL Formats](URL-Formats.md) for all supported patterns

### `Cannot parse on-premises ADS URL`

**Cause:** The on-prem URL doesn't have enough path segments before the ADO marker.

**Fix:** The URL must have at least `/{collection}/{project}/_workitems/...`. Example:
```
https://myserver.com/tfs/DefaultCollection/MyProject/_workitems/edit/123
                     ^^^^^^^^^^^^^^^^^^^^ ^^^^^^^^^
                     collection           project
```

### `Config file not found`

**Cause:** The `--config` path doesn't exist.

**Fix:** Create it with `python -m atc init` or specify the correct path.

### `Invalid config`

**Cause:** JSON syntax error or invalid field values.

**Fix:** Validate with `./run_atc.sh validate --config run.json` to see the specific error.

### `400 Bad Request` — REST API version out of range

**Cause:** Your on-prem Azure DevOps Server supports an older API version than ATC's default (7.1).

**Error message:**
```
Client Error '400 bad request' for URL
"The requested REST API version of 7.1 is out of range for this server.
The latest REST API version this server supports is 7.0."
```

**Fix (option 1 — automatic):** ATC now auto-detects the server's supported API version by default. If you're seeing this error on an older build, update to the latest ATC code.

**Fix (option 2 — explicit version in run.json):**
```json
{
  "url": "https://ehbads.hrsa.gov/ads/EHBs/EHBs/_workitems/edit/411599",
  "ado_api_version": "7.0",
  ...
}
```

**Fix (option 3 — environment variable):**
```bash
# .env
ATC_ADO_API_VERSION=7.0
```

```powershell
# PowerShell
$env:ATC_ADO_API_VERSION = "7.0"
```

The env var takes precedence over `run.json`. Set to `"auto"` (default) to let ATC probe the server.

## Runtime issues

### `ATC_ADO_PAT environment variable is not set`

**Cause:** The ADO PAT is not configured.

**Fix:** Set it in `cli/.env`:
```
ATC_ADO_PAT=your-token-here
```

Or export it:
```bash
export ATC_ADO_PAT="your-token"
```

### `401 Unauthorized` from ADO API

**Cause:** Invalid or expired PAT, or insufficient permissions.

**Fix:**
- Verify the PAT is valid and not expired
- Ensure the PAT has **Work Items: Read** scope
- For on-prem ADS, verify the PAT works for the target collection
- Check `ATC_ADO_PAT` doesn't have extra whitespace or quotes

### `404 Not Found` from ADO API

**Cause:** The work item ID doesn't exist, or the org/project is wrong.

**Fix:**
- Verify the URL opens correctly in a browser
- Check the work item ID exists in the target project
- For on-prem ADS, verify the collection and project names match the URL

### Provider-specific errors

#### Claude: `AuthenticationError`

Set `ATC_ANTHROPIC_API_KEY` in `.env`. Install extras: `python setup_env.py --extras claude`.

#### Azure OpenAI: `endpoint is required`

Set all three: `ATC_AZURE_OPENAI_ENDPOINT`, `ATC_AZURE_OPENAI_API_KEY`, `ATC_AZURE_OPENAI_DEPLOYMENT`.

#### Ollama: `Connection refused`

Ensure Ollama is running: `ollama serve` or check the service is started. Verify `ATC_OLLAMA_URL` (default: `http://localhost:11434`).

#### CLI Agent: `command failed`

Verify the command template works: replace `{prompt_file}` with a real file path and run it manually.

### Empty `.feature` files

**Cause:** The provider returned empty content, or the `prompt_only` provider was used.

**Fix:**
- Check provider logs for errors
- Verify the prompt renders correctly (check `scenario_prompt.md` in the workspace)
- If using `prompt_only`, generate the features manually from the prompts

### `Not a git repository`

**Cause:** `target_repo_path` points to a directory without a `.git` folder.

**Fix:** Ensure the target path is a valid git repository. Run `git init` in the target directory if needed.

## Getting help

- Check the [wiki pages](Home.md) for detailed documentation
- Review the [design documents](../Automated_Test_Creation_CLI_Design.md) for planned features
- Open an issue on the GitHub repository
