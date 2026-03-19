"""Pipeline executor — orchestrates all phases."""

from __future__ import annotations

import asyncio

from atc.core.progress import Phase, ProgressEvent, ProgressReporter
from atc.infra.config import RunConfig
from atc.infra.settings import AtcSettings
from atc.output.console import console, print_error, print_status, print_success


async def _emit(
    reporter: ProgressReporter | None,
    phase: Phase,
    message: str,
    *,
    current: int = 0,
    total: int = 0,
    level: str = "info",
) -> None:
    """Emit a progress event if a reporter is attached."""
    if reporter:
        await reporter.report(ProgressEvent(phase, message, current, total, level))


async def _phase_start(reporter: ProgressReporter | None, phase: Phase, message: str) -> None:
    if reporter:
        await reporter.phase_start(phase, message)


async def _phase_end(reporter: ProgressReporter | None, phase: Phase, message: str) -> None:
    if reporter:
        await reporter.phase_end(phase, message)


class PipelineCancelled(Exception):
    """Raised when the pipeline is cancelled via cancel_event."""


def _check_cancel(cancel_event: asyncio.Event | None) -> None:
    """Raise PipelineCancelled if cancellation has been requested."""
    if cancel_event and cancel_event.is_set():
        raise PipelineCancelled("Pipeline cancelled by user")


async def execute_pipeline(
    config: RunConfig,
    reporter: ProgressReporter | None = None,
    cancel_event: asyncio.Event | None = None,
) -> None:
    """Main pipeline: ingest → workspace → prompt → generate → copy → git."""
    from atc.infra.settings import resolve_settings

    base_settings = AtcSettings()
    settings = resolve_settings(base_settings, config.credentials)
    pat = settings.ado_pat.get_secret_value()

    if not pat:
        print_error(
            "ADO PAT is not set. Provide it via ATC_ADO_PAT env var, "
            ".env file, or the 'credentials.ado_pat' field in run.json."
        )
        await _emit(reporter, Phase.PARSE_URL, "ADO PAT is not set", level="error")
        return

    print_status(f"Starting ATC pipeline for: {config.url}")
    await _emit(reporter, Phase.PARSE_URL, f"Starting pipeline for: {config.url}")

    if config.options.dry_run:
        print_status("DRY RUN — no changes will be made.", style="bold yellow")
        await _emit(reporter, Phase.PARSE_URL, "DRY RUN mode enabled", level="warning")

    # Phase 1: Parse URL and fetch ADO hierarchy
    _check_cancel(cancel_event)
    await _phase_start(reporter, Phase.PARSE_URL, "Parsing ADO URL...")
    from atc.infra.ado_url import parse_ado_url

    target = parse_ado_url(config.url)
    msg = f"Parsed URL → org={target.org}, project={target.project}, id={target.work_item_id}"
    print_status(msg)
    await _emit(reporter, Phase.PARSE_URL, msg, level="success")
    await _phase_end(reporter, Phase.PARSE_URL, "URL parsed successfully")

    from atc.infra.ado import AdoClient

    # Determine API version: env var > run.json > auto
    api_version = config.ado_api_version
    if settings.ado_api_version != "auto":
        api_version = settings.ado_api_version
    if api_version != "auto":
        print_status(f"Using ADO API version: {api_version}")
        await _emit(reporter, Phase.FETCH_HIERARCHY, f"Using API version: {api_version}")

    await _phase_start(reporter, Phase.FETCH_HIERARCHY, "Fetching work item hierarchy...")

    _check_cancel(cancel_event)
    async with AdoClient(target.org_url, target.project, pat, api_version=api_version) as ado:
        max_depth = config.options.max_depth
        filter_tags = config.options.filter_tags
        if max_depth:
            print_status(f"Hierarchy depth limit: {max_depth} level(s) below root")
        if filter_tags:
            print_status(f"Tag filter: only children with tags {filter_tags}")
        print_status("Fetching work item hierarchy...")
        tree = await ado.get_tree(
            target.work_item_id,
            max_depth=max_depth,
            filter_tags=filter_tags,
        )

        from atc.output.console import print_tree

        print_tree(tree, title=f"Epic #{target.work_item_id}")
        all_nodes = tree.walk()
        await _emit(
            reporter,
            Phase.FETCH_HIERARCHY,
            f"Fetched {len(all_nodes)} work items",
            level="success",
        )
        await _phase_end(reporter, Phase.FETCH_HIERARCHY, "Hierarchy fetched")

        # Phase 2: Build workspace
        _check_cancel(cancel_event)
        await _phase_start(reporter, Phase.BUILD_WORKSPACE, "Building workspace...")
        from atc.infra.workspace import WorkspaceBuilder

        builder = WorkspaceBuilder(config.workspace_dir, config.product_name)
        manifest = await builder.build_from_tree(tree, ado, config.options.download_attachments)

        console.print(f"\n[bold]Workspace built at:[/bold] {manifest.root}")
        console.print(f"[bold]Work items processed:[/bold] {len(manifest.items)}")
        await _emit(
            reporter,
            Phase.BUILD_WORKSPACE,
            f"Workspace built at {manifest.root} — {len(manifest.items)} items",
            level="success",
        )
        await _phase_end(reporter, Phase.BUILD_WORKSPACE, "Workspace ready")

        # Phase 3: Render prompts
        _check_cancel(cancel_event)
        await _phase_start(reporter, Phase.RENDER_PROMPTS, "Rendering prompts...")
        from atc.infra.prompts import PromptRenderer

        renderer = PromptRenderer()
        if config.options.skip_incomplete_stories:
            print_status(
                "Story completeness filter enabled — "
                "skipping stories missing user/goal/benefit"
            )
            await _emit(
                reporter,
                Phase.RENDER_PROMPTS,
                "Story completeness filter enabled — "
                "stories missing user/goal/benefit will be skipped",
                level="warning",
            )
        story_nodes = _find_leaf_stories(
            tree, skip_incomplete=config.options.skip_incomplete_stories,
        )
        prompts_rendered = 0

        # Store bundles for Phase 4 generation
        prompt_bundles: dict[int, "PromptBundle"] = {}

        for i, (story_node, ancestors) in enumerate(story_nodes, 1):
            paths = manifest.get_paths(story_node.id)
            if not paths or not paths.prompt_path:
                continue

            from atc.core.models import PromptBundle

            bundle = renderer.render_scenario_prompt(
                story=story_node.item,
                ancestors=ancestors,
                images=[a for a in story_node.item.attachments if a.local_path],
                product_name=config.product_name,
            )
            prompt_bundles[story_node.id] = bundle

            # Save combined prompt for human review
            paths.prompt_path.write_text(bundle.combined, encoding="utf-8")

            # Also save split files for inspection
            system_path = paths.prompt_path.parent / "system_prompt.md"
            user_path = paths.prompt_path.parent / "user_prompt.md"
            system_path.write_text(bundle.system_message, encoding="utf-8")
            user_path.write_text(bundle.user_message, encoding="utf-8")
            prompts_rendered += 1
            if reporter:
                await reporter.item_progress(
                    Phase.RENDER_PROMPTS,
                    i,
                    len(story_nodes),
                    f"Rendered prompt for #{story_node.id}",
                )

        console.print(f"[bold]Prompts rendered:[/bold] {prompts_rendered}")
        await _emit(
            reporter,
            Phase.RENDER_PROMPTS,
            f"Rendered {prompts_rendered} prompts",
            level="success",
        )
        await _phase_end(reporter, Phase.RENDER_PROMPTS, "Prompts rendered")

        # Phase 4: Generate feature files
        _check_cancel(cancel_event)
        await _phase_start(reporter, Phase.GENERATE_FEATURES, "Generating feature files...")
        from atc.providers import create_provider

        provider = create_provider(config.provider, settings)
        generated = 0
        failed = 0
        skipped = 0
        total = len(story_nodes)

        # Generation limit settings
        gen_limit = config.options.generation_limit
        per_feature_limit = config.options.generation_limit_per_feature
        only_ids = set(config.options.generation_only_ids)
        feature_gen_counts: dict[int, int] = {}  # feature_id → count generated

        if gen_limit:
            console.print(f"[dim]Generation limit:[/dim] {gen_limit} total")
        if per_feature_limit:
            console.print(f"[dim]Per-feature limit:[/dim] {per_feature_limit} per Feature parent")
        if only_ids:
            console.print(f"[dim]Generating only IDs:[/dim] {sorted(only_ids)}")

        if config.options.dry_run:
            print_status("Skipping generation (dry run).", style="bold yellow")
            await _emit(
                reporter,
                Phase.GENERATE_FEATURES,
                "Skipped generation (dry run)",
                level="warning",
            )
        else:
            console.print(f"\n[bold]Generating feature files ({total} items)...[/bold]")

            for idx, (story_node, ancestors) in enumerate(story_nodes, 1):
                _check_cancel(cancel_event)
                item = story_node.item
                type_prefix = item.work_item_type.replace(" ", "")
                label = f"{type_prefix}#{item.id}"

                # Check total generation limit
                if gen_limit and generated >= gen_limit:
                    skipped += 1
                    msg = f"Skipped: {label} — total limit reached ({gen_limit})"
                    console.print(f"  [{idx}/{total}] [yellow]{msg}[/yellow]")
                    await _emit(reporter, Phase.GENERATE_FEATURES, msg, current=idx, total=total, level="warning")
                    continue

                # Check ID filter
                if only_ids and item.id not in only_ids:
                    skipped += 1
                    msg = f"Skipped: {label} — not in generation_only_ids"
                    console.print(f"  [{idx}/{total}] [yellow]{msg}[/yellow]")
                    await _emit(reporter, Phase.GENERATE_FEATURES, msg, current=idx, total=total, level="warning")
                    continue

                # Check per-feature limit
                feature_parent_id = _get_feature_parent_id(ancestors)
                if per_feature_limit and feature_parent_id is not None:
                    count = feature_gen_counts.get(feature_parent_id, 0)
                    if count >= per_feature_limit:
                        skipped += 1
                        feature_label = f"Feature#{feature_parent_id}"
                        msg = f"Skipped: {label} — per-feature limit reached for {feature_label} ({per_feature_limit})"
                        console.print(f"  [{idx}/{total}] [yellow]{msg}[/yellow]")
                        await _emit(reporter, Phase.GENERATE_FEATURES, msg, current=idx, total=total, level="warning")
                        continue

                paths = manifest.get_paths(story_node.id)
                if not paths or not paths.prompt_path or not paths.feature_path:
                    skipped += 1
                    msg = f"Skipped: {label} — no prompt or feature path"
                    console.print(f"  [{idx}/{total}] [yellow]{msg}[/yellow]")
                    await _emit(reporter, Phase.GENERATE_FEATURES, msg, current=idx, total=total, level="warning")
                    continue

                if not paths.prompt_path.exists():
                    skipped += 1
                    msg = f"Skipped: {label} — prompt file not found"
                    console.print(f"  [{idx}/{total}] [yellow]{msg}[/yellow]")
                    await _emit(reporter, Phase.GENERATE_FEATURES, msg, current=idx, total=total, level="warning")
                    continue

                console.print(f"  [{idx}/{total}] [dim]Generating:[/dim] {label} — {item.title}")
                await _emit(
                    reporter,
                    Phase.GENERATE_FEATURES,
                    f"Generating: {label} — {item.title}",
                    current=idx,
                    total=total,
                )

                # Use the PromptBundle if available, fall back to flat file
                bundle = prompt_bundles.get(story_node.id)
                if bundle is None:
                    # Reconstruct from saved split files
                    sys_path = paths.prompt_path.parent / "system_prompt.md"
                    usr_path = paths.prompt_path.parent / "user_prompt.md"
                    if sys_path.exists() and usr_path.exists():
                        from atc.core.models import PromptBundle

                        bundle = PromptBundle(
                            system_message=sys_path.read_text(encoding="utf-8"),
                            user_message=usr_path.read_text(encoding="utf-8"),
                        )
                    else:
                        # Legacy: single prompt file
                        bundle = paths.prompt_path.read_text(encoding="utf-8")

                images = [
                    a.local_path
                    for a in item.attachments
                    if a.local_path and a.local_path.exists()
                ]

                try:
                    content = await provider.generate(bundle, images)
                except Exception as e:
                    failed += 1
                    msg = f"Failed: {label} — {e}"
                    console.print(f"  [{idx}/{total}] [red]{msg}[/red]")
                    await _emit(reporter, Phase.GENERATE_FEATURES, msg, current=idx, total=total, level="error")
                    continue

                if content:
                    paths.feature_path.write_text(content, encoding="utf-8")
                    generated += 1
                    if feature_parent_id is not None:
                        feature_gen_counts[feature_parent_id] = feature_gen_counts.get(feature_parent_id, 0) + 1
                    msg = f"Generated: {paths.feature_path.name}"
                    console.print(f"  [{idx}/{total}] [green]{msg}[/green]")
                    await _emit(reporter, Phase.GENERATE_FEATURES, msg, current=idx, total=total, level="success")
                else:
                    failed += 1
                    msg = f"Empty response: {label} — provider returned no content"
                    console.print(f"  [{idx}/{total}] [red]{msg}[/red]")
                    await _emit(reporter, Phase.GENERATE_FEATURES, msg, current=idx, total=total, level="error")

            summary = (
                f"Generation complete: {generated} generated, "
                f"{failed} failed, {skipped} skipped (out of {total})"
            )
            console.print(
                f"\n[bold]Generation complete:[/bold] "
                f"[green]{generated} generated[/green], "
                f"[red]{failed} failed[/red], "
                f"[yellow]{skipped} skipped[/yellow] "
                f"(out of {total})"
            )
            await _emit(reporter, Phase.GENERATE_FEATURES, summary, level="success")

        await _phase_end(reporter, Phase.GENERATE_FEATURES, "Generation phase complete")

        # Phase 5: Copy to target repo
        _check_cancel(cancel_event)
        await _phase_start(reporter, Phase.COPY_TO_REPO, "Copying to target repo...")
        if config.target_repo_path and not config.options.dry_run:
            from atc.infra.workspace import copy_to_target_repo

            copied = copy_to_target_repo(manifest, config.target_repo_path)
            console.print(f"[bold]Files copied to repo:[/bold] {copied}")
            await _emit(
                reporter,
                Phase.COPY_TO_REPO,
                f"Copied {copied} files to {config.target_repo_path}",
                level="success",
            )

            # Phase 6: Git operations
            await _phase_start(reporter, Phase.GIT_OPERATIONS, "Running git operations...")
            if config.branch_name:
                from atc.infra.git import GitClient

                git = GitClient(config.target_repo_path)
                git.checkout_or_create_branch(config.branch_name)
                git.add_all()
                git.commit(f"feat(atc): add generated feature files for Epic #{target.work_item_id}")
                console.print(f"[bold]Committed to branch:[/bold] {config.branch_name}")
                await _emit(
                    reporter,
                    Phase.GIT_OPERATIONS,
                    f"Committed to branch: {config.branch_name}",
                    level="success",
                )
            await _phase_end(reporter, Phase.GIT_OPERATIONS, "Git operations complete")
        else:
            if config.options.dry_run:
                await _emit(reporter, Phase.COPY_TO_REPO, "Skipped (dry run)", level="warning")
            elif not config.target_repo_path:
                await _emit(reporter, Phase.COPY_TO_REPO, "No target repo configured", level="info")
        await _phase_end(reporter, Phase.COPY_TO_REPO, "Copy phase complete")

    # Phase 7: Run tests (optional)
    test_exec = config.options.test_execution
    project_path = str(config.target_repo_path) if config.target_repo_path else ""

    if test_exec.enabled and project_path and not config.options.dry_run:
        _check_cancel(cancel_event)
        await _phase_start(reporter, Phase.RUN_TESTS, "Running generated tests...")

        try:
            test_result = await _run_tests(
                project_path=project_path,
                test_config=test_exec,
                reporter=reporter,
            )

            if test_result.all_passed:
                msg = (
                    f"All tests passed: {test_result.passed}/{test_result.total} "
                    f"(TRX: {test_result.trx_path})"
                )
                console.print(f"[green]{msg}[/green]")
                await _emit(reporter, Phase.RUN_TESTS, msg, level="success")
            else:
                msg = (
                    f"Tests finished: {test_result.passed} passed, "
                    f"{test_result.failed} failed out of {test_result.total}"
                )
                console.print(f"[red]{msg}[/red]")
                await _emit(reporter, Phase.RUN_TESTS, msg, level="error")

                for ft in test_result.failed_tests:
                    err_line = f"  FAIL: {ft['name']}"
                    if ft.get("error_message"):
                        err_line += f" — {ft['error_message'][:120]}"
                    console.print(f"[red]{err_line}[/red]")
                    await _emit(reporter, Phase.RUN_TESTS, err_line, level="error")

            await _phase_end(reporter, Phase.RUN_TESTS, "Test execution complete")

        except FileNotFoundError as e:
            msg = f"Test runner error: {e}"
            console.print(f"[red]{msg}[/red]")
            await _emit(reporter, Phase.RUN_TESTS, msg, level="error")
            await _phase_end(reporter, Phase.RUN_TESTS, "Test execution failed")

        except Exception as e:
            msg = f"Test execution error: {e}"
            console.print(f"[red]{msg}[/red]")
            await _emit(reporter, Phase.RUN_TESTS, msg, level="error")
            await _phase_end(reporter, Phase.RUN_TESTS, "Test execution failed")

    elif test_exec.enabled and config.options.dry_run:
        await _phase_start(reporter, Phase.RUN_TESTS, "Skipping tests (dry run)")
        await _emit(reporter, Phase.RUN_TESTS, "Skipped test execution (dry run)", level="warning")
        await _phase_end(reporter, Phase.RUN_TESTS, "Skipped")
    elif test_exec.enabled and not project_path:
        await _phase_start(reporter, Phase.RUN_TESTS, "Skipping tests (no project path)")
        await _emit(
            reporter, Phase.RUN_TESTS,
            "Skipped — set target_repo_path to the EHB2010 project root to enable test execution",
            level="warning",
        )
        await _phase_end(reporter, Phase.RUN_TESTS, "Skipped")

    print_success("ATC pipeline complete!")
    await _emit(reporter, Phase.RUN_TESTS if test_exec.enabled else Phase.GIT_OPERATIONS, "Pipeline complete!", level="success")


def _get_feature_parent_id(ancestors: list["WorkItemNode"]) -> int | None:
    """Find the Feature parent ID from the ancestor chain."""
    for ancestor in reversed(ancestors):
        if ancestor.work_item_type == "Feature":
            return ancestor.id
    return None


async def _run_tests(
    project_path: str,
    test_config: "TestExecutionConfig",
    reporter: ProgressReporter | None = None,
) -> "TestResult":
    """Execute tests using the EHB Test Runner.

    Uses ``target_repo_path`` from run.json as the ``--project`` path
    (pointing to the EHB2010 root containing ``EHB.UI.Automation/``).

    The runner and TRX parser live in ``cli/tools/`` and are imported at
    call-time so the rest of the pipeline keeps working even if dotnet
    is not installed.
    """
    import sys
    from pathlib import Path as _Path

    # Make cli/tools/ importable at runtime
    tools_dir = _Path(__file__).resolve().parent.parent.parent / "tools"
    if str(tools_dir) not in sys.path:
        sys.path.insert(0, str(tools_dir))

    from ehb_test_runner import EHBTestRunner  # type: ignore[import-untyped]

    await _emit(
        reporter, Phase.RUN_TESTS,
        f"Initialising EHB Test Runner — project: {project_path}",
    )

    runner = EHBTestRunner(
        project_path=project_path,
        results_dir=test_config.results_dir or None,
        config=test_config.config,
        auto_build=test_config.auto_build,
    )

    # List available tags for information
    try:
        tags = runner.list_tags()
        if tags:
            await _emit(
                reporter, Phase.RUN_TESTS,
                f"Available tags: {', '.join(tags[:15])}{'...' if len(tags) > 15 else ''}",
            )
    except Exception:
        pass

    run_kwargs: dict = {}
    if test_config.tag:
        run_kwargs["tag"] = test_config.tag
    if test_config.filter_expr:
        run_kwargs["filter_expr"] = test_config.filter_expr
    if test_config.run_id:
        run_kwargs["run_id"] = test_config.run_id

    await _emit(
        reporter, Phase.RUN_TESTS,
        f"Running tests{' (tag=' + test_config.tag + ')' if test_config.tag else ''}"
        f"{' (filter=' + test_config.filter_expr + ')' if test_config.filter_expr else ''}...",
    )

    # Run synchronously in a thread to avoid blocking the event loop
    import asyncio as _asyncio

    result = await _asyncio.to_thread(runner.run, **run_kwargs)
    return result


_LEAF_TYPES = {"User Story", "Product Backlog Item", "Task"}


def _find_leaf_stories(
    root: "WorkItemNode",
    *,
    skip_incomplete: bool = False,
) -> list[tuple["WorkItemNode", list["WorkItemNode"]]]:
    """Find leaf work item nodes (User Story, PBI, Task) with their ancestor chain.

    When *skip_incomplete* is True, stories whose description and acceptance
    criteria lack a user/actor, goal/action, or benefit/purpose are excluded
    and logged to the console.
    """
    from atc.core.models import StoryCompletenessResult, WorkItemNode, check_story_completeness

    results: list[tuple[WorkItemNode, list[WorkItemNode]]] = []
    skipped: list[tuple[WorkItemNode, StoryCompletenessResult]] = []

    def _walk(node: WorkItemNode, ancestors: list[WorkItemNode]) -> None:
        if node.work_item_type in _LEAF_TYPES:
            if skip_incomplete:
                result = check_story_completeness(
                    node.item.description,
                    node.item.acceptance_criteria,
                    has_attachments=bool(node.item.attachments),
                )
                if not result.is_generatable:
                    skipped.append((node, result))
                    return
            results.append((node, list(ancestors)))
        else:
            for child in node.children:
                _walk(child, ancestors + [node])

    _walk(root, [])

    if skipped:
        from atc.output.console import console

        console.print(
            f"\n[yellow]Skipped {len(skipped)} item(s) — "
            f"incomplete story (missing user/goal/benefit):[/yellow]"
        )
        for node, result in skipped:
            missing = ", ".join(result.missing)
            console.print(f"  [yellow]• #{node.id} — {node.title}  (missing: {missing})[/yellow]")

    return results
