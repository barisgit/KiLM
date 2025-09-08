"""
Tests for update command group and subcommands.
"""

from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from kicad_lib_manager.commands.update.check import check_update_command
from kicad_lib_manager.commands.update.command import update_app
from kicad_lib_manager.commands.update.info import info_command
from kicad_lib_manager.commands.update.perform import perform_update_command

# Create test applications for individual commands
check_app = typer.Typer()
check_app.command()(check_update_command)

info_app = typer.Typer()
info_app.command()(info_command)

perform_app = typer.Typer()
perform_app.command()(perform_update_command)


@pytest.fixture
def runner():
    """Create a CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def mock_update_service():
    """Mock UpdateService for testing."""
    with (
        patch(
            "kicad_lib_manager.commands.update.check.UpdateService"
        ) as mock_service_check,
        patch(
            "kicad_lib_manager.commands.update.info.UpdateService"
        ) as mock_service_info,
        patch(
            "kicad_lib_manager.commands.update.perform.UpdateService"
        ) as mock_service_perform,
    ):
        service_instance = MagicMock()
        mock_service_check.return_value = service_instance
        mock_service_info.return_value = service_instance
        mock_service_perform.return_value = service_instance
        yield service_instance


@pytest.fixture
def mock_version():
    """Mock importlib.metadata.version."""
    with (
        patch(
            "kicad_lib_manager.commands.update.check.importlib.metadata.version"
        ) as mock_ver_check,
        patch(
            "kicad_lib_manager.commands.update.info.importlib.metadata.version"
        ) as mock_ver_info,
        patch(
            "kicad_lib_manager.commands.update.perform.importlib.metadata.version"
        ) as mock_ver_perform,
    ):
        mock_ver_check.return_value = "1.0.0"
        mock_ver_info.return_value = "1.0.0"
        mock_ver_perform.return_value = "1.0.0"
        yield mock_ver_check


class TestUpdateCheckCommand:
    """Test the 'kilm update check' command."""

    def test_check_update_available(self, runner, mock_update_service, mock_version):
        """Test check command when update is available."""
        mock_update_service.check_for_updates.return_value = {
            "has_update": True,
            "current_version": "1.0.0",
            "latest_version": "1.1.0",
            "method": "pip",
            "supports_auto_update": True,
        }
        mock_update_service.get_update_instructions.return_value = (
            "pip install --upgrade kilm"
        )

        result = runner.invoke(check_app)

        assert result.exit_code == 1  # Exit code 1 indicates update available
        assert "Update available!" in result.stdout
        assert "Current version: 1.0.0" in result.stdout
        assert "Latest version: 1.1.0" in result.stdout

    def test_check_no_update_available(self, runner, mock_update_service, mock_version):
        """Test check command when no update is available."""
        mock_update_service.check_for_updates.return_value = {
            "has_update": False,
            "current_version": "1.0.0",
            "latest_version": "1.0.0",
            "method": "pip",
            "supports_auto_update": True,
        }

        result = runner.invoke(check_app)

        assert result.exit_code == 0  # Exit code 0 indicates no update needed
        assert "You are using the latest version" in result.stdout

    def test_check_quiet_mode_with_update(
        self, runner, mock_update_service, mock_version
    ):
        """Test check command in quiet mode when update is available."""
        mock_update_service.check_for_updates.return_value = {
            "has_update": True,
            "current_version": "1.0.0",
            "latest_version": "1.1.0",
            "method": "pip",
            "supports_auto_update": True,
        }

        result = runner.invoke(check_app, ["--quiet"])

        assert result.exit_code == 1
        assert "Update available!" in result.stdout

    def test_check_quiet_mode_no_update(
        self, runner, mock_update_service, mock_version
    ):
        """Test check command in quiet mode when no update is available."""
        mock_update_service.check_for_updates.return_value = {
            "has_update": False,
            "current_version": "1.0.0",
            "latest_version": "1.0.0",
            "method": "pip",
            "supports_auto_update": True,
        }

        result = runner.invoke(check_app, ["--quiet"])

        assert result.exit_code == 0
        # Should have minimal output in quiet mode
        assert result.stdout.strip() == ""

    def test_check_force_flag(self, runner, mock_update_service, mock_version):
        """Test check command with force flag to bypass cache."""
        mock_update_service.check_for_updates.return_value = {
            "has_update": False,
            "current_version": "1.0.0",
            "latest_version": "1.0.0",
            "method": "pip",
            "supports_auto_update": True,
        }

        result = runner.invoke(check_app, ["--force"])

        assert result.exit_code == 0
        # Verify cache was bypassed (use_cache=False)
        mock_update_service.check_for_updates.assert_called_with(use_cache=False)

    def test_check_manual_update_required(
        self, runner, mock_update_service, mock_version
    ):
        """Test check command when manual update is required."""
        mock_update_service.check_for_updates.return_value = {
            "has_update": True,
            "current_version": "1.0.0",
            "latest_version": "1.1.0",
            "method": "homebrew",
            "supports_auto_update": False,
        }
        mock_update_service.get_update_instructions.return_value = "brew upgrade kilm"

        result = runner.invoke(check_app)

        assert result.exit_code == 1
        assert "Manual update required" in result.stdout
        assert "brew upgrade kilm" in result.stdout


class TestUpdateInfoCommand:
    """Test the 'kilm update info' command."""

    def test_info_display(self, runner, mock_update_service, mock_version):
        """Test info command display."""
        mock_update_service.check_for_updates.return_value = {
            "has_update": False,
            "current_version": "1.0.0",
            "latest_version": "1.0.0",
            "method": "pip",
            "supports_auto_update": True,
        }
        mock_update_service.get_installation_method.return_value = "pip"
        mock_update_service.can_auto_update.return_value = True
        mock_update_service.get_update_instructions.return_value = (
            "pip install --upgrade kilm"
        )

        result = runner.invoke(info_app)

        assert result.exit_code == 0
        assert "Version Information" in result.stdout
        assert "Installation Details" in result.stdout
        assert "Available Commands" in result.stdout

    def test_info_with_update_available(
        self, runner, mock_update_service, mock_version
    ):
        """Test info command when update is available."""
        mock_update_service.check_for_updates.return_value = {
            "has_update": True,
            "current_version": "1.0.0",
            "latest_version": "1.1.0",
            "method": "pip",
            "supports_auto_update": True,
        }
        mock_update_service.get_installation_method.return_value = "pip"
        mock_update_service.can_auto_update.return_value = True
        mock_update_service.get_update_instructions.return_value = (
            "pip install --upgrade kilm"
        )

        result = runner.invoke(info_app)

        assert result.exit_code == 0
        assert "1.1.0 available" in result.stdout

    def test_info_force_check(self, runner, mock_update_service, mock_version):
        """Test info command with force check flag."""
        mock_update_service.check_for_updates.return_value = {
            "has_update": False,
            "current_version": "1.0.0",
            "latest_version": "1.0.0",
            "method": "pip",
            "supports_auto_update": True,
        }
        mock_update_service.get_installation_method.return_value = "pip"
        mock_update_service.can_auto_update.return_value = True
        mock_update_service.get_update_instructions.return_value = (
            "pip install --upgrade kilm"
        )

        result = runner.invoke(info_app, ["--force-check"])

        assert result.exit_code == 0
        # Verify cache was bypassed
        mock_update_service.check_for_updates.assert_called_with(use_cache=False)


class TestUpdatePerformCommand:
    """Test the 'kilm update perform' command."""

    def test_perform_successful_update(self, runner, mock_update_service, mock_version):
        """Test successful update performance."""
        mock_update_service.can_auto_update.return_value = True
        mock_update_service.check_for_updates.return_value = {
            "has_update": True,
            "current_version": "1.0.0",
            "latest_version": "1.1.0",
        }
        mock_update_service.perform_update.return_value = (
            True,
            "Update completed successfully!",
        )

        result = runner.invoke(perform_app)

        assert result.exit_code == 0
        assert "Update completed successfully!" in result.stdout

    def test_perform_update_failed(self, runner, mock_update_service, mock_version):
        """Test failed update performance."""
        mock_update_service.can_auto_update.return_value = True
        mock_update_service.check_for_updates.return_value = {
            "has_update": True,
            "current_version": "1.0.0",
            "latest_version": "1.1.0",
        }
        mock_update_service.perform_update.return_value = (False, "Update failed")

        result = runner.invoke(perform_app)

        assert result.exit_code == 1
        assert "Update failed" in result.stdout

    def test_perform_no_auto_update_support(
        self, runner, mock_update_service, mock_version
    ):
        """Test perform command when auto-update is not supported."""
        mock_update_service.can_auto_update.return_value = False
        mock_update_service.get_installation_method.return_value = "homebrew"
        mock_update_service.get_update_instructions.return_value = "brew upgrade kilm"

        result = runner.invoke(perform_app)

        assert result.exit_code == 1
        assert "Automatic update not supported" in result.stdout
        assert "brew upgrade kilm" in result.stdout

    def test_perform_no_update_needed(self, runner, mock_update_service, mock_version):
        """Test perform command when no update is needed."""
        mock_update_service.can_auto_update.return_value = True
        mock_update_service.check_for_updates.return_value = {
            "has_update": False,
            "current_version": "1.0.0",
            "latest_version": "1.0.0",
        }

        result = runner.invoke(perform_app)

        assert result.exit_code == 0
        assert "Already using the latest version" in result.stdout

    def test_perform_force_update(self, runner, mock_update_service, mock_version):
        """Test perform command with force flag."""
        mock_update_service.can_auto_update.return_value = True
        mock_update_service.perform_update.return_value = (
            True,
            "Update completed successfully!",
        )

        result = runner.invoke(perform_app, ["--force"])

        assert result.exit_code == 0
        # Should skip the update check when forced
        mock_update_service.perform_update.assert_called_with(
            target_version=None, force=True, dry_run=False
        )

    def test_perform_dry_run(self, runner, mock_update_service, mock_version):
        """Test perform command in dry run mode."""
        mock_update_service.perform_update.return_value = (True, "Dry run message")

        result = runner.invoke(perform_app, ["--dry-run"])

        assert result.exit_code == 0
        assert "Dry run completed" in result.stdout
        mock_update_service.perform_update.assert_called_with(
            target_version=None, force=False, dry_run=True
        )

    def test_perform_target_version(self, runner, mock_update_service, mock_version):
        """Test perform command with specific target version."""
        mock_update_service.can_auto_update.return_value = True
        mock_update_service.check_for_updates.return_value = {
            "has_update": True,
            "current_version": "1.0.0",
            "latest_version": "1.1.0",
        }
        mock_update_service.perform_update.return_value = (
            True,
            "Update completed successfully!",
        )

        result = runner.invoke(perform_app, ["--target-version", "1.0.5"])

        assert result.exit_code == 0
        mock_update_service.perform_update.assert_called_with(
            target_version="1.0.5", force=False, dry_run=False
        )

    def test_perform_no_cache(self, runner, mock_update_service, mock_version):
        """Test perform command with no-cache flag."""
        mock_update_service.can_auto_update.return_value = True
        mock_update_service.check_for_updates.return_value = {
            "has_update": False,
            "current_version": "1.0.0",
            "latest_version": "1.0.0",
        }

        result = runner.invoke(perform_app, ["--no-cache"])

        assert result.exit_code == 0
        # Should bypass cache
        mock_update_service.check_for_updates.assert_called_with(use_cache=False)

    def test_deprecation_notice_displayed(
        self, runner, mock_update_service, mock_version
    ):
        """Test that deprecation notice is displayed."""
        mock_update_service.can_auto_update.return_value = True
        mock_update_service.check_for_updates.return_value = {
            "has_update": False,
            "current_version": "1.0.0",
            "latest_version": "1.0.0",
        }

        result = runner.invoke(perform_app)

        assert "BREAKING CHANGE NOTICE" in result.stdout
        assert "kilm sync" in result.stdout


class TestUpdateCommandGroup:
    """Test the update command group integration."""

    def test_update_app_help(self, runner):
        """Test that the update command group shows help correctly."""
        result = runner.invoke(update_app, ["--help"])

        assert result.exit_code == 0
        assert "Update KiLM CLI to the latest version" in result.stdout
        assert "check" in result.stdout
        assert "info" in result.stdout
        assert "perform" in result.stdout

    def test_update_app_no_args_shows_help(self, runner):
        """Test that running update with no args shows help."""
        result = runner.invoke(update_app, [])

        assert result.exit_code == 2  # CLI standard: missing args = error code
        assert "Usage:" in result.stdout
        assert "Commands" in result.stdout  # Rich formatting uses "╭─ Commands ───"

    def test_subcommand_help_messages(self, runner):
        """Test that each subcommand has proper help."""
        subcommands = ["check", "info", "perform"]

        for subcommand in subcommands:
            result = runner.invoke(update_app, [subcommand, "--help"])
            assert result.exit_code == 0
            assert "Usage:" in result.stdout


class TestIntegrationScenarios:
    """Test realistic integration scenarios."""

    def test_uv_tool_update_workflow(self, runner):
        """Test complete workflow for UV tool installation."""
        with (
            patch(
                "kicad_lib_manager.commands.update.check.UpdateService"
            ) as mock_service_class,
            patch("importlib.metadata.version") as mock_version,
        ):
            mock_version.return_value = "1.0.0"
            mock_service = MagicMock()
            mock_service_class.return_value = mock_service

            # Mock UV tool installation
            mock_service.check_for_updates.return_value = {
                "has_update": True,
                "current_version": "1.0.0",
                "latest_version": "1.1.0",
                "method": "uv",
                "supports_auto_update": True,
            }
            mock_service.get_update_instructions.return_value = "uv tool upgrade kilm"

            # Test check command
            result = runner.invoke(check_app)
            assert result.exit_code == 1
            assert "Update available!" in result.stdout
            assert "kilm update perform" in result.stdout

    def test_pipx_installation_workflow(self, runner):
        """Test complete workflow for pipx installation."""
        with (
            patch(
                "kicad_lib_manager.commands.update.info.UpdateService"
            ) as mock_service_class,
            patch("importlib.metadata.version") as mock_version,
        ):
            mock_version.return_value = "1.0.0"
            mock_service = MagicMock()
            mock_service_class.return_value = mock_service

            # Mock pipx installation
            mock_service.check_for_updates.return_value = {
                "has_update": False,
                "current_version": "1.0.0",
                "latest_version": "1.0.0",
                "method": "pipx",
                "supports_auto_update": True,
            }
            mock_service.get_installation_method.return_value = "pipx"
            mock_service.can_auto_update.return_value = True
            mock_service.get_update_instructions.return_value = "pipx upgrade kilm"

            # Test info command
            result = runner.invoke(info_app)
            assert result.exit_code == 0
            assert "pipx" in result.stdout
            assert "pipx upgrade kilm" in result.stdout

    def test_homebrew_manual_update_workflow(self, runner):
        """Test workflow for homebrew installation requiring manual update."""
        with (
            patch(
                "kicad_lib_manager.commands.update.perform.UpdateService"
            ) as mock_service_class,
            patch("importlib.metadata.version") as mock_version,
        ):
            mock_version.return_value = "1.0.0"
            mock_service = MagicMock()
            mock_service_class.return_value = mock_service

            # Mock homebrew installation (no auto-update support)
            mock_service.can_auto_update.return_value = False
            mock_service.get_installation_method.return_value = "homebrew"
            mock_service.get_update_instructions.return_value = (
                "Homebrew package not yet available (planned for future)"
            )

            # Test perform command
            result = runner.invoke(perform_app)
            assert result.exit_code == 1
            assert "Automatic update not supported" in result.stdout
            assert "homebrew" in result.stdout
