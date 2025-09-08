"""
Auto-update functionality for KiLM.
Handles installation method detection, PyPI integration, and update execution.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional

import requests
from packaging.version import InvalidVersion, Version


class InstallationDetector:
    """Platform-aware installation method detector."""

    def __init__(
        self,
        executable_path: Optional[Path] = None,
        platform_name: Optional[str] = None,
    ):
        self.executable_path = executable_path or Path(sys.executable)
        self.platform_name = platform_name or os.name
        self.executable_str = str(self.executable_path)

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
        """Detect conda installation."""
        return bool(
            os.environ.get("CONDA_DEFAULT_ENV") or "conda" in self.executable_str
        )

    def detect_uv(self) -> bool:
        """Detect UV tool installation."""
        # Check for explicit UV path patterns in the executable path - most reliable
        uv_path_patterns = any(
            part in self.executable_str for part in [".local/share/uv", "uv/tools"]
        )

        # More specific check: only if executable is actually within uv tools directory
        uv_tools_executable = False
        if self.is_unix_like():
            uv_tools_path = Path.home() / ".local" / "share" / "uv" / "tools"
            # Only consider it uv if the executable is actually within the uv tools directory
            try:
                self.executable_path.relative_to(uv_tools_path)
                uv_tools_executable = True
            except ValueError:
                # executable_path is not within uv_tools_path
                uv_tools_executable = False

        # Check environment variables only if no explicit path evidence
        # This prevents false positives when uv is installed system-wide but we're in a venv
        uv_env_vars = False
        if not uv_path_patterns and not uv_tools_executable:
            uv_env_vars = bool(
                os.environ.get("UV_TOOL_DIR") or os.environ.get("UV_TOOL_BIN_DIR")
            )

        return uv_path_patterns or uv_tools_executable or uv_env_vars

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

    def detect(self) -> str:
        """
        Detect installation method with priority order.
        Returns: 'pipx' | 'conda' | 'uv' | 'pip-venv' | 'homebrew' | 'pip'
        """
        # Priority order matters - more specific first
        if self.detect_pipx():
            return "pipx"

        if self.detect_conda():
            return "conda"

        if self.detect_uv():
            return "uv"

        if self.detect_virtual_env():
            return "pip-venv"

        if self.detect_homebrew():
            return "homebrew"

        return "pip"


# TODO: Add strong typing
def detect_installation_method() -> str:
    """
    Detect how KiLM was installed to determine appropriate update strategy.
    Returns: 'pipx' | 'pip' | 'pip-venv' | 'uv' | 'conda' | 'homebrew'
    """
    detector = InstallationDetector()
    return detector.detect()


class PyPIVersionChecker:
    """Responsible PyPI API client with caching and proper headers."""

    def __init__(self, package_name: str, version: str = "unknown"):
        self.package_name = package_name
        self.base_url = f"https://pypi.org/pypi/{package_name}/json"
        self.cache_file = Path.home() / ".cache" / "kilm" / "version_check.json"
        self.user_agent = f"KiLM/{version} (+https://github.com/barisgit/KiLM)"

    def check_latest_version(self) -> Optional[str]:
        """
        Check latest version from PyPI with caching and rate limiting.
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

    def _load_cache(self) -> Optional[dict]:
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


def update_via_pipx() -> bool:
    """Update KiLM via pipx. Most reliable method for CLI tools."""
    try:
        result = subprocess.run(
            ["pipx", "upgrade", "kilm"], capture_output=True, text=True, timeout=300
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def update_via_pip() -> bool:
    """Update KiLM via pip."""
    try:
        # Use same Python interpreter that's running KiLM
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "kilm"],
            capture_output=True,
            text=True,
            timeout=300,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def update_via_uv() -> bool:
    """Update KiLM via uv."""
    try:
        result = subprocess.run(
            ["uv", "tool", "upgrade", "kilm"],
            capture_output=True,
            text=True,
            timeout=300,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


class UpdateManager:
    """Manages update checking and execution for KiLM."""

    def __init__(self, current_version: str):
        self.version_checker = PyPIVersionChecker("kilm")
        self.current_version = current_version
        self.installation_method = detect_installation_method()

    def check_latest_version(self) -> Optional[str]:
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

    def get_update_instruction(self) -> str:
        """Get update instruction for the detected installation method."""
        instructions = {
            "pipx": "pipx upgrade kilm",
            "pip": "pip install --upgrade kilm",
            "pip-venv": "pip install --upgrade kilm",
            "uv": "uv tool upgrade kilm",
            "conda": "Conda package not yet available (planned for future)",
            "homebrew": "Homebrew package not yet available (planned for future)",
        }
        return instructions.get(self.installation_method, "Check your package manager")

    def can_auto_update(self) -> bool:
        """Check if automatic update is possible for this installation method."""
        return self.installation_method in ["pipx", "pip", "pip-venv", "uv"]

    def perform_update(self) -> tuple[bool, str]:
        """
        Execute update using detected installation method.
        Returns: (success: bool, message: str)
        """
        if not self.can_auto_update():
            instruction = self.get_update_instruction()
            return False, f"Manual update required. Run: {instruction}"

        update_functions = {
            "pipx": update_via_pipx,
            "pip": update_via_pip,
            "pip-venv": update_via_pip,
            "uv": update_via_uv,
        }

        update_func = update_functions.get(self.installation_method)
        if update_func:
            try:
                success = update_func()
                if success:
                    return True, "KiLM updated successfully!"
                else:
                    instruction = self.get_update_instruction()
                    return False, f"Auto-update failed. Try manually: {instruction}"
            except Exception as e:
                return False, f"Update error: {str(e)}"
        else:
            instruction = self.get_update_instruction()
            return False, f"Unsupported installation method. Run: {instruction}"


class UpdateService:
    """Service wrapper for KiLM update functionality."""

    def __init__(self, current_version: str):
        self.manager = UpdateManager(current_version)
        self.current_version = current_version

    def check_for_updates(self, use_cache: bool = True) -> dict[str, Any]:
        """
        Check for available updates.

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
        """
        Show update notification if updates are available.

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
                    f"Run: [bold cyan]{update_cmd}[/bold cyan]",
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

    def get_installation_method(self) -> str:
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
        target_version: Optional[str] = None,
        force: bool = False,
        dry_run: bool = False,
    ) -> tuple[bool, str]:
        """
        Perform update installation.

        Args:
            target_version: Specific version to install
            force: Force update even if already up to date
            dry_run: Show what would be done without doing it

        Returns:
            tuple[bool, str]: (success, message)
        """
        if dry_run:
            return self._show_dry_run_info(target_version)

        # Check if update is needed (unless forced)
        if not force:
            update_info = self.check_for_updates()
            if not update_info["has_update"]:
                return True, "Already using the latest version!"

        # Perform the update
        return self.manager.perform_update()

    def _show_dry_run_info(
        self, target_version: Optional[str] = None
    ) -> tuple[bool, str]:
        """Show what would happen during an update."""
        from rich.console import Console
        from rich.panel import Panel

        console = Console()
        method = self.manager.installation_method
        can_auto_update = self.manager.can_auto_update()
        package_spec = f"kilm=={target_version}" if target_version else "kilm"
        update_cmd = self.manager.get_update_instruction()

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
