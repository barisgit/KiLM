"""Checking for and installing new KiLM releases."""

# PEP 810: on Python 3.15+ these imports load on first use.
__lazy_modules__ = {"packaging.version"}

from typing import NamedTuple, Protocol, TypedDict

from packaging.version import InvalidVersion, Version
from rich.panel import Panel

from kicad_lib_manager.services.install_method import (
    InstallMethod,
    detect_installation_method,
    run_upgrade,
    update_instruction,
    upgrade_command,
)
from kicad_lib_manager.services.pypi_version import PyPIVersionChecker
from kicad_lib_manager.utils.console import get_console


class LatestVersionSource(Protocol):
    """Where the latest release is looked up; `PyPIVersionChecker` in production."""

    def check_latest_version(self, *, use_cache: bool = True) -> str | None:
        """Return the latest released version, or None when it is unknown."""
        ...


class UpdateStatus(TypedDict):
    """Result of an update check."""

    has_update: bool
    """Whether a release newer than the installed version exists."""
    current_version: str
    latest_version: str | None
    """None when no fresh cached answer was used and the PyPI lookup failed."""
    method: InstallMethod
    supports_auto_update: bool


class UpdateResult(NamedTuple):
    """Outcome of an installation attempt."""

    success: bool
    message: str
    """On failure, why it failed and how to update by hand."""


def is_newer_version(latest_version: str, current_version: str) -> bool:
    """Return whether `latest_version` is newer; False if either is no version."""
    try:
        return Version(latest_version) > Version(current_version)
    except InvalidVersion:
        return False


class UpdateService:
    """Checks PyPI for new KiLM releases and installs them.

    The installation method is detected once, at construction, and decides
    which installer command an update runs.
    """

    def __init__(
        self,
        current_version: str,
        *,
        method: InstallMethod | None = None,
        version_checker: LatestVersionSource | None = None,
    ) -> None:
        """Prepare update operations for the running installation.

        Args:
            current_version: The installed KiLM version.
            method: The installation method; detected when omitted.
            version_checker: The PyPI client; a cached kilm checker if omitted.
        """
        self.current_version = current_version
        self.method: InstallMethod = method or detect_installation_method()
        self.version_checker: LatestVersionSource = (
            version_checker or PyPIVersionChecker("kilm", current_version)
        )

    @property
    def can_auto_update(self) -> bool:
        """Whether KiLM can run the installer for this installation method."""
        return upgrade_command(self.method) is not None

    def update_instruction(self, target_version: str | None = None) -> str:
        """Return the command, or advice, for updating this installation by hand."""
        return update_instruction(self.method, target_version)

    def check_for_updates(self, *, use_cache: bool = True) -> UpdateStatus:
        """Compare the installed version with the latest release on PyPI.

        With `use_cache` a version check from the last day is reused. Never
        raises for network problems; `latest_version` is then None.
        """
        latest_version = self.version_checker.check_latest_version(use_cache=use_cache)
        return {
            "has_update": latest_version is not None
            and is_newer_version(latest_version, self.current_version),
            "current_version": self.current_version,
            "latest_version": latest_version,
            "method": self.method,
            "supports_auto_update": self.can_auto_update,
        }

    def show_update_notification(
        self, *, quiet: bool = False, force_check: bool = False, stderr: bool = False
    ) -> bool:
        """Print a panel when a newer release exists; return whether one does.

        Args:
            quiet: Print nothing when KiLM is up to date.
            force_check: Ask PyPI even when a recent answer is cached.
            stderr: Write the notice to stderr, for commands whose stdout
                output must stay pure, such as ``--json`` modes.
        """
        console = get_console(stderr=stderr)
        status = self.check_for_updates(use_cache=not force_check)
        if not status["has_update"]:
            if not quiet:
                console.print("[green]You are using the latest version.[/green]")
            return False

        current = status["current_version"]
        latest = status["latest_version"]
        lines = [
            "[yellow]Update available![/yellow]",
            f"Current: [blue]{current}[/blue] → Latest: [green]{latest}[/green]",
            "",
        ]
        if status["supports_auto_update"]:
            lines += [
                (
                    "Run [bold cyan]kilm update perform[/bold cyan] "
                    "to update automatically"
                ),
                f"Installation method: [dim]{self.method}[/dim]",
            ]
        else:
            instruction = self.update_instruction()
            method = f"[bold]{self.method}[/bold]"
            lines += [
                f"Installation method: {method} (manual update required)",
                f"Update manually: [bold cyan]{instruction}[/bold cyan]",
            ]
        console.print(
            Panel(
                "\n".join(lines),
                title="[bold blue]KiLM Update Available[/bold blue]",
                border_style="blue",
            )
        )
        return True

    def perform_update(self, target_version: str | None = None) -> UpdateResult:
        """Run the installer for the latest release, or exactly `target_version`.

        Installs unconditionally: deciding whether an update is needed is the
        caller's job. A target version may be older than the installed one.
        """
        command = upgrade_command(self.method, target_version)
        if command is None:
            return UpdateResult(
                success=False,
                message=f"Manual update required: {self.update_instruction()}",
            )
        error = run_upgrade(command)
        if error is None:
            return UpdateResult(success=True, message="KiLM updated successfully!")
        instruction = self.update_instruction(target_version)
        return UpdateResult(
            success=False, message=f"{error}\nTry manually: {instruction}"
        )
