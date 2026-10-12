"""Tests for checking for and installing KiLM releases."""

import pytest

from kicad_lib_manager.services import update_service
from kicad_lib_manager.services.install_method import InstallMethod
from kicad_lib_manager.services.pypi_version import PyPIVersionChecker
from kicad_lib_manager.services.update_service import UpdateService


class StaticVersionSource:
    """A latest-release source that answers without the network."""

    def __init__(self, latest: str | None) -> None:
        """Answer every check with `latest`."""
        self.latest = latest
        self.use_cache_calls: list[bool] = []

    def check_latest_version(self, *, use_cache: bool = True) -> str | None:
        """Record the cache choice and return the configured version."""
        self.use_cache_calls.append(use_cache)
        return self.latest


def make_service(
    method: InstallMethod = "pipx", latest: str | None = "1.1.0"
) -> UpdateService:
    """An UpdateService for an installed 1.0.0 that sees `latest` on PyPI."""
    return UpdateService(
        "1.0.0", method=method, version_checker=StaticVersionSource(latest)
    )


@pytest.fixture
def upgrades(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """Record installer commands instead of running them; they succeed."""
    commands: list[list[str]] = []

    def fake_run_upgrade(command: list[str]) -> str | None:
        commands.append(command)
        return None

    monkeypatch.setattr(update_service, "run_upgrade", fake_run_upgrade)
    return commands


class TestCheckForUpdates:
    """Comparing the installed version with the latest release."""

    @pytest.mark.parametrize(
        ("latest", "has_update"),
        [("1.1.0", True), ("1.0.0", False), ("0.9.0", False), (None, False)],
    )
    def test_newer_release(self, latest: str | None, *, has_update: bool) -> None:
        """Only a newer release is an update; an unknown one is not."""
        status = make_service(latest=latest).check_for_updates()
        assert status == {
            "has_update": has_update,
            "current_version": "1.0.0",
            "latest_version": latest,
            "method": "pipx",
            "supports_auto_update": True,
        }

    def test_invalid_versions_are_no_update(self) -> None:
        """A version string packaging cannot parse never reports an update."""
        assert not make_service(latest="not-a-version").check_for_updates()[
            "has_update"
        ]

    def test_cache_choice_reaches_the_version_source(self) -> None:
        """use_cache is passed through, so --force really asks PyPI."""
        source = StaticVersionSource("1.1.0")
        service = UpdateService("1.0.0", method="pip", version_checker=source)
        service.check_for_updates()
        service.check_for_updates(use_cache=False)
        assert source.use_cache_calls == [True, False]

    def test_default_checker_identifies_the_installed_version(self) -> None:
        """PyPI requests carry the running kilm version in the User-Agent."""
        checker = UpdateService("1.0.0", method="pip").version_checker
        assert isinstance(checker, PyPIVersionChecker)
        assert checker.user_agent.startswith("KiLM/1.0.0 ")


class TestPerformUpdate:
    """Running the installer."""

    def test_installs_the_latest_release(self, upgrades: list[list[str]]) -> None:
        """Without a target the installer upgrades to the latest release."""
        result = make_service("pipx").perform_update()
        assert result.success
        assert upgrades == [["pipx", "upgrade", "kilm"]]

    def test_installs_the_target_version(self, upgrades: list[list[str]]) -> None:
        """A target version is installed exactly, even when it is older."""
        result = make_service("uv").perform_update("0.9.0")
        assert result.success
        assert upgrades == [["uv", "tool", "install", "kilm==0.9.0"]]

    def test_failure_explains_and_suggests_the_manual_command(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The installer's error and the command to retry by hand are reported."""
        monkeypatch.setattr(
            update_service,
            "run_upgrade",
            lambda _command: "No matching distribution found for kilm==9.9.9",
        )
        result = make_service("pipx").perform_update("9.9.9")
        assert not result.success
        assert result.message == (
            "No matching distribution found for kilm==9.9.9\n"
            "Try manually: pipx install --force kilm==9.9.9"
        )

    def test_manual_methods_install_nothing(self, upgrades: list[list[str]]) -> None:
        """Methods without an installer command only get advice."""
        result = make_service("homebrew").perform_update()
        assert not result.success
        assert "Manual update required" in result.message
        assert upgrades == []


class TestShowUpdateNotification:
    """The update notice printed by the root command."""

    def test_up_to_date(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Up to date prints a confirmation, or nothing when quiet."""
        service = make_service(latest="1.0.0")
        assert not service.show_update_notification(quiet=True)
        assert not capsys.readouterr().out
        assert not service.show_update_notification()
        assert "You are using the latest version" in capsys.readouterr().out

    def test_update_available(self, capsys: pytest.CaptureFixture[str]) -> None:
        """A newer release is announced with how to get it."""
        assert make_service("pipx").show_update_notification(quiet=True)
        output = capsys.readouterr().out
        assert "1.0.0 → Latest: 1.1.0" in output
        assert "Run kilm update perform to update" in output

    def test_manual_update_instruction(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Installs KiLM cannot update show the manual instruction."""
        assert make_service("nix").show_update_notification(quiet=True)
        assert "Update manually: nix flake update" in capsys.readouterr().out
