"""Tests for the `kilm update` command group."""

import importlib.metadata
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

import kicad_lib_manager.main as main
from kicad_lib_manager.commands.update import check, info, perform
from kicad_lib_manager.commands.update.command import update_app
from kicad_lib_manager.main import app
from kicad_lib_manager.services import update_service
from kicad_lib_manager.services.config_service import Config
from kicad_lib_manager.services.install_method import InstallMethod
from kicad_lib_manager.services.update_service import UpdateService


@dataclass
class FakeInstallation:
    """An installed kilm 1.0.0 whose installer and PyPI are simulated."""

    method: InstallMethod = "pipx"
    latest: str | None = "1.1.0"
    upgrade_error: str | None = None
    use_cache_calls: list[bool] = field(default_factory=list)
    upgrades: list[list[str]] = field(default_factory=list)

    def service(self, current_version: str) -> UpdateService:
        """Build the service the commands use, seeing this installation."""
        return UpdateService(current_version, method=self.method, version_checker=self)

    def check_latest_version(self, *, use_cache: bool = True) -> str | None:
        """Answer version checks with `latest`, recording the cache choice."""
        self.use_cache_calls.append(use_cache)
        return self.latest

    def run_upgrade(self, command: list[str]) -> str | None:
        """Record an installer run; it fails with `upgrade_error` if set."""
        self.upgrades.append(command)
        return self.upgrade_error


@pytest.fixture
def installation(monkeypatch: pytest.MonkeyPatch) -> FakeInstallation:
    """Route the update commands to a simulated installation."""
    fake = FakeInstallation()
    monkeypatch.setattr(importlib.metadata, "version", lambda _name: "1.0.0")
    for module in (check, info, perform):
        monkeypatch.setattr(module, "UpdateService", fake.service)
    monkeypatch.setattr(update_service, "run_upgrade", fake.run_upgrade)
    return fake


def kilm_update(*args: str) -> Result:
    """Run `kilm update ARGS`."""
    return CliRunner().invoke(update_app, list(args))


class TestCheck:
    """`kilm update check`."""

    def test_update_available(self, installation: FakeInstallation) -> None:
        """A newer release is reported with exit status 1."""
        result = kilm_update("check")
        assert result.exit_code == 1
        assert "Update available!" in result.stdout
        assert "Current version: 1.0.0" in result.stdout
        assert "Latest version: 1.1.0" in result.stdout
        assert "Installation method: pipx" in result.stdout
        assert "kilm update perform" in result.stdout
        assert installation.use_cache_calls == [True]

    def test_up_to_date(self, installation: FakeInstallation) -> None:
        """Up to date exits 0, silently with --quiet."""
        installation.latest = "1.0.0"
        result = kilm_update("check")
        assert result.exit_code == 0
        assert "You are using the latest version (v1.0.0)" in result.stdout

        quiet = kilm_update("check", "--quiet")
        assert quiet.exit_code == 0
        assert not quiet.stdout.strip()

    def test_quiet_still_reports_an_update(
        self, installation: FakeInstallation
    ) -> None:
        """--quiet only silences the up-to-date message."""
        result = kilm_update("check", "-q")
        assert result.exit_code == 1
        assert "Update available!" in result.stdout
        assert installation.upgrades == []

    def test_force_bypasses_the_cache(self, installation: FakeInstallation) -> None:
        """--force asks PyPI even when a recent answer is cached."""
        kilm_update("check", "--force")
        assert installation.use_cache_calls == [False]

    def test_manual_update_required(self, installation: FakeInstallation) -> None:
        """Installs KiLM cannot update get the manual instruction."""
        installation.method = "nix"
        result = kilm_update("check")
        assert result.exit_code == 1
        assert "Manual update required: nix flake update" in result.stdout

    def test_unknown_latest_version_is_not_up_to_date(
        self, installation: FakeInstallation
    ) -> None:
        """A failed PyPI check is not reported as being up to date."""
        installation.latest = None
        result = kilm_update("check")
        assert result.exit_code == 1
        assert "Could not determine the latest version" in result.stdout


class TestInfo:
    """`kilm update info`."""

    def test_up_to_date(self, installation: FakeInstallation) -> None:
        """The panel shows version, installation details, and the commands."""
        installation.latest = "1.0.0"
        result = kilm_update("info")
        assert result.exit_code == 0
        assert "Current version: 1.0.0 (latest)" in result.stdout
        assert "Method: pipx" in result.stdout
        assert "Update command: pipx upgrade kilm" in result.stdout
        assert "Available Commands" in result.stdout

    def test_update_available(self, installation: FakeInstallation) -> None:
        """A newer release is shown next to the current version."""
        result = kilm_update("info", "--force-check")
        assert result.exit_code == 0
        assert "1.1.0 available" in result.stdout
        assert installation.use_cache_calls == [False]


class TestPerform:
    """`kilm update perform`."""

    def test_installs_the_latest_release(self, installation: FakeInstallation) -> None:
        """An available update is installed with the method's installer."""
        result = kilm_update("perform")
        assert result.exit_code == 0
        assert "BREAKING CHANGE NOTICE" in result.stdout
        assert "kilm sync" in result.stdout
        assert "Updating from 1.0.0 to 1.1.0" in result.stdout
        assert "Update completed successfully!" in result.stdout
        assert installation.upgrades == [["pipx", "upgrade", "kilm"]]

    def test_installer_failure(self, installation: FakeInstallation) -> None:
        """A failed installer exits 1 with its error and the manual command."""
        installation.upgrade_error = "pipx: network unreachable"
        result = kilm_update("perform")
        assert result.exit_code == 1
        assert "Update failed: pipx: network unreachable" in result.stdout
        assert "Try manually: pipx upgrade kilm" in result.stdout

    @pytest.mark.parametrize("dry_run", [False, True])
    def test_unsupported_method(
        self, installation: FakeInstallation, *, dry_run: bool
    ) -> None:
        """Methods without an installer exit 1, in a dry run too."""
        installation.method = "homebrew"
        result = kilm_update("perform", *(["--dry-run"] if dry_run else []))
        assert result.exit_code == 1
        assert "Automatic update not supported" in result.stdout
        assert "Installation method: homebrew" in result.stdout
        assert installation.upgrades == []

    def test_up_to_date(self, installation: FakeInstallation) -> None:
        """Nothing is installed when the latest release is installed."""
        installation.latest = "1.0.0"
        result = kilm_update("perform")
        assert result.exit_code == 0
        assert "Already using the latest version (v1.0.0)" in result.stdout
        assert installation.upgrades == []

    def test_force_reinstalls(self, installation: FakeInstallation) -> None:
        """--force installs without asking PyPI whether an update exists."""
        installation.latest = "1.0.0"
        result = kilm_update("perform", "--force")
        assert result.exit_code == 0
        assert installation.use_cache_calls == []
        assert installation.upgrades == [["pipx", "upgrade", "kilm"]]

    def test_dry_run(self, installation: FakeInstallation) -> None:
        """A dry run shows the installer command and installs nothing."""
        result = kilm_update("perform", "--dry-run", "-t", "1.0.5")
        assert result.exit_code == 0
        assert "pipx install --force kilm==1.0.5" in result.stdout
        assert "Dry run completed" in result.stdout
        assert installation.upgrades == []

    def test_target_version_downgrade(self, installation: FakeInstallation) -> None:
        """A target version is installed even when it is older."""
        installation.latest = "1.0.0"
        result = kilm_update("perform", "--target-version", "0.9.0")
        assert result.exit_code == 0
        assert "Updating from 1.0.0 to 0.9.0" in result.stdout
        assert installation.upgrades == [["pipx", "install", "--force", "kilm==0.9.0"]]

    def test_target_version_already_installed(
        self, installation: FakeInstallation
    ) -> None:
        """Asking for the installed version changes nothing without --force."""
        result = kilm_update("perform", "-t", "1.0")
        assert result.exit_code == 0
        assert "Already using version 1.0.0" in result.stdout
        assert installation.upgrades == []

    def test_invalid_target_version(self, installation: FakeInstallation) -> None:
        """A target that is no version number is a usage error."""
        result = kilm_update("perform", "-t", "latest-please")
        assert result.exit_code == 2
        assert installation.upgrades == []

    def test_no_cache(self, installation: FakeInstallation) -> None:
        """--no-cache asks PyPI even when a recent answer is cached."""
        kilm_update("perform", "--no-cache")
        assert installation.use_cache_calls == [False]


class TestStartupUpdateCheck:
    """The update check the root group runs before its subcommands."""

    @pytest.fixture
    def startup(self, monkeypatch: pytest.MonkeyPatch) -> FakeInstallation:
        """Route the root group's update check to a simulated installation."""
        fake = FakeInstallation()
        monkeypatch.setattr(importlib.metadata, "version", lambda _name: "1.0.0")
        monkeypatch.setattr(main, "UpdateService", fake.service)
        return fake

    def test_up_to_date_check_is_recorded(
        self, startup: FakeInstallation, home: Path
    ) -> None:
        """A due check is recorded whether or not it found an update."""
        startup.latest = "1.0.0"
        result = CliRunner().invoke(app, ["config", "list"])

        assert result.exit_code == 0
        assert not Config().should_check_updates()

    def test_help_does_not_check_for_updates(
        self, startup: FakeInstallation
    ) -> None:
        """`kilm --help` answers without the network."""
        startup.latest = "1.1.0"
        result = CliRunner().invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "Update available" not in result.output
        assert startup.use_cache_calls == []


class TestGroup:
    """The `kilm update` group itself."""

    @pytest.mark.parametrize("args", [[], ["--help"]])
    def test_help_lists_the_subcommands(self, args: list[str]) -> None:
        """Without a subcommand, or with --help, the group shows its help."""
        result = kilm_update(*args)
        assert "Update KiLM CLI to the latest version" in result.stdout
        for name in ("check", "info", "perform"):
            assert name in result.stdout

    @pytest.mark.parametrize("name", ["check", "info", "perform"])
    def test_subcommand_help(self, name: str) -> None:
        """Every subcommand documents its usage."""
        result = kilm_update(name, "--help")
        assert result.exit_code == 0
        assert "Usage:" in result.stdout
