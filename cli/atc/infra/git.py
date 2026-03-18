"""Git operations — branch, commit, push via subprocess."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from atc.output.console import console


def _find_git() -> str:
    """Locate the git executable, raising a clear error if missing."""
    git = shutil.which("git")
    if git:
        return git
    # Common Windows install locations when git isn't on PATH
    if sys.platform == "win32":
        for candidate in (
            Path(r"C:\Program Files\Git\cmd\git.exe"),
            Path(r"C:\Program Files (x86)\Git\cmd\git.exe"),
        ):
            if candidate.exists():
                return str(candidate)
    raise FileNotFoundError(
        "git executable not found. Install Git and ensure it is on your PATH."
    )


class GitClient:
    """Subprocess-based git client for the target automation repo."""

    def __init__(self, repo_path: Path) -> None:
        self.repo_path = Path(repo_path)
        self._git = _find_git()
        if not (self.repo_path / ".git").exists():
            raise ValueError(f"Not a git repository: {self.repo_path}")

    def _run(self, *args: str) -> str:
        result = subprocess.run(
            [self._git, *args],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
        return result.stdout.strip()

    def checkout_or_create_branch(self, branch_name: str) -> None:
        """Switch to branch, creating it if it doesn't exist."""
        try:
            self._run("checkout", branch_name)
            console.print(f"  Switched to existing branch: {branch_name}")
        except RuntimeError:
            self._run("checkout", "-b", branch_name)
            console.print(f"  Created and switched to branch: {branch_name}")

    def add_all(self) -> None:
        """Stage all changes."""
        self._run("add", "-A")

    def add_files(self, paths: list[Path]) -> None:
        """Stage specific files."""
        str_paths = [str(p) for p in paths]
        self._run("add", *str_paths)

    def commit(self, message: str) -> str:
        """Create a commit and return the hash."""
        self._run("commit", "-m", message)
        return self._run("rev-parse", "HEAD")

    def push(self, branch_name: str, remote: str = "origin") -> None:
        """Push branch to remote."""
        self._run("push", "-u", remote, branch_name)

    def current_branch(self) -> str:
        """Get the current branch name."""
        return self._run("rev-parse", "--abbrev-ref", "HEAD")

    def has_changes(self) -> bool:
        """Check if there are uncommitted changes."""
        status = self._run("status", "--porcelain")
        return bool(status)
