"""Tests for installation method detection and the installer commands."""

import subprocess
import sys
from pathlib import PurePath, PurePosixPath, PureWindowsPath

import pytest

from kicad_lib_manager.services import install_method
from kicad_lib_manager.services.install_method import (
    InstallationDetector,
    InstallMethod,
    detect_installation_method,
    run_upgrade,
    update_instruction,
    upgrade_command,
)

PIPX_PYTHON = "/Users/user/.local/share/pipx/venvs/kilm/bin/python"
UV_PYTHON = "/Users/user/.local/share/uv/tools/kilm/bin/python"


@pytest.fixture(autouse=True)
def outside_any_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Detect as if no tool environment were active, whatever runs the tests.

    CI runners and dev shells export these variables (setup-uv on Windows sets
    UV_TOOL_DIR, for example), and the test interpreter usually runs in a venv.
    """
    for variable in (
        "PIPX_HOME",
        "CONDA_DEFAULT_ENV",
        "CONDA_PREFIX",
        "UV_TOOL_DIR",
        "UV_TOOL_BIN_DIR",
        "VIRTUAL_ENV",
    ):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setattr(sys, "prefix", sys.base_prefix)


def detect(executable: PurePath, **kwargs: str) -> InstallMethod:
    """Detect the method for an interpreter at `executable`."""
    return InstallationDetector(executable_path=executable, **kwargs).detect()


class TestInstallationDetector:
    """Which evidence identifies which installation method."""

    @pytest.mark.parametrize(
        ("executable", "expected"),
        [
            (PurePosixPath(PIPX_PYTHON), "pipx"),
            (PurePosixPath("/opt/miniconda3/envs/kilm/bin/python"), "conda"),
            (PurePosixPath(UV_PYTHON), "uv"),
            (PurePosixPath("/nix/store/abc123-python3-3.12.9/bin/python3.12"), "nix"),
            (PurePosixPath("/opt/homebrew/bin/python3"), "homebrew"),
            (PurePosixPath("/usr/bin/python3"), "unknown"),
            (
                PureWindowsPath(r"C:\Users\user\pipx\venvs\kilm\Scripts\python.exe"),
                "pipx",
            ),
            (
                PureWindowsPath(
                    r"C:\Users\user\AppData\Roaming\uv\tools\kilm\Scripts\python.exe"
                ),
                "uv",
            ),
            (
                PureWindowsPath(
                    r"C:\Users\user\AppData\Roaming\uv\data\tools\kilm\Scripts\python.exe"
                ),
                "uv",
            ),
        ],
    )
    def test_interpreter_location_identifies_the_method(
        self, executable: PurePath, expected: InstallMethod
    ) -> None:
        """Tool environments are recognized by path, with either separator."""
        platform_name = "nt" if isinstance(executable, PureWindowsPath) else "posix"
        assert detect(executable, platform_name=platform_name) == expected

    def test_homebrew_paths_do_not_apply_on_windows(self) -> None:
        """A Homebrew-looking path on Windows is no Homebrew install."""
        executable = PurePosixPath("/opt/homebrew/bin/python3")
        assert detect(executable, platform_name="nt") == "unknown"

    def test_pipx_home_with_a_pipx_interpreter(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """PIPX_HOME moves pipx environments out of the default location."""
        monkeypatch.setenv("PIPX_HOME", "/opt/pipx")
        assert detect(PurePosixPath("/opt/pipx/bin/python")) == "pipx"

    def test_conda_prefix_containing_the_interpreter(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An interpreter inside the active CONDA_PREFIX is a conda install."""
        monkeypatch.setenv("CONDA_PREFIX", "/opt/envs/kilm-env")
        assert detect(PurePosixPath("/opt/envs/kilm-env/bin/python")) == "conda"

    def test_active_conda_env_alone_is_not_a_conda_install(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Many shells activate conda's base env, whatever installed kilm."""
        monkeypatch.setenv("CONDA_DEFAULT_ENV", "base")
        monkeypatch.setenv("CONDA_PREFIX", "/opt/envs/base")
        assert detect(PurePosixPath(UV_PYTHON)) == "uv"

    def test_uv_tool_dir_containing_the_interpreter(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An interpreter inside UV_TOOL_DIR is a uv tool install."""
        monkeypatch.setenv("UV_TOOL_DIR", "/custom/uv-tools")
        assert detect(PurePosixPath("/custom/uv-tools/kilm/bin/python")) == "uv"

    def test_uv_env_vars_alone_are_not_a_uv_install(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """UV_TOOL_DIR and UV_TOOL_BIN_DIR only say where uv puts tools.

        They are set on CI runners and in shells that use uv for other tools,
        so they must not turn a kilm running elsewhere into a uv install.
        """
        monkeypatch.setenv("UV_TOOL_DIR", "/Users/user/.local/share/uv/tools")
        monkeypatch.setenv("UV_TOOL_BIN_DIR", "/Users/user/.local/bin")
        assert detect(PurePosixPath("/usr/bin/python")) == "unknown"

    def test_virtual_env_variable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An activated virtual environment is a pip-in-venv install."""
        monkeypatch.setenv("VIRTUAL_ENV", "/path/to/venv")
        assert detect(PurePosixPath("/path/to/venv/bin/python")) == "pip-venv"

    def test_virtual_env_prefix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A running venv interpreter is a pip-in-venv install."""
        monkeypatch.setattr(sys, "prefix", "/path/to/venv")
        monkeypatch.setattr(sys, "base_prefix", "/usr/local")
        assert detect(PurePosixPath("/path/to/venv/bin/python")) == "pip-venv"

    def test_tool_environments_win_over_their_venv(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """pipx, uv, and Nix environments are venvs too; the tool decides."""
        monkeypatch.setenv("VIRTUAL_ENV", "/home/user/project/.venv")
        assert detect(PurePosixPath(PIPX_PYTHON)) == "pipx"
        assert detect(PurePosixPath("/nix/store/abc-python3/bin/python3")) == "nix"

    def test_pip_installer_record(self) -> None:
        """Outside any environment, pip's INSTALLER record identifies pip."""
        assert detect(PurePosixPath("/usr/bin/python3"), installer="pip") == "pip"

    def test_running_interpreter_and_metadata(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """detect_installation_method inspects the running interpreter."""
        monkeypatch.setattr(sys, "executable", PIPX_PYTHON)
        assert detect_installation_method() == "pipx"


class TestUpgradeCommand:
    """The installer command for each method."""

    @pytest.mark.parametrize(
        ("method", "target_version", "expected"),
        [
            ("pipx", None, "pipx upgrade kilm"),
            ("pipx", "1.0.5", "pipx install --force kilm==1.0.5"),
            # `uv tool upgrade` would keep an earlier exact pin.
            ("uv", None, "uv tool install kilm@latest"),
            ("uv", "1.0.5", "uv tool install kilm==1.0.5"),
            ("pip", None, "pip install --upgrade kilm"),
            ("pip-venv", "1.0.5", "pip install --upgrade kilm==1.0.5"),
        ],
    )
    def test_automatic_methods(
        self, method: InstallMethod, target_version: str | None, expected: str
    ) -> None:
        """Automatic methods install the latest release or exactly the target."""
        assert update_instruction(method, target_version) == expected

    @pytest.mark.parametrize(
        ("method", "expected"),
        [
            ("conda", "Conda package not yet available (planned for future)"),
            ("homebrew", "Homebrew package not yet available (planned for future)"),
            (
                "nix",
                (
                    "nix flake update, then rebuild the configuration or profile"
                    " that installs kilm"
                ),
            ),
            ("unknown", "Update KiLM with the tool that installed it"),
        ],
    )
    def test_manual_methods(self, method: InstallMethod, expected: str) -> None:
        """Methods KiLM cannot update get advice instead of a command."""
        assert upgrade_command(method) is None
        assert update_instruction(method) == expected


class TestRunUpgrade:
    """Running an installer and explaining its failure."""

    @pytest.fixture
    def calls(self, monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
        """Record installer runs; each fails with a long error output."""
        recorded: list[list[str]] = []

        def fake_run(
            argv: list[str], **_kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            recorded.append(argv)
            error = "".join(f"line {number}\n" for number in range(20))
            return subprocess.CompletedProcess(argv, 1, "", error)

        monkeypatch.setattr(install_method.subprocess, "run", fake_run)
        return recorded

    def test_pip_runs_in_the_running_interpreter(self, calls: list[list[str]]) -> None:
        """Pip updates the environment kilm runs in, not whatever pip is on PATH."""
        run_upgrade(["pip", "install", "--upgrade", "kilm"])
        assert calls == [[sys.executable, "-m", "pip", "install", "--upgrade", "kilm"]]

    def test_failure_reports_the_end_of_the_error_output(
        self, calls: list[list[str]]
    ) -> None:
        """The last lines of the installer's output explain the failure."""
        error = run_upgrade(["pipx", "upgrade", "kilm"])
        assert calls == [["pipx", "upgrade", "kilm"]]
        assert error == "\n".join(f"line {number}" for number in range(10, 20))

    def test_missing_installer(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An installer that cannot start is reported, not raised."""

        def fake_run(argv: list[str], **_kwargs: object) -> None:
            raise FileNotFoundError(2, "No such file or directory", argv[0])

        monkeypatch.setattr(install_method.subprocess, "run", fake_run)
        error = run_upgrade(["pipx", "upgrade", "kilm"])
        assert error == "Could not run pipx: No such file or directory"

    def test_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A zero exit status is success."""

        def fake_run(
            argv: list[str], **_kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(argv, 0, "done", "")

        monkeypatch.setattr(install_method.subprocess, "run", fake_run)
        assert run_upgrade(["uv", "tool", "install", "kilm@latest"]) is None
