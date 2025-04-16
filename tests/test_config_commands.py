"""
Tests for KiCad Library Manager config commands.
"""

import os
import pytest
from pathlib import Path
from click.testing import CliRunner

from kicad_lib_manager.cli import main
from kicad_lib_manager.config import Config

# Sample test data
TEST_LIBRARIES = [
    {
        "name": "test-github-lib",
        "path": "/path/to/github/library",
        "type": "github"
    },
    {
        "name": "test-cloud-lib",
        "path": "/path/to/cloud/library",
        "type": "cloud"
    }
]


@pytest.fixture
def mock_config(monkeypatch):
    """Create a mock config for testing."""
    config = Config()
    
    # Mock the _load_config method to not actually load from disk
    def mock_load_config():
        config._config = {
            "max_backups": 5,
            "libraries": TEST_LIBRARIES.copy(),
            "current_library": TEST_LIBRARIES[0]["path"]
        }
    
    monkeypatch.setattr(config, "_load_config", mock_load_config)
    
    # Mock the save method to not actually write to disk
    monkeypatch.setattr(config, "save", lambda: None)
    
    # Return the config
    config._load_config()
    return config


@pytest.fixture
def mock_config_class(monkeypatch, mock_config):
    """Mock the Config class to return our mock config."""
    monkeypatch.setattr("kicad_lib_manager.commands.config.Config", lambda: mock_config)
    return mock_config


def test_config_list(mock_config_class):
    """Test the 'kilm config list' command."""
    runner = CliRunner()
    result = runner.invoke(main, ["config", "list"])
    
    assert result.exit_code == 0
    assert "Configured Libraries" in result.output
    assert "GitHub Libraries" in result.output
    assert "Cloud Libraries" in result.output
    assert "test-github-lib" in result.output
    assert "test-cloud-lib" in result.output
    assert "(current)" in result.output  # Current library should be marked


def test_config_list_filtered(mock_config_class):
    """Test the 'kilm config list --type github' command."""
    runner = CliRunner()
    result = runner.invoke(main, ["config", "list", "--type", "github"])
    
    assert result.exit_code == 0
    assert "GitHub Libraries" in result.output
    assert "test-github-lib" in result.output
    assert "Cloud Libraries" not in result.output
    assert "test-cloud-lib" not in result.output


def test_config_set_default(mock_config_class):
    """Test the 'kilm config set-default' command."""
    runner = CliRunner()
    result = runner.invoke(main, ["config", "set-default", "test-cloud-lib", "--type", "cloud"])
    
    assert result.exit_code == 0
    assert "Set cloud library 'test-cloud-lib' as default" in result.output
    assert mock_config_class.get_current_library() == TEST_LIBRARIES[1]["path"]


def test_config_set_default_interactive(mock_config_class):
    """Test the interactive 'kilm config set-default' command."""
    runner = CliRunner()
    # Simulate user selecting the cloud library (option 2)
    result = runner.invoke(main, ["config", "set-default", "--type", "cloud"], input="1\n")
    
    assert result.exit_code == 0
    assert "Available cloud libraries:" in result.output
    assert "1. test-cloud-lib" in result.output
    assert "Set cloud library 'test-cloud-lib' as default" in result.output
    assert mock_config_class.get_current_library() == TEST_LIBRARIES[1]["path"]


def test_config_set_default_interactive_github(mock_config_class):
    """Test the interactive 'kilm config set-default' command with GitHub libraries."""
    runner = CliRunner()
    # Simulate user selecting the GitHub library (option 1)
    result = runner.invoke(main, ["config", "set-default"], input="1\n")
    
    assert result.exit_code == 0
    assert "Available github libraries:" in result.output
    assert "1. test-github-lib" in result.output
    assert "Set github library 'test-github-lib' as default" in result.output
    assert mock_config_class.get_current_library() == TEST_LIBRARIES[0]["path"]


def test_config_set_default_not_found(mock_config_class):
    """Test 'kilm config set-default' with non-existent library."""
    runner = CliRunner()
    result = runner.invoke(main, ["config", "set-default", "non-existent-lib"])
    
    assert result.exit_code != 0
    assert "No github library named 'non-existent-lib' found" in result.output


def test_config_remove(mock_config_class):
    """Test the 'kilm config remove' command."""
    runner = CliRunner()
    # Use --force to bypass confirmation prompt
    result = runner.invoke(main, ["config", "remove", "test-github-lib", "--force"])
    
    assert result.exit_code == 0
    assert "Removed library 'test-github-lib'" in result.output
    
    # Verify the library was removed
    remaining_libraries = mock_config_class.get_libraries()
    assert len(remaining_libraries) == 1
    assert remaining_libraries[0]["name"] == "test-cloud-lib"


def test_config_remove_with_confirmation(mock_config_class):
    """Test 'kilm config remove' with confirmation prompt."""
    runner = CliRunner()
    # Simulate user confirming the removal
    result = runner.invoke(main, ["config", "remove", "test-github-lib"], input="y\n")
    
    assert result.exit_code == 0
    assert "Will remove github library 'test-github-lib'" in result.output
    assert "Removed library 'test-github-lib'" in result.output


def test_config_remove_not_found(mock_config_class):
    """Test 'kilm config remove' with non-existent library."""
    runner = CliRunner()
    result = runner.invoke(main, ["config", "remove", "non-existent-lib", "--force"])
    
    assert result.exit_code != 0
    assert "No library named 'non-existent-lib' found" in result.output 