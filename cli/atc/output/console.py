"""Rich console output helpers."""

from rich.console import Console
from rich.panel import Panel
from rich.tree import Tree

from atc.core.models import WorkItemNode

console = Console()


def print_tree(root: WorkItemNode, title: str = "Work Item Hierarchy") -> None:
    """Print the work item tree using Rich."""
    tree = Tree(f"[bold]{title}[/bold]")
    _add_node(tree, root)
    console.print(tree)


def _add_node(tree: Tree, node: WorkItemNode) -> None:
    type_colors = {
        "Epic": "magenta",
        "Feature": "cyan",
        "User Story": "green",
        "Task": "yellow",
        "Bug": "red",
    }
    color = type_colors.get(node.work_item_type, "white")
    label = f"[{color}]{node.work_item_type}[/{color}] #{node.id} — {node.title}"
    branch = tree.add(label)
    for child in node.children:
        _add_node(branch, child)


def print_status(message: str, style: str = "bold green") -> None:
    console.print(f"[{style}]{message}[/{style}]")


def print_error(message: str) -> None:
    console.print(Panel(message, title="Error", border_style="red"))


def print_success(message: str) -> None:
    console.print(Panel(message, title="Success", border_style="green"))
