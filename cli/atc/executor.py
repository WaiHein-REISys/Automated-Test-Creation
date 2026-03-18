"""Pipeline executor — orchestrates all phases."""

from __future__ import annotations

from atc.infra.config import RunConfig
from atc.infra.settings import AtcSettings
from atc.output.console import console, print_error, print_status, print_success


async def execute_pipeline(config: RunConfig) -> None:
    """Main pipeline: ingest → workspace → prompt → generate → copy → git."""
    settings = AtcSettings()
    pat = settings.ado_pat.get_secret_value()

    if not pat:
        print_error("ATC_ADO_PAT environment variable is not set.")
        return

    print_status(f"Starting ATC pipeline for: {config.url}")

    if config.options.dry_run:
        print_status("DRY RUN — no changes will be made.", style="bold yellow")

    # Phase 1: Parse URL and fetch ADO hierarchy
    from atc.infra.ado_url import parse_ado_url

    target = parse_ado_url(config.url)
    print_status(f"Parsed URL → org={target.org}, project={target.project}, id={target.work_item_id}")

    from atc.infra.ado import AdoClient

    # Determine API version: env var > run.json > auto
    api_version = config.ado_api_version
    if settings.ado_api_version != "auto":
        api_version = settings.ado_api_version
    if api_version != "auto":
        print_status(f"Using ADO API version: {api_version}")

    async with AdoClient(target.org_url, target.project, pat, api_version=api_version) as ado:
        print_status("Fetching work item hierarchy...")
        tree = await ado.get_tree(target.work_item_id)

        from atc.output.console import print_tree

        print_tree(tree, title=f"Epic #{target.work_item_id}")

        # Phase 2: Build workspace
        from atc.infra.workspace import WorkspaceBuilder

        builder = WorkspaceBuilder(config.workspace_dir, config.product_name)
        manifest = await builder.build_from_tree(tree, ado, config.options.download_attachments)

        console.print(f"\n[bold]Workspace built at:[/bold] {manifest.root}")
        console.print(f"[bold]Work items processed:[/bold] {len(manifest.items)}")

        # Phase 3: Render prompts
        from atc.infra.prompts import PromptRenderer

        renderer = PromptRenderer()
        story_nodes = _find_leaf_stories(tree)
        prompts_rendered = 0

        for story_node, ancestors in story_nodes:
            paths = manifest.get_paths(story_node.id)
            if not paths or not paths.prompt_path:
                continue

            prompt = renderer.render_scenario_prompt(
                story=story_node.item,
                ancestors=ancestors,
                images=[a for a in story_node.item.attachments if a.local_path],
            )
            paths.prompt_path.write_text(prompt, encoding="utf-8")
            prompts_rendered += 1

        console.print(f"[bold]Prompts rendered:[/bold] {prompts_rendered}")

        # Phase 4: Generate feature files
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
        else:
            console.print(f"\n[bold]Generating feature files ({total} items)...[/bold]")

            for idx, (story_node, ancestors) in enumerate(story_nodes, 1):
                item = story_node.item
                type_prefix = item.work_item_type.replace(" ", "")
                label = f"{type_prefix}#{item.id}"

                # Check total generation limit
                if gen_limit and generated >= gen_limit:
                    skipped += 1
                    console.print(f"  [{idx}/{total}] [yellow]Skipped:[/yellow] {label} — total limit reached ({gen_limit})")
                    continue

                # Check ID filter
                if only_ids and item.id not in only_ids:
                    skipped += 1
                    console.print(f"  [{idx}/{total}] [yellow]Skipped:[/yellow] {label} — not in generation_only_ids")
                    continue

                # Check per-feature limit
                feature_parent_id = _get_feature_parent_id(ancestors)
                if per_feature_limit and feature_parent_id is not None:
                    count = feature_gen_counts.get(feature_parent_id, 0)
                    if count >= per_feature_limit:
                        skipped += 1
                        feature_label = f"Feature#{feature_parent_id}"
                        console.print(f"  [{idx}/{total}] [yellow]Skipped:[/yellow] {label} — per-feature limit reached for {feature_label} ({per_feature_limit})")
                        continue

                paths = manifest.get_paths(story_node.id)
                if not paths or not paths.prompt_path or not paths.feature_path:
                    skipped += 1
                    console.print(f"  [{idx}/{total}] [yellow]Skipped:[/yellow] {label} — no prompt or feature path")
                    continue

                if not paths.prompt_path.exists():
                    skipped += 1
                    console.print(f"  [{idx}/{total}] [yellow]Skipped:[/yellow] {label} — prompt file not found")
                    continue

                console.print(f"  [{idx}/{total}] [dim]Generating:[/dim] {label} — {item.title}")

                prompt = paths.prompt_path.read_text(encoding="utf-8")
                images = [
                    a.local_path
                    for a in item.attachments
                    if a.local_path and a.local_path.exists()
                ]

                try:
                    content = await provider.generate(prompt, images)
                except Exception as e:
                    failed += 1
                    console.print(f"  [{idx}/{total}] [red]Failed:[/red] {label} — {e}")
                    continue

                if content:
                    paths.feature_path.write_text(content, encoding="utf-8")
                    generated += 1
                    if feature_parent_id is not None:
                        feature_gen_counts[feature_parent_id] = feature_gen_counts.get(feature_parent_id, 0) + 1
                    console.print(f"  [{idx}/{total}] [green]Generated:[/green] {paths.feature_path.name}")
                else:
                    failed += 1
                    console.print(f"  [{idx}/{total}] [red]Empty response:[/red] {label} — provider returned no content")

            console.print(
                f"\n[bold]Generation complete:[/bold] "
                f"[green]{generated} generated[/green], "
                f"[red]{failed} failed[/red], "
                f"[yellow]{skipped} skipped[/yellow] "
                f"(out of {total})"
            )

        # Phase 5: Copy to target repo
        if config.target_repo_path and not config.options.dry_run:
            from atc.infra.workspace import copy_to_target_repo

            copied = copy_to_target_repo(manifest, config.target_repo_path)
            console.print(f"[bold]Files copied to repo:[/bold] {copied}")

            # Phase 6: Git operations
            if config.branch_name:
                from atc.infra.git import GitClient

                git = GitClient(config.target_repo_path)
                git.checkout_or_create_branch(config.branch_name)
                git.add_all()
                git.commit(f"feat(atc): add generated feature files for Epic #{target.work_item_id}")
                console.print(f"[bold]Committed to branch:[/bold] {config.branch_name}")

    print_success("ATC pipeline complete!")


def _get_feature_parent_id(ancestors: list["WorkItemNode"]) -> int | None:
    """Find the Feature parent ID from the ancestor chain."""
    for ancestor in reversed(ancestors):
        if ancestor.work_item_type == "Feature":
            return ancestor.id
    return None


_LEAF_TYPES = {"User Story", "Product Backlog Item", "Task"}


def _find_leaf_stories(
    root: "WorkItemNode",
) -> list[tuple["WorkItemNode", list["WorkItemNode"]]]:
    """Find leaf work item nodes (User Story, PBI, Task) with their ancestor chain."""
    from atc.core.models import WorkItemNode

    results: list[tuple[WorkItemNode, list[WorkItemNode]]] = []

    def _walk(node: WorkItemNode, ancestors: list[WorkItemNode]) -> None:
        if node.work_item_type in _LEAF_TYPES:
            results.append((node, list(ancestors)))
        else:
            for child in node.children:
                _walk(child, ancestors + [node])

    _walk(root, [])
    return results
