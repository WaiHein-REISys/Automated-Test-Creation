# AI Providers

ATC supports five AI providers for generating `.feature` files. The provider is configured in `run.json` under the `provider` field.

## Provider comparison

| Provider | API Key Required | Vision | Offline | Fully Automated |
|----------|-----------------|--------|---------|-----------------|
| Claude | Yes (`ATC_ANTHROPIC_API_KEY`) | Yes | No | Yes |
| Azure OpenAI | Yes (`ATC_AZURE_OPENAI_API_KEY`) | Yes (gpt-4o) | No | Yes |
| Ollama | No | Yes (llava) | Yes | Yes |
| CLI Agent | No | No | Varies | Yes |
| Prompt Only | No | N/A | Yes | No (manual) |

## Claude (Anthropic API)

```json
{
  "provider": {
    "type": "claude",
    "model": "claude-sonnet-4-20250514"
  }
}
```

- **Vision support:** image attachments from ADO are base64-encoded and sent to the API
- **Default model:** `claude-sonnet-4-20250514`
- **Response parsing:** extracts `.feature` content from markdown-wrapped responses (strips ` ```gherkin ` / ` ``` `)

### Setup

```bash
python setup_env.py --extras claude
```

Environment variable:
```
ATC_ANTHROPIC_API_KEY=sk-ant-...
```

### Implementation

`cli/atc/providers/claude.py` — uses the `anthropic` Python SDK. Sends the prompt as a user message with optional image content blocks.

## Azure OpenAI

```json
{
  "provider": {
    "type": "azure_openai",
    "model": "gpt-4o",
    "options": {
      "endpoint": "https://your-resource.openai.azure.com/",
      "api_version": "2024-12-01-preview"
    }
  }
}
```

- **Vision support:** compatible with vision-capable deployments (gpt-4o, gpt-4-turbo)
- **Model field:** maps to your Azure deployment name
- **Endpoint and API version:** can be set in `provider.options` or via env vars

### Setup

```bash
python setup_env.py --extras azure-openai
```

Environment variables:
```
ATC_AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
ATC_AZURE_OPENAI_API_KEY=your-key
ATC_AZURE_OPENAI_DEPLOYMENT=gpt-4o
ATC_AZURE_OPENAI_API_VERSION=2024-12-01-preview
```

### Implementation

`cli/atc/providers/azure_openai.py` — uses the `openai` Python SDK with Azure configuration. Sends prompt as a user message with optional image URL content parts.

## Ollama (Local LLM)

```json
{
  "provider": {
    "type": "ollama",
    "model": "llama3"
  }
}
```

- **Runs locally** — no API key, no internet required
- **Multimodal support:** use `llava` or other vision models for image-aware generation
- **Default URL:** `http://localhost:11434`

### Setup

1. Install [Ollama](https://ollama.com/)
2. Pull a model: `ollama pull llama3`
3. Start Ollama (runs as a background service)

Environment variables (optional):
```
ATC_OLLAMA_MODEL=llama3
ATC_OLLAMA_URL=http://localhost:11434
```

### Implementation

`cli/atc/providers/ollama.py` — direct HTTP client to the Ollama `/api/generate` endpoint. Sends prompt as a string with optional base64-encoded images.

## CLI Agent (External Tool)

```json
{
  "provider": {
    "type": "cli_agent",
    "options": {
      "command": "windsurf generate --prompt {prompt_file}"
    }
  }
}
```

- **Invokes any external CLI command**
- **`{prompt_file}` placeholder** is replaced with the path to a temp file containing the rendered prompt
- **stdout** is captured as the generated `.feature` content

### Setup

Set the command in `provider.options.command` or via env var:
```
ATC_CLI_AGENT_CMD="my-tool generate --input {prompt_file}"
```

### Implementation

`cli/atc/providers/cli_agent.py` — writes the prompt to a temp file, substitutes `{prompt_file}` in the command, runs via `asyncio.create_subprocess_shell`, captures stdout, cleans up the temp file.

## Prompt Only (Manual)

```json
{
  "provider": {
    "type": "prompt_only"
  }
}
```

- **No AI invocation** — the pipeline renders and saves prompts but does not generate features
- **Use case:** manually copy prompts into Windsurf Cascade, ChatGPT, or any tool
- **Output:** `scenario_prompt.md` files in the workspace, empty `.feature` files (not written)

### Workflow

1. Run the pipeline: `./run_atc.sh run --config run.json`
2. Open each `scenario_prompt.md` in your preferred AI tool
3. Copy the generated content into the corresponding `Test Scenarios/*.feature` file
4. (Planned) Run `atc run --config run.json --resume` to continue with copy-to-repo and git

### Implementation

`cli/atc/providers/prompt_only.py` — returns an empty string from `generate()`. The executor skips writing the `.feature` file when content is empty.

## Adding a new provider

1. Create `cli/atc/providers/my_provider.py`:

```python
from atc.providers.base import GenerationProvider
from pathlib import Path

class MyProvider(GenerationProvider):
    def __init__(self, api_key: str, model: str = "default") -> None:
        self._api_key = api_key
        self._model = model

    async def generate(self, prompt: str, images: list[Path] | None = None) -> str:
        # Call your API, return .feature file content
        ...
```

2. Register in `cli/atc/providers/__init__.py:create_provider()`:

```python
elif provider_type == "my_provider":
    from atc.providers.my_provider import MyProvider
    return MyProvider(api_key=settings.my_api_key, model=config.model)
```

3. Add env vars to `cli/atc/infra/settings.py:AtcSettings` if needed
4. Update `ProviderConfig.type` description in `cli/atc/infra/config.py`

## Future enhancements

- **Cascade provider** — directly invoke Windsurf Cascade API
- **Batch provider** — submit all prompts at once for providers that support batch APIs
- **Caching** — skip re-generation for unchanged work items
- **Provider fallback chain** — try provider A, fall back to B on failure
