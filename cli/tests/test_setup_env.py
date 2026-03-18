"""Tests for the setup helper script."""

from __future__ import annotations

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import setup_env


def test_supported_python_versions_include_312_and_313() -> None:
    assert setup_env.is_supported_python_version((3, 12))
    assert setup_env.is_supported_python_version((3, 13))


def test_supported_python_versions_exclude_out_of_range_versions() -> None:
    assert not setup_env.is_supported_python_version((3, 11))
    assert not setup_env.is_supported_python_version((3, 14))


def test_supported_python_label_matches_project_range() -> None:
    assert setup_env.supported_python_label() == "Python 3.12 or 3.13"
