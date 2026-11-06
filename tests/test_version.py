"""Version single source of truth (extended by the v0.4.0 grill).

The VERSION file, ``pyproject.toml``, the package ``__version__``, the
``--version`` CLI output, the newest CHANGELOG heading and the Pages
``meta.content_version`` must stay in lockstep. Everything runs in-process
(tomllib + typer's CliRunner) — no subprocess or binary dependency, so it
runs on any CI runner.
"""

from __future__ import annotations

import json
import re
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


def _newest_changelog_version() -> str:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    match = re.search(r"^## \[(\d+\.\d+\.\d+)\]", text, re.MULTILINE)
    assert match is not None, "CHANGELOG.md has no version heading"
    return match.group(1)


def _site_content_version() -> str:
    data = json.loads((ROOT / "web" / "site.json").read_text(encoding="utf-8"))
    return data["meta"]["content_version"]


def test_version_surfaces_are_in_lockstep():
    assert _version_file() == _pyproject_version()
    assert _pyproject_version() == margledger.__version__


def test_changelog_head_matches_version():
    assert _newest_changelog_version() == _version_file()


def test_site_content_version_matches_version():
    assert _site_content_version() == f"v{_version_file()}"


def test_cli_version_flag_prints_package_version():
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0
    assert f"margledger {margledger.__version__}" in result.output
