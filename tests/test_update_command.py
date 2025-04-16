"""
Tests for KiCad Library Manager update command.
"""

import os
import pytest
from unittest.mock import patch, MagicMock, Mock
from pathlib import Path
from click.testing import CliRunner

from kicad_lib_manager.cli import main
from kicad_lib_manager.commands.update import check_for_library_changes

# Sample test libraries
TEST_LIBRARIES = [
    {
        "name": "test-lib",
        "path": "/path/to/test/library",
        "type": "github"
    }
]


@pytest.fixture
def mock_config(monkeypatch):
    """Mock configuration with test libraries."""
    config_mock = MagicMock()
    config_mock.get_libraries.return_value = TEST_LIBRARIES
    
    monkeypatch.setattr("kicad_lib_manager.commands.update.Config", lambda: config_mock)
    return config_mock


@pytest.fixture
def mock_subprocess_run(monkeypatch):
    """Mock subprocess.run to simulate git pull results."""
    run_mock = MagicMock()
    # Return successful git pull by default
    result = MagicMock()
    result.returncode = 0
    result.stdout = "Updating abcd123..efgh456\nsymbols/newlib.kicad_sym | 120 ++++++++++++\n1 file changed"
    run_mock.return_value = result
    
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
    

def test_update_command(mock_config, mock_subprocess_run, mock_path_methods):
    """Test the basic update command."""
    runner = CliRunner()
    result = runner.invoke(main, ["update"])
    
    assert result.exit_code == 0
    assert "Updating 1 KiCad GitHub libraries" in result.output
    assert "Updated" in result.output
    assert "1 libraries updated" in result.output
    
    # Verify subprocess was called correctly
    mock_subprocess_run.assert_called_once()
    args, kwargs = mock_subprocess_run.call_args
    assert args[0] == ["git", "pull"]
    assert kwargs["check"] is False


def test_update_with_auto_setup(mock_config, mock_subprocess_run, mock_path_methods):
    """Test update with auto-setup option."""
    # Create a mock context to track invocation
    context_mock = Mock()
    
    # Mock the Context class constructor to return our mock
    with patch('click.Context', return_value=context_mock):
        # Mock the setup module import
        setup_module_mock = Mock()
        setup_module_mock.setup = Mock(name="setup_command")
        
        # Mock the module import
        with patch.dict('sys.modules', {'kicad_lib_manager.commands.setup': setup_module_mock}):
            runner = CliRunner()
            result = runner.invoke(main, ["update", "--auto-setup"])
            
            assert result.exit_code == 0
            assert "Running 'kilm setup'" in result.output
            
            # Since we've mocked Context and the setup module is properly returned by 
            # the import, we can verify the test succeeded if the output contains the 
            # expected message about running setup


def test_update_with_already_up_to_date(mock_config, mock_path_methods):
    """Test update when repositories are already up to date."""
    # Create a mock that returns "Already up to date" for git pull
    mock_run = MagicMock()
    result = MagicMock()
    result.returncode = 0
    result.stdout = "Already up to date."
    mock_run.return_value = result
    
    with patch("subprocess.run", mock_run):
        runner = CliRunner()
        result = runner.invoke(main, ["update"])
        
        assert result.exit_code == 0
        assert "Up to date" in result.output
        assert "0 libraries updated" in result.output
        assert "1 libraries up to date" in result.output


def test_update_with_verbose(mock_config, mock_subprocess_run, mock_path_methods):
    """Test update with verbose option."""
    runner = CliRunner()
    result = runner.invoke(main, ["update", "--verbose"])
    
    assert result.exit_code == 0
    assert "Success:" in result.output


def test_update_dry_run(mock_config, mock_subprocess_run, mock_path_methods):
    """Test update with dry-run option."""
    runner = CliRunner()
    result = runner.invoke(main, ["update", "--dry-run"])
    
    assert result.exit_code == 0
    assert "Dry run: would execute 'git pull'" in result.output
    
    # Verify subprocess was not called for git pull
    mock_subprocess_run.assert_not_called()


def test_update_no_libraries(monkeypatch):
    """Test update when no libraries are configured."""
    config_mock = MagicMock()
    config_mock.get_libraries.return_value = []
    monkeypatch.setattr("kicad_lib_manager.commands.update.Config", lambda: config_mock)
    
    runner = CliRunner()
    result = runner.invoke(main, ["update"])
    
    assert result.exit_code == 0
    assert "No GitHub libraries configured" in result.output


def test_check_for_library_changes():
    """Test the library change detection function."""
    # Create a temporary test directory
    tmp_path = Path("/tmp/test_lib")
    
    # Test with git output indicating new symbol library
    git_output = "symbols/newlib.kicad_sym | 120 ++++++++++"
    
    # Mock file existence with a patch
    with patch.object(Path, "exists", return_value=True), \
         patch.object(Path, "is_dir", return_value=True), \
         patch.object(Path, "glob") as mock_glob:
        
        # Setup mock glob to return different files based on pattern
        def mock_glob_func(pattern):
            if "**/*.kicad_sym" in pattern:
                mock_file = MagicMock()
                mock_file.name = "test.kicad_sym"
                return [mock_file]
            elif "**/*.pretty" in pattern:
                return []
            elif "*" in pattern:
                return []
            return []
            
        mock_glob.side_effect = mock_glob_func
        
        # Test the function
        changes = check_for_library_changes(git_output, tmp_path)
        assert "symbols" in changes
        assert "footprints" not in changes
        assert "templates" not in changes 