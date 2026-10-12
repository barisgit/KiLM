"""Rich output follows the stream that is current when output is written."""

import importlib
import io
import pkgutil

import pytest
from rich.console import Console

import kicad_lib_manager
from kicad_lib_manager.utils.console import get_console


class TerminalStream:
    """A minimal text stream that reports itself as a terminal."""

    def write(self, text: str) -> int:
        """Discard the text; only terminal detection matters here."""
        return len(text)

    def flush(self) -> None:
        """Nothing is buffered."""

    def isatty(self) -> bool:
        """Claim to be a terminal so Rich enables color."""
        return True


def test_no_module_holds_a_console() -> None:
    """Importing the package creates no Console that would freeze color detection."""
    holders: list[str] = []
    for module_info in pkgutil.walk_packages(
        kicad_lib_manager.__path__, f"{kicad_lib_manager.__name__}."
    ):
        module = importlib.import_module(module_info.name)
        holders.extend(
            f"{module_info.name}.{name}"
            for name, value in vars(module).items()
            if isinstance(value, Console)
        )
    assert not holders, f"Module-level consoles: {holders}"


def test_get_console_detects_the_current_stdout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A console obtained after redirecting stdout reflects the new stream."""
    for name in ("NO_COLOR", "FORCE_COLOR", "TTY_COMPATIBLE", "TTY_INTERACTIVE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")

    monkeypatch.setattr("sys.stdout", TerminalStream())
    assert get_console().color_system is not None

    monkeypatch.setattr("sys.stdout", io.StringIO())
    assert get_console().color_system is None
