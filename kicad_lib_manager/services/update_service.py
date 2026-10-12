"""Auto-update functionality for KiLM.
Handles installation method detection, PyPI integration, and update execution.
"""

# PEP 810: on Python 3.15+ these imports load on first use.
__lazy_modules__ = {"packaging.version", "requests"}

import importlib.metadata
import json
import os
import subprocess
import sys
import time
from pathlib import Path, PurePath
from typing import Any, Literal

import requests
from packaging.version import InvalidVersion, Version


InstallMethod = Literal[
    "pipx", "conda", "uv", "nix", "pip-venv", "homebrew", "pip", "unknown"
]
"""How KiLM was installed; decides how it can be updated."""


def read_installer() -> str | None:
    """Return the installer recorded for kilm (INSTALLER file), if any."""
    try:
        installer = importlib.metadata.distribution("kilm").read_text("INSTALLER")
    except importlib.metadata.PackageNotFoundError:
        return None
    return installer.strip() if installer else None


class InstallationDetector:
    """Platform-aware installation method detector."""

    def __init__(
        self,
        executable_path: PurePath | None = None,
        platform_name: str | None = None,
        *,
        installer: str | None = "",
    ):
        self.executable_path = executable_path or Path(sys.executable)
        self.platform_name = platform_name or os.name
        # "" means "read it from the installed distribution".
        self.installer = read_installer() if installer == "" else installer
        # Forward slashes on every platform so the path patterns below
        # (".local/share/pipx", "uv/tools", ...) also match Windows paths.
        self.executable_str = self.executable_path.as_posix()

    def is_windows(self) -> bool:
        """Check if running on Windows."""
        return self.platform_name == "nt"

    def is_unix_like(self) -> bool:
        """Check if running on Unix-like system."""
        return not self.is_windows()

    def detect_pipx(self) -> bool:
        """Detect pipx installation."""
        # Check for pipx path patterns
        pipx_patterns = [".local/share/pipx", "pipx/venvs"]
        if any(part in self.executable_str for part in pipx_patterns):
            return True

        # Check for pipx environment variable
        pipx_home = os.environ.get("PIPX_HOME")
        return bool(pipx_home and "pipx" in self.executable_str)

    def detect_conda(self) -> bool:
        """Detect a conda install: the interpreter lives in a conda environment.

        An activated environment (``CONDA_DEFAULT_ENV``) is no evidence on its
        own, since many shells activate conda's base environment by default.
        """
        if "conda" in self.executable_str:
            return True
        prefix = os.environ.get("CONDA_PREFIX")
        return bool(prefix) and self.executable_path.is_relative_to(
            type(self.executable_path)(prefix)
        )

    def detect_uv(self) -> bool:
        """Detect a uv tool install: the interpreter lives in a uv tools directory.

        uv keeps tool environments in ``uv/tools`` under its data directory
        (``uv/data/tools`` on Windows) unless ``UV_TOOL_DIR`` moves them. The
        variable alone is no evidence: it is also set where uv manages other
        tools, so only an interpreter inside that directory counts.
        """
        if any(
            part in self.executable_str for part in ("/uv/tools/", "/uv/data/tools/")
        ):
            return True
        tool_dir = os.environ.get("UV_TOOL_DIR")
        return bool(tool_dir) and self.executable_path.is_relative_to(
            type(self.executable_path)(tool_dir)
        )

    def detect_virtual_env(self) -> bool:
        """Detect virtual environment (pip in venv)."""
        # Check VIRTUAL_ENV environment variable
        if os.environ.get("VIRTUAL_ENV"):
            return True

        # Check sys.prefix vs base_prefix
        base_prefix = getattr(sys, "base_prefix", sys.prefix)
        return sys.prefix != base_prefix

    def detect_homebrew(self) -> bool:
        """Detect homebrew installation (macOS/Linux)."""
        if self.is_windows():
            return False

        homebrew_paths = ["/opt/homebrew/", "/usr/local/Cellar/"]
        return any(self.executable_str.startswith(path) for path in homebrew_paths)

    def detect_nix(self) -> bool:
        """Detect a Nix install: the interpreter lives in the Nix store."""
        return self.executable_str.startswith("/nix/store/")

    def detect(self) -> InstallMethod:
        """Detect the installation method, most specific evidence first.

        Returns "unknown" rather than guessing when nothing identifies the
        installer, so callers never suggest a command that cannot work.
        """
        # Priority order matters - more specific first
        if self.detect_pipx():
            return "pipx"

        if self.detect_conda():
            return "conda"

        if self.detect_uv():
            return "uv"

        if self.detect_nix():
            return "nix"

        if self.detect_virtual_env():
            return "pip-venv"

        if self.detect_homebrew():
            return "homebrew"

        if self.installer == "pip":
            return "pip"

        return "unknown"


def detect_installation_method() -> InstallMethod:
    """Detect how KiLM was installed to determine appropriate update strategy."""
    detector = InstallationDetector()
    return detector.detect()


class PyPIVersionChecker:
    """Responsible PyPI API client with caching and proper headers."""

    def __init__(self, package_name: str, version: str = "unknown"):
        self.package_name = package_name
        self.base_url = f"https://pypi.org/pypi/{package_name}/json"
        self.cache_file = Path.home() / ".cache" / "kilm" / "version_check.json"
        self.user_agent = f"KiLM/{version} (+https://github.com/barisgit/KiLM)"

    def check_latest_version(self) -> str | None:
        """Check latest version from PyPI with caching and rate limiting.
        Returns None if check fails or is rate limited.
        """
        try:
            headers = {"User-Agent": self.user_agent}

            # Use cached ETag if available
            cached_data = self._load_cache()
            if cached_data is not None and "etag" in cached_data:
                headers["If-None-Match"] = cached_data["etag"]

            response = requests.get(self.base_url, headers=headers, timeout=10)

            if response.status_code == 304:  # Not Modified
                return cached_data.get("version") if cached_data else None

            if response.status_code == 200:
                data = response.json()
                latest_version = data["info"]["version"]

                # Cache response with ETag
                self._save_cache(
                    {
                        "version": latest_version,
                        "etag": response.headers.get("ETag"),
                        "timestamp": time.time(),
                    }
                )

                return latest_version

        except (requests.RequestException, KeyError, json.JSONDecodeError):
            # Fail silently - don't block CLI functionality
            pass

        return None

    def _load_cache(self) -> dict | None:
        """Load cached version data."""
        if self.cache_file.exists():
            try:
                with Path(self.cache_file).open() as f:
                    data = json.load(f)
                    # Cache valid for 24 hours
                    if time.time() - data.get("timestamp", 0) < 86400:
                        return data
            except (json.JSONDecodeError, KeyError):
                pass
        return None

    def _save_cache(self, data: dict):
        """Save version data to cache."""
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        with Path(self.cache_file).open("w") as f:
            json.dump(data, f)


def upgrade_command(
    method: InstallMethod, target_version: str | None = None
) -> list[str] | None:
    """Return the command that updates kilm for an install method, as shown to users.

    Without a target version the command upgrades to the latest release; with
    one it installs exactly that version, which may be a downgrade. Returns
    None for methods where kilm cannot update itself.
    """
    spec = f"kilm=={target_version}" if target_version else "kilm"
    if method == "pipx":
        if target_version:
            return ["pipx", "install", "--force", spec]
        return ["pipx", "upgrade", "kilm"]
    if method == "uv":
        # `uv tool upgrade` keeps an exact pin from an earlier install and
        # then succeeds without changing anything; `uv tool install` replaces
        # the pin.
        return ["uv", "tool", "install", spec if target_version else "kilm@latest"]
    if method in ("pip", "pip-venv"):
        return ["pip", "install", "--upgrade", spec]
    return None


def run_upgrade(command: list[str]) -> bool:
    """Run an upgrade command from `upgrade_command` and report success."""
    # pip runs through this interpreter so it updates the running environment.
    argv = [sys.executable, "-m", *command] if command[0] == "pip" else command
    try:
        result = subprocess.run(
            argv, capture_output=True, text=True, timeout=300, check=False
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    return result.returncode == 0


class UpdateManager:
    """Manages update checking and execution for KiLM."""

    def __init__(self, current_version: str):
        self.version_checker = PyPIVersionChecker("kilm")
        self.current_version = current_version
        self.installation_method: InstallMethod = detect_installation_method()

    def check_latest_version(self) -> str | None:
        """Check for latest version available on PyPI."""
        return self.version_checker.check_latest_version()

    def is_newer_version_available(self, latest_version: str) -> bool:
        """Compare versions to determine if update is available."""
        try:
            current_ver = Version(self.current_version)
            latest_ver = Version(latest_version)
            return latest_ver > current_ver
        except (InvalidVersion, AttributeError):
            return False

    def get_update_instruction(self, target_version: str | None = None) -> str:
        """Get update instruction for the detected installation method."""
        command = upgrade_command(self.installation_method, target_version)
        if command:
            return " ".join(command)
        instructions: dict[InstallMethod, str] = {
            "conda": "Conda package not yet available (planned for future)",
            "homebrew": "Homebrew package not yet available (planned for future)",
            "nix": "nix flake update, then rebuild the configuration or profile"
            " that installs kilm",
            "unknown": "Update KiLM with the tool that installed it",
        }
        return instructions.get(self.installation_method, "")

    def can_auto_update(self) -> bool:
        """Check if automatic update is possible for this installation method."""
        return upgrade_command(self.installation_method) is not None

    def perform_update(self, target_version: str | None = None) -> tuple[bool, str]:
        """Install the latest release, or `target_version` when given.

        Returns: (success, message)
        """
        command = upgrade_command(self.installation_method, target_version)
        if command is None:
            instruction = self.get_update_instruction()
            return False, f"Manual update required: {instruction}"
        if run_upgrade(command):
            return True, "KiLM updated successfully!"
        instruction = self.get_update_instruction(target_version)
        return False, f"Auto-update failed. Try manually: {instruction}"


class UpdateService:
    """Service wrapper for KiLM update functionality."""

    def __init__(self, current_version: str):
        self.manager = UpdateManager(current_version)
        self.current_version = current_version

    def check_for_updates(self, use_cache: bool = True) -> dict[str, Any]:
        """Check for available updates.

        Returns:
            Dict containing update status information:
            - has_update: whether an update is available
            - current_version: current installed version
            - latest_version: latest available version
            - method: installation method identifier
            - supports_auto_update: whether automatic update is supported
        """
        latest_version = (
            self.manager.check_latest_version()
            if use_cache
            else self.manager.version_checker.check_latest_version()
        )
        has_update = False

        if latest_version:
            has_update = self.manager.is_newer_version_available(latest_version)

        return {
            "has_update": has_update,
            "current_version": self.current_version,
            "latest_version": latest_version,
            "method": self.manager.installation_method,
            "supports_auto_update": self.manager.can_auto_update(),
        }

    def show_update_notification(
        self, quiet: bool = False, force_check: bool = False
    ) -> bool:
        """Show update notification if updates are available.

        Args:
            quiet: Only show notification if update is available
            force_check: Skip cache and force fresh check

        Returns:
            bool: True if update is available
        """
        from rich.console import Console
        from rich.panel import Panel

        console = Console()
        update_info = self.check_for_updates(use_cache=not force_check)

        if not update_info["has_update"]:
            if not quiet:
                console.print("[green]✓[/green] You are using the latest version!")
            return False

        # Create update notification
        current = update_info["current_version"]
        latest = update_info["latest_version"]
        method = update_info["method"]
        can_auto_update = update_info["supports_auto_update"]

        message_lines = [
            "[yellow]Update available![/yellow]",
            f"Current: [blue]{current}[/blue] → Latest: [green]{latest}[/green]",
            "",
        ]

        if can_auto_update:
            message_lines.extend(
                [
                    "Run [bold cyan]kilm update[/bold cyan] to update automatically",
                    f"Installation method: [dim]{method}[/dim]",
                ]
            )
        else:
            update_cmd = self.manager.get_update_instruction()
            message_lines.extend(
                [
                    f"Installation method: [bold]{method}[/bold] (manual update required)",
                    f"Update manually: [bold cyan]{update_cmd}[/bold cyan]",
                ]
            )

        message = "\n".join(message_lines)

        console.print(
            Panel(
                message,
                title="[bold blue]KiLM Update Available[/bold blue]",
                border_style="blue",
            )
        )

        return True

    def is_update_available(self, latest_version: str) -> bool:
        """Check if an update is available."""
        return self.manager.is_newer_version_available(latest_version)

    def get_installation_method(self) -> InstallMethod:
        """Get detected installation method."""
        return self.manager.installation_method

    def get_update_instructions(self) -> str:
        """Get update instructions for current installation method."""
        return self.manager.get_update_instruction()

    def can_auto_update(self) -> bool:
        """Check if automatic updates are supported."""
        return self.manager.can_auto_update()

    def perform_update(
        self,
        target_version: str | None = None,
        force: bool = False,
        dry_run: bool = False,
    ) -> tuple[bool, str]:
        """Perform update installation.

        Args:
            target_version: Specific version to install
            force: Force update even if already up to date
            dry_run: Show what would be done without doing it

        Returns:
            tuple[bool, str]: (success, message)
        """
        if dry_run:
            return self._show_dry_run_info(target_version)

        # A target version is installed as asked, even when it is older.
        if not force and target_version is None:
            update_info = self.check_for_updates()
            if not update_info["has_update"]:
                return True, "Already using the latest version!"

        return self.manager.perform_update(target_version)

    def _show_dry_run_info(self, target_version: str | None = None) -> tuple[bool, str]:
        """Show what would happen during an update."""
        from rich.console import Console
        from rich.panel import Panel

        console = Console()
        method = self.manager.installation_method
        can_auto_update = self.manager.can_auto_update()
        package_spec = f"kilm=={target_version}" if target_version else "kilm"
        update_cmd = self.manager.get_update_instruction(target_version)

        console.print(
            Panel(
                f"""[bold]Update Plan (Dry Run)[/bold]

Installation method: [cyan]{method}[/cyan]
Target package: [green]{package_spec}[/green]
Auto-update supported: [{"green" if can_auto_update else "red"}]{can_auto_update}[/]

Command that would be executed:
[bold cyan]{update_cmd}[/bold cyan]""",
                title="[bold yellow]Dry Run[/bold yellow]",
                border_style="yellow",
            )
        )

        return can_auto_update, f"Dry run completed - would execute: {update_cmd}"
