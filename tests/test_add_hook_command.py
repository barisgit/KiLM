"""Tests for ``kilm add-hook`` in temporary repositories."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from kicad_lib_manager.main import app

GIT = shutil.which("git")

pytestmark = pytest.mark.skipif(GIT is None, reason="git is not installed")


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Return an empty git repository isolated from the user's git config."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / ".gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    repo = tmp_path / "repo"
    repo.mkdir()
    assert GIT is not None
    subprocess.run(  # noqa: S603 -- fixed git arguments built by the test
        [GIT, "init", "--quiet"], cwd=repo, check=True
    )
    return repo


def test_add_hook_installs_an_executable_post_merge_hook(repo: Path) -> None:
    """The hook runs ``kilm sync`` and uses LF line endings on every platform."""
    result = CliRunner().invoke(app, ["add-hook", "--directory", str(repo)])

    assert result.exit_code == 0, result.output
    hook = repo / ".git" / "hooks" / "post-merge"
    content = hook.read_bytes()
    assert b"kilm sync" in content
    assert b"\r\n" not in content
    if os.name != "nt":
        assert hook.stat().st_mode & 0o111


def test_add_hook_merges_into_an_existing_hook(repo: Path) -> None:
    """Without ``--force`` an existing hook keeps its own commands."""
    hook = repo / ".git" / "hooks" / "post-merge"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text("#!/bin/sh\necho mine\n", encoding="utf-8")

    result = CliRunner().invoke(
        app, ["add-hook", "--directory", str(repo)], input="y\n"
    )

    assert result.exit_code == 0, result.output
    content = hook.read_text(encoding="utf-8")
    assert "echo mine" in content
    assert "kilm sync" in content
    assert len(list(hook.parent.glob("post-merge.backup.*"))) == 1


def test_add_hook_outside_a_repository_reports_one_error(tmp_path: Path) -> None:
    """A directory that is not a repository fails with a single error line."""
    result = CliRunner().invoke(app, ["add-hook", "--directory", str(tmp_path)])

    assert result.exit_code == 1
    assert result.output.count("Error") == 1, result.output
