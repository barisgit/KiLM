"""Tests for ``kilm sync`` against real git repositories in a temporary directory."""

import shutil
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from kicad_lib_manager.commands.setup import command as setup_command
from kicad_lib_manager.commands.sync import command as sync_command
from kicad_lib_manager.commands.sync.command import check_for_library_changes
from kicad_lib_manager.main import app
from kicad_lib_manager.services.config_service import LibraryDict

GIT = shutil.which("git")

pytestmark = pytest.mark.skipif(GIT is None, reason="git is not installed")


def _git(repo: Path, *args: str) -> str:
    assert GIT is not None
    result = subprocess.run(  # noqa: S603 -- fixed git arguments built by the tests
        [GIT, *args], cwd=repo, capture_output=True, text=True, check=True
    )
    return result.stdout


def _commit_file(repo: Path, relative: str, message: str) -> None:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(message, encoding="utf-8")
    _git(repo, "add", "--all")
    _git(repo, "commit", "--quiet", "--message", message)


class FakeConfig:
    """Stands in for ``Config`` with a fixed list of GitHub libraries."""

    def __init__(self, libraries: list[LibraryDict]) -> None:
        """Serve ``libraries`` from ``get_libraries``."""
        self.libraries = libraries

    def get_libraries(self, library_type: str | None = None) -> list[LibraryDict]:
        """Return the configured libraries of ``library_type``."""
        return [lib for lib in self.libraries if lib["type"] == library_type]


@pytest.fixture(autouse=True)
def isolated_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep git and KiLM away from the user's configuration."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(home / ".gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("LC_ALL", "C")
    for role in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{role}_NAME", "KiLM Test")
        monkeypatch.setenv(f"GIT_{role}_EMAIL", "kilm@example.com")


@pytest.fixture
def upstream(tmp_path: Path) -> Path:
    """Return a repository with one commit that a library clones."""
    repo = tmp_path / "upstream"
    repo.mkdir()
    _git(repo, "init", "--quiet")
    _commit_file(repo, "README.md", "initial")
    return repo


@pytest.fixture
def library(tmp_path: Path, upstream: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Return a clone of ``upstream`` registered as the only GitHub library."""
    clone = tmp_path / "library"
    _git(tmp_path, "clone", "--quiet", str(upstream), str(clone))
    config = FakeConfig([{"name": "demo", "path": str(clone), "type": "github"}])
    monkeypatch.setattr(sync_command, "Config", lambda: config)
    return clone


def test_sync_reports_an_up_to_date_library(library: Path) -> None:
    """A pull that brings nothing counts as up to date."""
    result = CliRunner().invoke(app, ["sync"])

    assert result.exit_code == 0, result.output
    assert "Syncing 1 KiCad GitHub libraries" in result.output
    assert "0 libraries synced" in result.output
    assert "1 libraries up to date" in result.output
    assert "No new libraries detected" in result.output


def test_sync_pulls_and_detects_new_libraries(upstream: Path, library: Path) -> None:
    """New symbol libraries anywhere in the pulled commits are reported."""
    _commit_file(upstream, "symbols/New.kicad_sym", "add symbols")
    _commit_file(upstream, "docs/notes.md", "add notes")

    result = CliRunner().invoke(app, ["sync"])

    assert result.exit_code == 0, result.output
    assert (library / "symbols" / "New.kicad_sym").exists()
    assert "1 libraries synced" in result.output
    assert "demo: symbols" in result.output
    assert "kilm sync --auto-setup" in result.output


def test_sync_counts_an_up_to_date_pull_in_any_language(
    library: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Up to date is judged by HEAD, not by the wording of git's message."""
    monkeypatch.setenv("LC_ALL", "de_DE.UTF-8")
    monkeypatch.delenv("LANGUAGE", raising=False)
    if "Already up to date" in _git(library, "pull"):
        pytest.skip("git has no German translation here")

    result = CliRunner().invoke(app, ["sync"])

    assert result.exit_code == 0, result.output
    assert "0 libraries synced" in result.output
    assert "1 libraries up to date" in result.output


def test_sync_dry_run_does_not_pull(upstream: Path, library: Path) -> None:
    """A dry run names the library and leaves it untouched."""
    _commit_file(upstream, "symbols/New.kicad_sym", "add symbols")

    result = CliRunner().invoke(app, ["sync", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "Dry run: would execute 'git pull'" in result.output
    assert not (library / "symbols").exists()


def test_sync_auto_setup_runs_setup_with_its_defaults(
    upstream: Path, library: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Setup runs with its option defaults, so it looks up the library itself."""
    monkeypatch.setattr(
        setup_command, "find_environment_variables", lambda _name: None
    )
    _commit_file(upstream, "symbols/New.kicad_sym", "add symbols")

    result = CliRunner().invoke(app, ["sync", "--auto-setup"])

    assert "Running 'kilm setup'" in result.output
    assert "KICAD_USER_LIB not set and not provided" in result.output
    assert "Error: 1" not in result.output
    assert result.exit_code == 1


def test_sync_skips_a_directory_that_is_not_a_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A configured path without ``.git`` is skipped, not pulled."""
    plain = tmp_path / "plain"
    plain.mkdir()
    config = FakeConfig([{"name": "plain", "path": str(plain), "type": "github"}])
    monkeypatch.setattr(sync_command, "Config", lambda: config)

    result = CliRunner().invoke(app, ["sync"])

    assert result.exit_code == 0, result.output
    assert "Not a git repository" in result.output
    assert "1 libraries skipped" in result.output


def test_sync_without_libraries(monkeypatch: pytest.MonkeyPatch) -> None:
    """No configured GitHub library is not an error."""
    monkeypatch.setattr(sync_command, "Config", lambda: FakeConfig([]))

    result = CliRunner().invoke(app, ["sync"])

    assert result.exit_code == 0
    assert "No GitHub libraries configured" in result.output


def test_check_for_library_changes_without_history(tmp_path: Path) -> None:
    """Without a previous commit the current content is reported."""
    repo = tmp_path / "fresh"
    repo.mkdir()
    _git(repo, "init", "--quiet")
    _commit_file(repo, "footprints/Part.pretty/Part.kicad_mod", "footprint")
    _commit_file(repo, "templates/basic/metadata.yaml", "template")
    (repo / "symbols").mkdir()

    assert check_for_library_changes(repo) == ["templates"]
    assert sorted(check_for_library_changes(repo, "HEAD~5")) == [
        "footprints",
        "templates",
    ]


def test_check_for_library_changes_detects_a_renamed_library(tmp_path: Path) -> None:
    """A renamed library file is a new library name that setup must add."""
    repo = tmp_path / "renamed"
    repo.mkdir()
    _git(repo, "init", "--quiet")
    _commit_file(repo, "symbols/Old.kicad_sym", "symbols")
    _git(repo, "mv", "symbols/Old.kicad_sym", "symbols/New.kicad_sym")
    _git(repo, "commit", "--quiet", "--message", "rename")

    assert check_for_library_changes(repo) == ["symbols"]
