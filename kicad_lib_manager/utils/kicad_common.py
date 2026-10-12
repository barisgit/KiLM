"""KiCad's ``kicad_common.json``: typed reads and backed-up atomic writes.

KiCad keeps environment variables under ``environment.vars`` and the pinned
libraries under ``session.pinned_symbol_libs`` and ``session.pinned_fp_libs``.
The helpers here narrow the parsed JSON to the parts KiLM uses and replace
the file atomically after backing it up, so a failed write never leaves
KiCad with a truncated configuration.
"""

import json
from pathlib import Path

from kicad_lib_manager.utils.backup import create_backup
from kicad_lib_manager.utils.file_ops import write_atomically

JsonObject = dict[str, object]
"""A parsed JSON object."""

PINNED_SYMBOLS_KEY = "pinned_symbol_libs"
PINNED_FOOTPRINTS_KEY = "pinned_fp_libs"


def as_json_object(value: object) -> JsonObject | None:
    """Return a copy of ``value`` with text keys, or None when it is not a dict."""
    if not isinstance(value, dict):
        return None
    return {str(key): item for key, item in value.items()}


def as_list(value: object) -> list[object]:
    """Return a copy of ``value`` when it is a list, otherwise an empty list."""
    if not isinstance(value, list):
        return []
    return [*value]


def session_of(config: JsonObject) -> JsonObject | None:
    """Return a copy of the ``session`` object of ``config``, if it has one."""
    return as_json_object(config.get("session"))


def pinned_names(session: JsonObject, key: str) -> list[str]:
    """Return the library names pinned under ``key`` in ``session``."""
    return [name for name in as_list(session.get(key)) if isinstance(name, str)]


def load_json_object(path: Path) -> JsonObject:
    """Read the JSON object stored in ``path``.

    Raises:
        OSError: The file cannot be read.
        ValueError: The file is not JSON or does not hold an object.
    """
    data = as_json_object(json.loads(path.read_text(encoding="utf-8")))
    if data is None:
        msg = f"{path} does not contain a JSON object"
        raise ValueError(msg)
    return data


def replace_json_object(path: Path, data: JsonObject, *, max_backups: int) -> None:
    """Back up ``path``, then replace it atomically with ``data`` as indented JSON.

    ``max_backups`` is the number of backups of ``path`` to keep.
    """
    create_backup(path, max_backups)
    write_atomically(path, json.dumps(data, indent=2).encode("utf-8"))
