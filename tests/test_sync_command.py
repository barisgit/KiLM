"""
Tests for KiCad Library Manager sync command (formerly update command).
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from kicad_lib_manager.commands.sync.command import check_for_library_changes
from kicad_lib_manager.main import app as main

# Sample test libraries
TEST_LIBRARIES = [
    {"name": "test-lib", "path": "/path/to/test/library", "type": "github"}
]


@pytest.fixture
def mock_config(monkeypatch):
    """Mock configuration with test libraries."""
    config_mock = MagicMock()
    config_mock.get_libraries.return_value = TEST_LIBRARIES

    monkeypatch.setattr(
        "kicad_lib_manager.commands.sync.command.Config", lambda: config_mock
    )
    return config_mock


@pytest.fixture
def mock_subprocess_run(monkeypatch):
    """Mock subprocess.run to simulate git pull and git diff results."""
    run_mock = MagicMock()

    # Create different results for different calls
    def mock_run_side_effect(*args, **kwargs):
        result = MagicMock()
        result.returncode = 0

        # Check if this is a git diff call
        if args[0] == ["git", "diff", "--name-status", "HEAD~1", "HEAD"]:
            result.stdout = "A\tsymbols/newlib.kicad_sym"
        else:
            # This is a git pull call
            result.stdout = "Updating abcd123..efgh456\nsymbols/newlib.kicad_sym | 120 ++++++++++++\n1 file changed"

        return result

    run_mock.side_effect = mock_run_side_effect
    monkeypatch.setattr("subprocess.run", run_mock)
    return run_mock


@pytest.fixture
def mock_path_methods(monkeypatch):
    """Mock Path methods to simulate filesystem."""

    # Mock Path.exists to return True for all paths to avoid "Path does not exist" errors
    def mock_exists(self):
        return True

    # Mock Path.is_dir to return True for directories
    def mock_is_dir(self):
        return True

    # Mock Path / operator to properly build paths
    def mock_truediv(self, other):
        return Path(f"{self}/{other}")

    # Mock glob to simulate finding library files
    def mock_glob(self, pattern):
        if "**/*.kicad_sym" in pattern:
            mock_file = MagicMock()
            mock_file.name = "test.kicad_sym"
            return [mock_file]
        elif "**/*.pretty" in pattern:
            mock_dir = MagicMock()
            mock_dir.name = "test.pretty"
            mock_dir.is_dir.return_value = True
            return [mock_dir]
        elif "*" in pattern and "metadata.yaml" not in str(self):
            mock_dir = MagicMock()
            mock_dir.name = "template-dir"
            mock_dir.__truediv__ = lambda self, other: Path(f"{self}/{other}")
            mock_dir.exists = lambda: True
            return [mock_dir]
        return []

    monkeypatch.setattr(Path, "exists", mock_exists)
    monkeypatch.setattr(Path, "is_dir", mock_is_dir)
    monkeypatch.setattr(Path, "__truediv__", mock_truediv)
    monkeypatch.setattr(Path, "glob", mock_glob)


def test_sync_command(mock_config, mock_subprocess_run, mock_path_methods):
    """Test the basic sync command."""
    runner = CliRunner()
    result = runner.invoke(main, ["sync"])

    assert result.exit_code == 0
    assert "Syncing 1 KiCad GitHub libraries" in result.output
    assert "Updated" in result.output
    assert "1 libraries synced" in result.output

    # Verify subprocess was called correctly
    # Should be called twice: once for git pull, once for git diff
    assert mock_subprocess_run.call_count == 2

    # Check the first call (git pull)
    first_call_args, first_call_kwargs = mock_subprocess_run.call_args_list[0]
    assert first_call_args[0] == ["git", "pull"]
    assert first_call_kwargs["check"] is False

    # Check the second call (git diff)
    second_call_args, second_call_kwargs = mock_subprocess_run.call_args_list[1]
    assert second_call_args[0] == ["git", "diff", "--name-status", "HEAD~1", "HEAD"]
    assert second_call_kwargs["check"] is False


def test_sync_with_auto_setup(mock_config, mock_subprocess_run, mock_path_methods):
    """Test sync with auto-setup option."""
    # Mock the setup command function (imported within sync function)
    with patch("kicad_lib_manager.commands.setup.command.setup") as mock_setup:
        mock_setup.return_value = None  # setup function returns None on success

        runner = CliRunner()
        result = runner.invoke(main, ["sync", "--auto-setup"])

        assert result.exit_code == 0
        assert "Running 'kilm setup'" in result.output

        # Verify that setup was called
        mock_setup.assert_called_once()


def test_sync_with_already_up_to_date(mock_config, mock_path_methods):
    """Test update when repositories are already up to date."""
    # Create a mock that returns "Already up to date" for git pull
    mock_run = MagicMock()
    result = MagicMock()
    result.returncode = 0
    result.stdout = "Already up to date."
    mock_run.return_value = result

    with patch("subprocess.run", mock_run):
        runner = CliRunner()
        result = runner.invoke(main, ["sync"])

        assert result.exit_code == 0
        assert "Up to date" in result.output
        assert "0 libraries synced" in result.output
        assert "1 libraries up to date" in result.output


def test_sync_with_verbose(mock_config, mock_subprocess_run, mock_path_methods):
    """Test update with verbose option."""
    runner = CliRunner()
    result = runner.invoke(main, ["sync", "--verbose"])

    assert result.exit_code == 0
    assert "Success:" in result.output


def test_sync_dry_run(mock_config, mock_subprocess_run, mock_path_methods):
    """Test update with dry-run option."""
    runner = CliRunner()
    result = runner.invoke(main, ["sync", "--dry-run"])

    assert result.exit_code == 0
    assert "Dry run: would execute 'git pull'" in result.output

    # Verify subprocess was not called for git pull
    mock_subprocess_run.assert_not_called()


def test_sync_no_libraries(monkeypatch):
    """Test sync when no libraries are configured."""
    config_mock = MagicMock()
    config_mock.get_libraries.return_value = []
    monkeypatch.setattr(
        "kicad_lib_manager.commands.sync.command.Config", lambda: config_mock
    )

    runner = CliRunner()
    result = runner.invoke(main, ["sync"])

    assert result.exit_code == 0
    assert "No GitHub libraries configured" in result.output


def test_check_for_library_changes():
    """Test the library change detection function."""
    # Create a temporary test directory
    tmp_path = Path("/tmp/test_lib")

    # Mock subprocess.run to simulate git diff output
    with patch("subprocess.run") as mock_run:
        # Mock successful git diff with symbol library changes
        result = MagicMock()
        result.returncode = 0
        result.stdout = (
            "A\tsymbols/newlib.kicad_sym\nM\tfootprints/existing.pretty/file.kicad_mod"
        )
        mock_run.return_value = result

        # Test the function with new signature (only lib_path)
        changes = check_for_library_changes(tmp_path)

        # Should detect both symbols and footprints changes
        assert "symbols" in changes
        assert "footprints" in changes
        assert "templates" not in changes

        # Verify git diff was called correctly
        mock_run.assert_called_once_with(
            ["git", "diff", "--name-status", "HEAD~1", "HEAD"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=False,
        )


def test_check_for_library_changes_fallback():
    """Test the library change detection function fallback when git diff fails."""
    # Create a temporary test directory
    tmp_path = Path("/tmp/test_lib")

    # Mock subprocess.run to simulate git diff failure
    with patch("subprocess.run") as mock_run:
        # Mock failed git diff
        result = MagicMock()
        result.returncode = 1
        result.stdout = ""
        mock_run.return_value = result

        # Mock file existence with a patch for fallback behavior
        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "is_dir", return_value=True),
            patch.object(Path, "glob") as mock_glob,
        ):
            # Setup mock glob to return symbol files
            def mock_glob_func(pattern):
                if "**/*.kicad_sym" in pattern:
                    mock_file = MagicMock()
                    mock_file.name = "test.kicad_sym"
                    return [mock_file]
                return []

            mock_glob.side_effect = mock_glob_func

            # Test the function fallback behavior
            changes = check_for_library_changes(tmp_path)
            assert "symbols" in changes
            assert "footprints" not in changes
            assert "templates" not in changes
