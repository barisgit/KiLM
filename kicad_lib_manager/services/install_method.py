"""How KiLM was installed, and the command that updates such an installation."""

import importlib.metadata
import os
import subprocess
import sys
from pathlib import Path, PurePath
from typing import Final, Literal

InstallMethod = Literal[
    "pipx", "conda", "uv", "nix", "pip-venv", "homebrew", "pip", "unknown"
]
"""How KiLM was installed; decides how it can be updated."""

UPGRADE_TIMEOUT_SECONDS: Final = 300
"""How long an installer may run before the update counts as failed."""

UPGRADE_ERROR_LINES: Final = 10
"""Trailing lines of installer output kept to explain a failed update."""

_MANUAL_INSTRUCTIONS: Final[dict[InstallMethod, str]] = {
    "conda": "Conda package not yet available (planned for future)",
    "homebrew": "Homebrew package not yet available (planned for future)",
    "nix": "nix flake update, then rebuild the configuration or profile"
    " that installs kilm",
    "unknown": "Update KiLM with the tool that installed it",
}
"""What to tell users of methods that `upgrade_command` cannot update."""


def read_installer() -> str | None:
    """Return the installer recorded for kilm (its INSTALLER file), if any."""
    try:
        installer = importlib.metadata.distribution("kilm").read_text("INSTALLER")
    except importlib.metadata.PackageNotFoundError:
        return None
    if installer is None:
        return None
    return installer.strip() or None


class InstallationDetector:
    """Infers the installation method from where the interpreter lives.

    The evidence is the interpreter path, the platform, the installer recorded
    in the package metadata, and the environment variables of the tools that
    create such environments. Path patterns are matched on the forward-slash
    form of the path, so they hold on Windows too.
    """

    def __init__(
        self,
        executable_path: PurePath | None = None,
        platform_name: str | None = None,
        *,
        installer: str | None = None,
    ) -> None:
        """Describe one interpreter.

        Args:
            executable_path: The interpreter; defaults to the running one.
            platform_name: An `os.name` value; defaults to the running one.
            installer: The installer recorded in kilm's metadata, if any.
        """
        self.executable_path = executable_path or Path(sys.executable)
        self.platform_name = platform_name or os.name
        self.installer = installer
        self.executable_str = self.executable_path.as_posix()

    def is_windows(self) -> bool:
        """Return whether the interpreter runs on Windows."""
        return self.platform_name == "nt"

    def detect_pipx(self) -> bool:
        """Return whether the interpreter is a pipx environment."""
        if any(
            part in self.executable_str for part in (".local/share/pipx", "pipx/venvs")
        ):
            return True
        return bool(os.environ.get("PIPX_HOME")) and "pipx" in self.executable_str

    def detect_conda(self) -> bool:
        """Return whether the interpreter lives in a conda environment.

        An activated environment (``CONDA_DEFAULT_ENV``) is no evidence on its
        own, since many shells activate conda's base environment by default.
        """
        if "conda" in self.executable_str:
            return True
        return self._is_inside_env_dir("CONDA_PREFIX")

    def detect_uv(self) -> bool:
        """Return whether the interpreter lives in a uv tools directory.

        uv keeps tool environments in ``uv/tools`` under its data directory
        (``uv/data/tools`` on Windows) unless ``UV_TOOL_DIR`` moves them. The
        variable alone is no evidence: it is also set where uv manages other
        tools, so only an interpreter inside that directory counts.
        """
        if any(
            part in self.executable_str for part in ("/uv/tools/", "/uv/data/tools/")
        ):
            return True
        return self._is_inside_env_dir("UV_TOOL_DIR")

    @staticmethod
    def detect_virtual_env() -> bool:
        """Return whether the running interpreter is a virtual environment."""
        if os.environ.get("VIRTUAL_ENV", ""):
            return True
        return sys.prefix != getattr(sys, "base_prefix", sys.prefix)

    def detect_homebrew(self) -> bool:
        """Return whether the interpreter belongs to Homebrew."""
        if self.is_windows():
            return False
        return self.executable_str.startswith(("/opt/homebrew/", "/usr/local/Cellar/"))

    def detect_nix(self) -> bool:
        """Return whether the interpreter lives in the Nix store."""
        return self.executable_str.startswith("/nix/store/")

    def detect(self) -> InstallMethod:
        """Return the installation method, most specific evidence first.

        Returns "unknown" rather than guessing when nothing identifies the
        installer, so callers never suggest a command that cannot work.
        """
        checks: tuple[tuple[InstallMethod, bool], ...] = (
            ("pipx", self.detect_pipx()),
            ("conda", self.detect_conda()),
            ("uv", self.detect_uv()),
            ("nix", self.detect_nix()),
            ("pip-venv", self.detect_virtual_env()),
            ("homebrew", self.detect_homebrew()),
            ("pip", self.installer == "pip"),
        )
        return next((method for method, found in checks if found), "unknown")

    def _is_inside_env_dir(self, variable: str) -> bool:
        """Return whether the interpreter is inside the directory `variable` names."""
        directory = os.environ.get(variable, "")
        return bool(directory) and self.executable_path.is_relative_to(
            type(self.executable_path)(directory)
        )


def detect_installation_method() -> InstallMethod:
    """Return how the running KiLM was installed."""
    return InstallationDetector(installer=read_installer()).detect()


def upgrade_command(
    method: InstallMethod, target_version: str | None = None
) -> list[str] | None:
    """Return the command that updates kilm for an install method, as shown to users.

    Without a target version the command upgrades to the latest release; with
    one it installs exactly that version, which may be a downgrade. Returns
    None for methods where kilm cannot update itself.
    """
    if method == "pipx":
        if target_version is not None:
            return ["pipx", "install", "--force", f"kilm=={target_version}"]
        return ["pipx", "upgrade", "kilm"]
    if method == "uv":
        # `uv tool upgrade` keeps an exact pin from an earlier install and
        # then succeeds without changing anything; `uv tool install` replaces
        # the pin.
        spec = "kilm@latest" if target_version is None else f"kilm=={target_version}"
        return ["uv", "tool", "install", spec]
    if method in {"pip", "pip-venv"}:
        spec = "kilm" if target_version is None else f"kilm=={target_version}"
        return ["pip", "install", "--upgrade", spec]
    return None


def update_instruction(method: InstallMethod, target_version: str | None = None) -> str:
    """Return what a user runs or does to update an installation by hand."""
    command = upgrade_command(method, target_version)
    if command is not None:
        return " ".join(command)
    return _MANUAL_INSTRUCTIONS[method]


def run_upgrade(command: list[str]) -> str | None:
    """Run an upgrade command from `upgrade_command`.

    Returns None on success, otherwise why it failed: the end of the
    installer's error output, or why the installer could not run.
    """
    # pip runs through this interpreter so it updates the running environment.
    argv = [sys.executable, "-m", *command] if command[0] == "pip" else command
    try:
        result = subprocess.run(  # noqa: S603 -- argv comes from upgrade_command, not user input
            argv,
            capture_output=True,
            text=True,
            timeout=UPGRADE_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return f"{command[0]} did not finish within {UPGRADE_TIMEOUT_SECONDS} seconds"
    except OSError as exc:
        return f"Could not run {command[0]}: {exc.strerror or exc}"
    if result.returncode == 0:
        return None
    output = (result.stderr or result.stdout).strip().splitlines()
    detail = "\n".join(output[-UPGRADE_ERROR_LINES:])
    return detail or f"{command[0]} exited with status {result.returncode}"
