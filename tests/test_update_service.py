"""
Tests for the update service functionality including installation detection and update operations.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests

from kicad_lib_manager.services.update_service import (
    InstallationDetector,
    UpdateManager,
    UpdateService,
    detect_installation_method,
)


class TestInstallationDetection:
    """Test installation method detection logic using the modular detector."""

    def test_detect_pipx_installation_path_pattern(self):
        """Test detection of pipx installation via path pattern."""
        detector = InstallationDetector(
            executable_path=Path("/Users/user/.local/share/pipx/venvs/kilm/bin/python")
        )
        assert detector.detect_pipx() is True
        assert detector.detect() == "pipx"

    def test_detect_pipx_installation_with_env_var(self, monkeypatch):
        """Test detection of pipx installation via environment variable."""
        monkeypatch.setenv("PIPX_HOME", "/Users/user/.local/share/pipx")

        detector = InstallationDetector(executable_path=Path("/opt/pipx/bin/python"))
        assert detector.detect_pipx() is True
        assert detector.detect() == "pipx"

    def test_detect_conda_installation_path_pattern(self):
        """Test detection of conda installation via path pattern."""
        detector = InstallationDetector(
            executable_path=Path("/opt/miniconda3/envs/kilm/bin/python")
        )
        assert detector.detect_conda() is True
        assert detector.detect() == "conda"

    def test_detect_conda_installation_with_env_var(self, monkeypatch):
        """Test detection of conda installation via environment variable."""
        monkeypatch.setenv("CONDA_DEFAULT_ENV", "kilm-env")

        detector = InstallationDetector(executable_path=Path("/usr/bin/python"))
        assert detector.detect_conda() is True
        assert detector.detect() == "conda"

    def test_detect_uv_installation_env_vars(self, monkeypatch):
        """Test detection of UV installation via environment variables."""
        monkeypatch.setenv("UV_TOOL_DIR", "/Users/user/.local/share/uv")

        detector = InstallationDetector(executable_path=Path("/usr/bin/python"))
        assert detector.detect_uv() is True
        assert detector.detect() == "uv"

    def test_detect_uv_installation_path_patterns(self):
        """Test detection of UV installation via path patterns."""
        detector = InstallationDetector(
            executable_path=Path("/Users/user/.local/share/uv/tools/kilm/bin/python")
        )
        assert detector.detect_uv() is True
        assert detector.detect() == "uv"

    def test_detect_pip_venv_installation_env_var(self, monkeypatch):
        """Test detection of pip in virtual environment via VIRTUAL_ENV."""
        monkeypatch.setenv("VIRTUAL_ENV", "/path/to/venv")

        detector = InstallationDetector(
            executable_path=Path("/path/to/venv/bin/python")
        )
        assert detector.detect_virtual_env() is True
        assert detector.detect() == "pip-venv"

    def test_detect_pip_venv_installation_prefix_check(self, monkeypatch):
        """Test detection of pip in venv via sys.prefix check."""
        # Mock sys.prefix and base_prefix to simulate virtual environment
        monkeypatch.setattr(sys, "prefix", "/path/to/venv")
        monkeypatch.setattr(sys, "base_prefix", "/usr/local")

        detector = InstallationDetector(
            executable_path=Path("/path/to/venv/bin/python")
        )
        assert detector.detect_virtual_env() is True
        assert detector.detect() == "pip-venv"

    def test_platform_detection(self):
        """Test platform detection methods."""
        # Test Windows detection
        windows_detector = InstallationDetector(platform_name="nt")
        assert windows_detector.is_windows() is True
        assert windows_detector.is_unix_like() is False

        # Test Unix detection
        unix_detector = InstallationDetector(platform_name="posix")
        assert unix_detector.is_windows() is False
        assert unix_detector.is_unix_like() is True

    def test_priority_order(self):
        """Test that detection follows correct priority order."""
        # pipx should take priority over pip-venv
        with (
            patch.object(sys, "prefix", "/path/to/venv"),
            patch.object(sys, "base_prefix", "/usr/local"),
        ):
            detector = InstallationDetector(
                executable_path=Path(
                    "/Users/user/.local/share/pipx/venvs/kilm/bin/python"
                )
            )
            assert detector.detect() == "pipx"  # pipx wins over pip-venv

    def test_legacy_detect_installation_method_function(self, monkeypatch):
        """Test that the legacy function still works."""
        monkeypatch.setattr(
            sys, "executable", "/Users/user/.local/share/pipx/venvs/kilm/bin/python"
        )
        result = detect_installation_method()
        assert result == "pipx"


class TestUpdateManager:
    """Test UpdateManager functionality."""

    @pytest.fixture
    def update_manager(self):
        """Create an UpdateManager instance for testing."""
        with patch(
            "kicad_lib_manager.services.update_service.detect_installation_method"
        ) as mock_detect:
            mock_detect.return_value = "pip"
            return UpdateManager("1.0.0")

    def test_version_comparison(self, update_manager):
        """Test version comparison logic."""
        assert update_manager.is_newer_version_available("1.1.0") is True
        assert update_manager.is_newer_version_available("1.0.0") is False
        assert update_manager.is_newer_version_available("0.9.0") is False

    def test_invalid_version_comparison(self, update_manager):
        """Test handling of invalid version strings."""
        assert update_manager.is_newer_version_available("invalid-version") is False

    def test_can_auto_update_supported_methods(self, monkeypatch):
        """Test auto-update support for supported installation methods."""
        for method in ["pipx", "pip", "pip-venv", "uv"]:
            with patch(
                "kicad_lib_manager.services.update_service.detect_installation_method"
            ) as mock_detect:
                mock_detect.return_value = method
                manager = UpdateManager("1.0.0")
                assert manager.can_auto_update() is True

    def test_can_auto_update_unsupported_methods(self, monkeypatch):
        """Test auto-update support for unsupported installation methods."""
        for method in ["conda", "homebrew"]:
            with patch(
                "kicad_lib_manager.services.update_service.detect_installation_method"
            ) as mock_detect:
                mock_detect.return_value = method
                manager = UpdateManager("1.0.0")
                assert manager.can_auto_update() is False

    def test_get_update_instructions(self):
        """Test getting update instructions for different installation methods."""
        test_cases = [
            ("pipx", "pipx upgrade kilm"),
            ("pip", "pip install --upgrade kilm"),
            ("pip-venv", "pip install --upgrade kilm"),
            ("uv", "uv tool upgrade kilm"),
            ("conda", "Conda package not yet available (planned for future)"),
            ("homebrew", "Homebrew package not yet available (planned for future)"),
        ]

        for method, expected in test_cases:
            with patch(
                "kicad_lib_manager.services.update_service.detect_installation_method"
            ) as mock_detect:
                mock_detect.return_value = method
                manager = UpdateManager("1.0.0")
                assert manager.get_update_instruction() == expected


class TestUpdateService:
    """Test UpdateService functionality."""

    @pytest.fixture
    def update_service(self):
        """Create an UpdateService instance for testing."""
        with patch(
            "kicad_lib_manager.services.update_service.detect_installation_method"
        ) as mock_detect:
            mock_detect.return_value = "pip"
            return UpdateService("1.0.0")

    def test_check_for_updates_no_update_available(self, update_service):
        """Test check for updates when no update is available."""
        with (
            patch.object(update_service.manager, "check_latest_version") as mock_check,
            patch.object(
                update_service.manager, "is_newer_version_available"
            ) as mock_newer,
        ):
            mock_check.return_value = "1.0.0"
            mock_newer.return_value = False

            result = update_service.check_for_updates()

            assert result["has_update"] is False
            assert result["current_version"] == "1.0.0"
            assert result["latest_version"] == "1.0.0"
            assert result["method"] == "pip"
            assert "supports_auto_update" in result

    def test_check_for_updates_update_available(self, update_service):
        """Test check for updates when update is available."""
        with (
            patch.object(update_service.manager, "check_latest_version") as mock_check,
            patch.object(
                update_service.manager, "is_newer_version_available"
            ) as mock_newer,
        ):
            mock_check.return_value = "1.1.0"
            mock_newer.return_value = True

            result = update_service.check_for_updates()

            assert result["has_update"] is True
            assert result["current_version"] == "1.0.0"
            assert result["latest_version"] == "1.1.0"
            assert result["method"] == "pip"
            assert "supports_auto_update" in result

    def test_check_for_updates_no_latest_version(self, update_service):
        """Test check for updates when latest version cannot be determined."""
        with patch.object(update_service.manager, "check_latest_version") as mock_check:
            mock_check.return_value = None

            result = update_service.check_for_updates()

            assert result["has_update"] is False
            assert result["current_version"] == "1.0.0"
            assert result["latest_version"] is None
            assert result["method"] == "pip"

    def test_show_update_notification_no_update(self, update_service):
        """Test showing update notification when no update is available."""
        with (
            patch.object(update_service, "check_for_updates") as mock_check,
            patch("rich.console.Console") as mock_console,
        ):
            mock_check.return_value = {
                "has_update": False,
                "current_version": "1.0.0",
                "latest_version": "1.0.0",
                "method": "pip",
                "supports_auto_update": True,
            }

            result = update_service.show_update_notification()

            assert result is False
            # Verify the console was used to print the "latest version" message
            mock_console.assert_called()

    def test_show_update_notification_update_available(self, update_service):
        """Test showing update notification when update is available."""
        with (
            patch.object(update_service, "check_for_updates") as mock_check,
            patch("rich.console.Console") as mock_console,
            patch("rich.panel.Panel") as mock_panel,
        ):
            mock_check.return_value = {
                "has_update": True,
                "current_version": "1.0.0",
                "latest_version": "1.1.0",
                "method": "pip",
                "supports_auto_update": True,
            }

            result = update_service.show_update_notification()

            assert result is True
            # Verify console and panel were used
            mock_console.assert_called()
            mock_panel.assert_called()

    def test_perform_update_dry_run(self, update_service):
        """Test dry run mode for updates."""
        with patch.object(update_service, "_show_dry_run_info") as mock_dry_run:
            mock_dry_run.return_value = (True, "Dry run message")

            success, message = update_service.perform_update(dry_run=True)

            assert success is True
            assert message == "Dry run message"
            mock_dry_run.assert_called_once_with(None)

    def test_perform_update_no_update_needed(self, update_service):
        """Test performing update when no update is needed."""
        with patch.object(update_service, "check_for_updates") as mock_check:
            mock_check.return_value = {"has_update": False}

            success, message = update_service.perform_update()

            assert success is True
            assert message == "Already using the latest version!"

    def test_perform_update_force_when_no_update_needed(self, update_service):
        """Test performing forced update when no update is needed."""
        with (
            patch.object(update_service, "check_for_updates") as mock_check,
            patch.object(update_service.manager, "perform_update") as mock_perform,
        ):
            mock_check.return_value = {"has_update": False}
            mock_perform.return_value = (True, "Update successful")

            success, message = update_service.perform_update(force=True)

            assert success is True
            assert message == "Update successful"
            mock_perform.assert_called_once()

    def test_dry_run_info_display(self, update_service):
        """Test dry run information display."""
        with (
            patch("rich.console.Console") as mock_console,
            patch("rich.panel.Panel") as mock_panel,
        ):
            success, message = update_service._show_dry_run_info("1.1.0")

            # Should return whether auto-update is supported
            assert isinstance(success, bool)
            assert "Dry run completed" in message

            # Verify console and panel were used
            mock_console.assert_called()
            mock_panel.assert_called()


class TestPyPIVersionChecker:
    """Test PyPI version checking functionality."""

    @pytest.fixture
    def version_checker(self):
        """Create a PyPIVersionChecker instance for testing."""
        from kicad_lib_manager.services.update_service import PyPIVersionChecker

        return PyPIVersionChecker("kilm", "1.0.0")

    def test_cache_file_location(self, version_checker):
        """Test that cache file is created in the correct location."""
        assert version_checker.cache_file.name == "version_check.json"
        assert "kilm" in str(version_checker.cache_file)

    @patch("requests.get")
    def test_successful_version_check(self, mock_get, version_checker):
        """Test successful version check from PyPI."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"info": {"version": "1.1.0"}}
        mock_response.headers.get.return_value = "etag123"
        mock_get.return_value = mock_response

        version = version_checker.check_latest_version()

        assert version == "1.1.0"

    @patch("requests.get")
    def test_failed_version_check(self, mock_get, version_checker):
        """Test failed version check from PyPI."""
        mock_get.side_effect = requests.RequestException("Network error")

        version = version_checker.check_latest_version()

        assert version is None

    @patch("requests.get")
    def test_not_modified_response(self, mock_get, version_checker):
        """Test handling of 304 Not Modified response."""
        # First, create cached data with correct key names
        import time

        version_checker._save_cache(
            {"version": "1.0.5", "etag": "etag123", "timestamp": time.time()}
        )

        mock_response = Mock()
        mock_response.status_code = 304
        mock_get.return_value = mock_response

        version = version_checker.check_latest_version()

        assert version == "1.0.5"
