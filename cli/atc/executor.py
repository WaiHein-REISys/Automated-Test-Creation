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

    async with AdoClient(target.org_url, target.project, pat) as ado:
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

        if config.options.dry_run:
            print_status("Skipping generation (dry run).", style="bold yellow")
        else:
            for story_node, ancestors in story_nodes:
                paths = manifest.get_paths(story_node.id)
                if not paths or not paths.prompt_path or not paths.feature_path:
                    continue

                prompt = paths.prompt_path.read_text(encoding="utf-8")
                images = [
                    a.local_path
                    for a in story_node.item.attachments
                    if a.local_path and a.local_path.exists()
                ]

                content = await provider.generate(prompt, images)
                if content:
                    paths.feature_path.write_text(content, encoding="utf-8")
                    generated += 1
                    console.print(
                        f"  [green]Generated:[/green] {paths.feature_path.name}"
                    )

            console.print(f"[bold]Feature files generated:[/bold] {generated}")

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


def _find_leaf_stories(
    root: "WorkItemNode",
) -> list[tuple["WorkItemNode", list["WorkItemNode"]]]:
    """Find User Story nodes with their ancestor chain."""
    from atc.core.models import WorkItemNode

    results: list[tuple[WorkItemNode, list[WorkItemNode]]] = []

    def _walk(node: WorkItemNode, ancestors: list[WorkItemNode]) -> None:
        if node.work_item_type == "User Story":
            results.append((node, list(ancestors)))
        else:
            for child in node.children:
                _walk(child, ancestors + [node])

    _walk(root, [])
    return results
