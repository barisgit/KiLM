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
from typing import Optional

import requests
from packaging.version import InvalidVersion, Version


def detect_installation_method() -> str:
    """
    Detect how KiLM was installed to determine appropriate update strategy.
    Returns: 'pipx' | 'pip' | 'pip-venv' | 'uv' | 'conda'
    """
    executable_path = Path(sys.executable)

    # Check for pipx installation
    if any(
        part in str(executable_path) for part in [".local/share/pipx", "pipx/venvs"]
    ):
        return "pipx"

    if os.environ.get("PIPX_HOME") and "pipx" in str(executable_path):
        return "pipx"

    # Check for conda installation
    if os.environ.get("CONDA_DEFAULT_ENV") or "conda" in str(executable_path):
        return "conda"

    # Check for uv installation (only via official environment variables)
    if os.environ.get("UV_TOOL_DIR") or os.environ.get("UV_TOOL_BIN_DIR"):
        return "uv"

    # Check for virtual environment (pip in venv)
    if os.environ.get("VIRTUAL_ENV") or sys.prefix != getattr(
        sys, "base_prefix", sys.prefix
    ):
        return "pip-venv"

    # Check for homebrew installation (strict path check)
    if str(executable_path).startswith(("/opt/homebrew/", "/usr/local/Cellar/")):
        return "homebrew"

    # Default to system pip
    return "pip"


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

    def check_for_updates(self) -> Optional[str]:
        """Check for available updates."""
        return self.manager.check_latest_version()

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

    def perform_update(self) -> tuple[bool, str]:
        """Perform the update."""
        return self.manager.perform_update()
