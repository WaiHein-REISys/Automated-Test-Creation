"""Run configuration models."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class CredentialsConfig(BaseModel):
    """Optional credentials that can be stored in run.json.

    Values here take priority over environment variables / ``.env``.
    Leave a field empty to fall back to the corresponding ``ATC_*`` env var.

    .. warning::
       Storing secrets in JSON files is convenient but less secure than
       environment variables.  Make sure ``run.json`` is in ``.gitignore``.
    """

    ado_pat: str = Field(default="", description="Azure DevOps Personal Access Token")

    # Claude / Anthropic
    anthropic_api_key: str = Field(default="", description="Anthropic API key")

    # Azure OpenAI
    azure_openai_endpoint: str = Field(default="", description="Azure OpenAI endpoint URL")
    azure_openai_api_key: str = Field(default="", description="Azure OpenAI API key")
    azure_openai_deployment: str = Field(default="", description="Azure OpenAI deployment name")
    azure_openai_api_version: str = Field(default="", description="Azure OpenAI API version")

    # Ollama
    ollama_url: str = Field(default="", description="Ollama server URL")
    ollama_model: str = Field(default="", description="Ollama model name")

    # CLI Agent
    cli_agent_cmd: str = Field(default="", description="CLI agent command template")


class ProviderConfig(BaseModel):
    """AI provider configuration."""

    type: str = Field(default="prompt_only", description="claude | azure_openai | ollama | cli_agent | prompt_only")
    model: str = ""
    options: dict[str, str] = Field(default_factory=dict)


class TestExecutionConfig(BaseModel):
    """Configuration for running generated tests against an EHB2010 project.

    When ``enabled`` is True and ``target_repo_path`` is set in the parent
    ``RunConfig``, the pipeline will execute tests after the git-commit phase
    using the standalone EHB Test Runner (``cli/tools/ehb_test_runner.py``).

    The ``target_repo_path`` field on ``RunConfig`` is reused as the
    ``--project`` path for the test runner (it points to the EHB2010 root
    that contains the ``EHB.UI.Automation/`` folder).
    """

    enabled: bool = Field(
        default=False,
        description="Run generated tests after the pipeline completes",
    )
    tag: str = Field(
        default="",
        description="SpecFlow tag to filter tests (e.g. 'Automated', 'SF424Short')",
    )
    filter_expr: str = Field(
        default="",
        description="Raw dotnet test --filter expression (overrides tag)",
    )
    run_id: str = Field(
        default="",
        description="Unique run identifier for TRX naming.  Auto-generated if empty.",
    )
    results_dir: str = Field(
        default="",
        description="Directory for TRX output files.  Defaults to ./TestResults in CWD.",
    )
    config: str = Field(
        default="Release",
        description="Build configuration (Release / Debug)",
    )
    auto_build: bool = Field(
        default=True,
        description="Build the project before running tests",
    )


class RunOptions(BaseModel):
    """Runtime options."""

    dry_run: bool = False
    download_attachments: bool = True
    include_images_in_prompt: bool = True

    # Hierarchy depth limit (0 = unlimited)
    max_depth: int = Field(
        default=0,
        description=(
            "Maximum hierarchy depth to traverse below the root work item. "
            "0 = unlimited (fetch the full tree). "
            "1 = root + its direct children only. "
            "2 = root + children + grandchildren, etc."
        ),
    )

    # Tag-based filtering for child work items
    filter_tags: list[str] = Field(
        default_factory=list,
        description=(
            "Only include child work items that have at least one of these tags. "
            "Empty list = no filtering (fetch all children). "
            "Tags are matched case-insensitively against the ADO System.Tags field."
        ),
    )

    # Story completeness filter
    skip_incomplete_stories: bool = Field(
        default=False,
        description=(
            "Skip user stories that lack the minimum context needed to "
            "generate a feature file.  A story is considered incomplete "
            "when its description and acceptance criteria are missing any "
            "of: user/actor, goal/action, or benefit/purpose."
        ),
    )

    # Generation limits (0 = unlimited, empty list = all)
    generation_limit: int = Field(
        default=0, description="Max total feature files to generate (0 = unlimited)"
    )
    generation_limit_per_feature: int = Field(
        default=0, description="Max feature files per Feature parent folder (0 = unlimited)"
    )
    generation_only_ids: list[int] = Field(
        default_factory=list, description="Only generate for these work item IDs (empty = all)"
    )

    # Test execution
    test_execution: TestExecutionConfig = Field(
        default_factory=TestExecutionConfig,
        description="Post-pipeline test execution settings (EHB Test Runner)",
    )


class RunConfig(BaseModel):
    """Top-level run configuration loaded from JSON."""

    url: str = Field(default="", description="ADO work item URL (auto-parses org/project/ID)")
    product_name: str = Field(default="", description="Product name for folder structure")
    workspace_dir: Path = Field(default=Path("./workspace"))
    target_repo_path: Path | None = Field(
        default=None, description="Local path to target automation repo"
    )
    branch_name: str | None = Field(
        default=None, description="Git branch name, e.g. dev/DME/feature/EHB"
    )
    ado_api_version: str = Field(
        default="auto",
        description=(
            "Azure DevOps REST API version. "
            "'auto' probes the server and picks the best supported version (7.1, 7.0, 6.0). "
            "Set explicitly (e.g. '7.0') for on-prem servers that reject newer versions."
        ),
    )
    credentials: CredentialsConfig = Field(
        default_factory=CredentialsConfig,
        description=(
            "Optional inline credentials.  Values set here override "
            "environment variables and .env.  Leave empty to use env vars."
        ),
    )
    provider: ProviderConfig = Field(default_factory=ProviderConfig)
    options: RunOptions = Field(default_factory=RunOptions)
