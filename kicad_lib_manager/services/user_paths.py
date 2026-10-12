"""Where KiLM keeps its per-user configuration and cache files."""

from pathlib import Path
from typing import Final

from kicad_lib_manager.utils.constants import CONFIG_DIR_NAME, CONFIG_FILE_NAME

CACHE_DIR_NAME: Final = "kilm"
"""Directory under ~/.cache for version checks and update-check timestamps."""


def user_config_file() -> Path:
    """Return the KiLM configuration file of the current user."""
    return Path.home() / ".config" / CONFIG_DIR_NAME / CONFIG_FILE_NAME


def user_cache_dir() -> Path:
    """Return the KiLM cache directory of the current user."""
    return Path.home() / ".cache" / CACHE_DIR_NAME
