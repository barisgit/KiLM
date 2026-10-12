"""Locate KiCad's per-user configuration directory."""

import os
import platform
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Final

from kicad_lib_manager.utils.constants import FOOTPRINT_TABLE_FILE, SYMBOL_TABLE_FILE

RUN_KICAD_FIRST: Final = "Please run KiCad at least once before using this tool."


def kicad_config_root(system: str, home: Path, environ: Mapping[str, str]) -> Path:
    """Return the directory holding KiCad's per-version configuration directories.

    Raises:
        FileNotFoundError: The platform is not supported, or on Windows
            APPDATA is not set.
    """
    if system == "Darwin":
        return home / "Library" / "Preferences" / "kicad"
    if system == "Linux":
        return home / ".config" / "kicad"
    if system == "Windows":
        appdata = environ.get("APPDATA", "")
        if not appdata:
            msg = "APPDATA environment variable not found"
            raise FileNotFoundError(msg)
        return Path(appdata) / "kicad"
    msg = f"Unsupported platform: {system}"
    raise FileNotFoundError(msg)


def find_kicad_config(
    *,
    system: str | None = None,
    home: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> Path:
    """Return the configuration directory of the newest KiCad version.

    Version directories are those whose names contain a digit, ordered by
    their numbers (10.0 after 9.0). The chosen one must hold a symbol or
    footprint library table.

    Args:
        system: Platform name as from `platform.system()`; defaults to it.
        home: Home directory; defaults to the user's.
        environ: Environment; defaults to `os.environ`.

    Raises:
        FileNotFoundError: KiCad has no configuration directory, version
            directory, or library table, typically because it never ran.
    """
    root = kicad_config_root(
        system or platform.system(),
        home or Path.home(),
        os.environ if environ is None else environ,
    )
    if not root.exists():
        msg = f"KiCad configuration directory not found at {root}. {RUN_KICAD_FIRST}"
        raise FileNotFoundError(msg)

    versions = [
        entry
        for entry in root.iterdir()
        if entry.is_dir() and any(c.isdigit() for c in entry.name)
    ]
    if not versions:
        msg = f"No KiCad version directories found in {root}. {RUN_KICAD_FIRST}"
        raise FileNotFoundError(msg)

    latest = max(versions, key=lambda entry: (_version_key(entry), entry.name))
    if (
        not (latest / SYMBOL_TABLE_FILE).exists()
        and not (latest / FOOTPRINT_TABLE_FILE).exists()
    ):
        msg = f"KiCad library tables not found in {latest}. {RUN_KICAD_FIRST}"
        raise FileNotFoundError(msg)
    return latest


def _version_key(version_dir: Path) -> tuple[int, ...]:
    """Return the numbers in a version directory name, for numeric ordering."""
    return tuple(int(part) for part in re.findall(r"\d+", version_dir.name))
