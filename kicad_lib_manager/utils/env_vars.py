"""Library paths from the user's environment, and KiCad's kicad_common.json.

find_environment_variables looks a library path up the way a user would set
it. The update functions change the environment variables and pinned
libraries in kicad_common.json, backing the file up first and replacing it
atomically.
"""

import json
import os
import re
import shutil
import subprocess
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import NamedTuple, cast

from kicad_lib_manager.services.config_service import Config
from kicad_lib_manager.utils.constants import (
    CLOUD_METADATA_FILE,
    DEFAULT_MAX_BACKUPS,
    GITHUB_METADATA_FILE,
    KICAD_COMMON_FILE,
    MODELS_DIR_VAR,
    SYMBOL_DIR_VAR,
)
from kicad_lib_manager.utils.kicad_common import (
    PINNED_FOOTPRINTS_KEY,
    PINNED_SYMBOLS_KEY,
    JsonObject,
    replace_json_object,
)


class KiCadConfigError(ValueError):
    """kicad_common.json is not valid JSON or not shaped as KiCad writes it."""


class _LibraryVariable(NamedTuple):
    """How KiLM derives a main library variable without the user setting it."""

    configured_path: Callable[[Config], str | None]
    """Reads the current library of this kind from the KiLM configuration."""
    marker_file: str
    """The metadata file that makes a directory a library of this kind."""


_LIBRARY_VARIABLES = {
    SYMBOL_DIR_VAR: _LibraryVariable(
        lambda config: config.get_symbol_library_path(), GITHUB_METADATA_FILE
    ),
    MODELS_DIR_VAR: _LibraryVariable(
        lambda config: config.get_3d_library_path(), CLOUD_METADATA_FILE
    ),
}
_SHELL_FILES = (".bashrc", ".bash_profile", ".profile", ".zshrc")


def find_environment_variables(var_name: str) -> str | None:
    """Return the value of var_name from the first source that defines it.

    The sources, in order: the KiLM configuration (current library paths, for
    KICAD_USER_LIB and KICAD_3D_LIB), a library metadata file in the current
    directory (the directory then is the library), the process environment,
    fish universal variables, and export lines in ~/.bashrc, ~/.bash_profile,
    ~/.profile, and ~/.zshrc. A source that fails to read is skipped.

    Returns:
        The value, or None when no source defines it.
    """
    lookups: tuple[Callable[[str], str | None], ...] = (
        _from_config,
        _from_current_directory,
        os.environ.get,
        _from_fish,
        _from_shell_files,
    )
    for lookup in lookups:
        value = lookup(var_name)
        if value is not None:
            return value
    return None


def _from_config(var_name: str) -> str | None:
    variable = _LIBRARY_VARIABLES.get(var_name)
    if variable is None:
        return None
    try:
        path = variable.configured_path(Config())
    except (OSError, LookupError, TypeError, ValueError):
        return None
    return path or None


def _from_current_directory(var_name: str) -> str | None:
    variable = _LIBRARY_VARIABLES.get(var_name)
    if variable is None:
        return None
    try:
        current_dir = Path.cwd().resolve()
        is_library = (current_dir / variable.marker_file).exists()
    except OSError:
        return None
    return str(current_dir) if is_library else None


def _from_fish(var_name: str) -> str | None:
    fish = shutil.which("fish")
    if fish is None:
        return None
    try:
        result = subprocess.run(  # noqa: S603 -- fixed fish command; var_name comes from KiLM code, not user input
            [fish, "-c", f"echo ${var_name}"],
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    return result.stdout.strip() or None


def _from_shell_files(var_name: str) -> str | None:
    pattern = re.compile(rf"^(?:export\s+)?{re.escape(var_name)}=[\'\"]?(.*?)[\'\"]?$")
    home = Path.home()
    for name in _SHELL_FILES:
        try:
            text = (home / name).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            match = pattern.search(line.strip())
            if match:
                return str(match.group(1))
    return None


def expand_user_path(path: str) -> str:
    """Return path with a leading ~ expanded to the home directory."""
    if path.startswith("~"):
        return str(Path(path).expanduser())
    return path


def update_kicad_env_vars(
    kicad_config: Path,
    env_vars: Mapping[str, str | None],
    *,
    dry_run: bool = False,
    max_backups: int = DEFAULT_MAX_BACKUPS,
) -> bool:
    """Set or remove environment variables in kicad_common.json.

    A None value removes the variable; blank values are ignored. Paths are
    stored with forward slashes. The file is backed up and rewritten only
    when something changes, and never in a dry run.

    Args:
        kicad_config: KiCad's configuration directory.
        env_vars: Variable name to value (None removes it).
        dry_run: Report whether anything would change without writing.
        max_backups: Number of backups of kicad_common.json to keep.

    Returns:
        Whether the variables differ (or would differ) from the file.

    Raises:
        FileNotFoundError: kicad_common.json does not exist.
        KiCadConfigError: kicad_common.json is not valid JSON of the expected shape.
    """
    requested = {k: v for k, v in env_vars.items() if v is None or v.strip()}
    if not requested:
        return False

    kicad_common, config = _load_kicad_common(kicad_config)
    environment = _object_entry(config, "environment", kicad_common)
    current = _object_entry(environment, "vars", kicad_common)
    updated = dict(current)
    for key, value in requested.items():
        if value is None:
            updated.pop(key, None)
        else:
            updated[key] = value.replace("\\", "/")

    if updated == current:
        return False
    if not dry_run:
        environment["vars"] = updated
        replace_json_object(kicad_common, config, max_backups=max_backups)
    return True


def update_pinned_libraries(
    kicad_config: Path,
    *,
    symbol_libs: Sequence[str] | None = None,
    footprint_libs: Sequence[str] | None = None,
    dry_run: bool = False,
    max_backups: int = DEFAULT_MAX_BACKUPS,
) -> bool:
    """Pin libraries in kicad_common.json, keeping those already pinned.

    The file is backed up and rewritten only when a library is newly pinned,
    and never in a dry run.

    Args:
        kicad_config: KiCad's configuration directory.
        symbol_libs: Symbol library names to pin.
        footprint_libs: Footprint library names to pin.
        dry_run: Report whether anything would change without writing.
        max_backups: Number of backups of kicad_common.json to keep.

    Returns:
        Whether a library is (or would be) newly pinned.

    Raises:
        FileNotFoundError: kicad_common.json does not exist.
        KiCadConfigError: kicad_common.json is not valid JSON of the expected shape.
    """
    requested = {
        PINNED_SYMBOLS_KEY: () if symbol_libs is None else symbol_libs,
        PINNED_FOOTPRINTS_KEY: () if footprint_libs is None else footprint_libs,
    }
    if not any(requested.values()):
        return False

    kicad_common, config = _load_kicad_common(kicad_config)
    if config.get("session") is None:
        config["session"] = {
            PINNED_SYMBOLS_KEY: [],
            PINNED_FOOTPRINTS_KEY: [],
            "remember_open_files": False,
        }
    session = _object_entry(config, "session", kicad_common)
    changed = False
    for key, libs in requested.items():
        pinned = _list_entry(session, key, kicad_common)
        new = [lib for lib in dict.fromkeys(libs) if lib not in pinned]
        changed = changed or bool(new)
        if not dry_run:
            pinned.extend(new)

    if changed and not dry_run:
        replace_json_object(kicad_common, config, max_backups=max_backups)
    return changed


def _load_kicad_common(kicad_config: Path) -> tuple[Path, JsonObject]:
    """Path and parsed content of kicad_common.json in kicad_config."""
    kicad_common = kicad_config / KICAD_COMMON_FILE
    if not kicad_common.exists():
        msg = f"KiCad common configuration file not found at {kicad_common}"
        raise FileNotFoundError(msg)
    try:
        document: object = json.loads(kicad_common.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        msg = f"Invalid JSON format in {kicad_common}"
        raise KiCadConfigError(msg) from e
    if not isinstance(document, dict):
        msg = f"Invalid KiCad configuration in {kicad_common}: expected an object"
        raise KiCadConfigError(msg)
    return kicad_common, cast("JsonObject", document)


def _object_entry(parent: JsonObject, key: str, kicad_common: Path) -> JsonObject:
    """parent[key] as a JSON object; an absent or null entry becomes {}."""
    value = parent.get(key)
    if value is None:
        created: JsonObject = {}
        parent[key] = created
        return created
    if not isinstance(value, dict):
        msg = f"Invalid {key!r} in {kicad_common}: expected an object"
        raise KiCadConfigError(msg)
    return cast("JsonObject", value)


def _list_entry(parent: JsonObject, key: str, kicad_common: Path) -> list[object]:
    """parent[key] as a JSON array; an absent or null entry becomes []."""
    value = parent.get(key)
    if value is None:
        created: list[object] = []
        parent[key] = created
        return created
    if not isinstance(value, list):
        msg = f"Invalid {key!r} in {kicad_common}: expected an array"
        raise KiCadConfigError(msg)
    return cast("list[object]", value)
