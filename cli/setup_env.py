#!/usr/bin/env python3
"""Cross-platform environment setup for ATC.

Works on Windows, macOS, and Linux. Detects available tooling (uv or pip)
and installs dependencies into a virtual environment.

Usage:
    python setup_env.py                  # Install core dependencies
    python setup_env.py --extras claude  # Install with Claude provider
    python setup_env.py --extras dev     # Install dev tools
    python setup_env.py --extras all     # Install everything
"""

from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path

PYTHON_MIN = (3, 12)
PYTHON_MAX = (3, 14)
VENV_DIR = ".venv"
EXTRAS = ["claude", "azure-openai", "dev"]


def _print(msg: str, style: str = "info") -> None:
    symbols = {"info": "→", "ok": "✓", "warn": "!", "err": "✗"}
    sym = symbols.get(style, "→")
    print(f"  {sym} {msg}")


def is_supported_python_version(version: tuple[int, int]) -> bool:
    """Return True when the interpreter version is supported by the project."""
    return PYTHON_MIN <= version < PYTHON_MAX


def supported_python_label() -> str:
    """Return the supported Python range for user-facing messages."""
    return f"Python {PYTHON_MIN[0]}.{PYTHON_MIN[1]} or {PYTHON_MAX[0]}.{PYTHON_MAX[1] - 1}"


def check_python_version() -> None:
    v = sys.version_info
    version = (v.major, v.minor)
    if not is_supported_python_version(version):
        _print(
            f"{supported_python_label()} is required (found {v.major}.{v.minor}.{v.micro})",
            "err",
        )
        sys.exit(1)
    _print(f"Python {v.major}.{v.minor}.{v.micro}", "ok")


def find_uv() -> str | None:
    """Find the uv executable, if available."""
    return shutil.which("uv")


def find_pip(venv: Path) -> str:
    """Return pip path inside the venv."""
    if platform.system() == "Windows":
        return str(venv / "Scripts" / "pip.exe")
    return str(venv / "bin" / "pip")


def find_python(venv: Path) -> str:
    """Return python path inside the venv."""
    if platform.system() == "Windows":
        return str(venv / "Scripts" / "python.exe")
    return str(venv / "bin" / "python")


def run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
    """Run a command, printing it first."""
    _print(f"$ {' '.join(cmd)}", "info")
    result = subprocess.run(cmd, text=True, **kwargs)  # type: ignore[arg-type]
    if result.returncode != 0:
        _print(f"Command failed with exit code {result.returncode}", "err")
        sys.exit(result.returncode)
    return result


def setup_with_uv(uv: str, extras: list[str]) -> None:
    """Set up the environment using uv."""
    _print("Using uv for dependency management", "ok")

    # Force reinstall of the local package so the editable .pth file points to
    # the current directory (it contains an absolute path that goes stale when
    # the repo is moved or cloned to a new location).
    cmd = [uv, "sync", "--reinstall-package", "atc", "--python", f"{PYTHON_MIN[0]}.{PYTHON_MIN[1]}"]
    for extra in extras:
        cmd.extend(["--extra", extra])
    run(cmd)


def setup_with_pip(extras: list[str]) -> None:
    """Set up the environment using venv + pip (fallback)."""
    _print("uv not found — falling back to venv + pip", "warn")
    venv = Path(VENV_DIR)

    if not venv.exists():
        _print(f"Creating virtual environment in {VENV_DIR}/", "info")
        run([sys.executable, "-m", "venv", str(venv)])
    else:
        _print(f"Virtual environment already exists at {VENV_DIR}/", "ok")

    py = find_python(venv)

    # Upgrade pip first
    run([py, "-m", "pip", "install", "--upgrade", "pip"])

    # Build the install spec
    install_spec = "."
    if extras:
        extra_str = ",".join(extras)
        install_spec = f".[{extra_str}]"

    run([py, "-m", "pip", "install", "-e", install_spec])
    _print("Dependencies installed", "ok")

    # Print activation instructions
    py = find_python(venv)
    _print("", "info")
    if platform.system() == "Windows":
        _print("Activate the virtual environment:", "info")
        _print(f"  PowerShell:  .\\{VENV_DIR}\\Scripts\\Activate.ps1", "info")
        _print(f"  CMD:         .\\{VENV_DIR}\\Scripts\\activate.bat", "info")
        _print(f"  Or run directly: {py} -m atc --help", "info")
    else:
        _print("Activate the virtual environment:", "info")
        _print(f"  source {VENV_DIR}/bin/activate", "info")
        _print(f"  Or run directly: {py} -m atc --help", "info")


def create_env_file() -> None:
    """Create .env from .env.example if it doesn't exist."""
    env_file = Path(".env")
    example = Path(".env.example")
    if not env_file.exists() and example.exists():
        shutil.copy(example, env_file)
        _print("Created .env from .env.example — edit it with your credentials", "ok")
    elif env_file.exists():
        _print(".env already exists", "ok")


def main() -> None:
    parser = argparse.ArgumentParser(description="Set up ATC development environment")
    parser.add_argument(
        "--extras",
        nargs="*",
        default=[],
        choices=EXTRAS + ["all"],
        help="Optional dependency groups to install",
    )
    args = parser.parse_args()

    extras: list[str] = args.extras or []
    if "all" in extras:
        extras = EXTRAS

    print()
    print("ATC Environment Setup")
    print("=" * 40)
    print(f"  Platform: {platform.system()} {platform.machine()}")
    print()

    check_python_version()

    uv = find_uv()
    if uv:
        setup_with_uv(uv, extras)
    else:
        setup_with_pip(extras)

    create_env_file()

    print()
    print("Setup complete!")
    print()

    # Show the right run command
    if uv:
        print("  Run ATC:")
        print("    uv run python -m atc --help")
    else:
        py = find_python(Path(VENV_DIR))
        print("  Run ATC:")
        print(f"    {py} -m atc --help")

    print()


if __name__ == "__main__":
    main()
