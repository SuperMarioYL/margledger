"""Version single source of truth (added by the v0.3.0 grill).

The VERSION file, ``pyproject.toml``, the package ``__version__`` and the
``--version`` CLI output must stay in lockstep. Everything runs in-process
(tomllib + typer's CliRunner) — no subprocess or binary dependency, so it
runs on any CI runner.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import margledger
from margledger.cli import app
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parent.parent


def _version_file() -> str:
    return (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def _pyproject_version() -> str:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return data["project"]["version"]


def test_version_surfaces_are_in_lockstep():
    assert _version_file() == _pyproject_version()
    assert _pyproject_version() == margledger.__version__


def test_cli_version_flag_prints_package_version():
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0
    assert f"margledger {margledger.__version__}" in result.output
