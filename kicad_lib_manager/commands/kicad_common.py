"""Typed access to KiCad's ``kicad_common.json``.

KiCad keeps environment variables under ``environment.vars`` and the pinned
libraries under ``session.pinned_symbol_libs`` and ``session.pinned_fp_libs``.
The helpers here read the JSON into plain objects, narrow the parts the
commands use, and write the file back atomically, so a failed write never
leaves KiCad with a truncated configuration.
"""

import json
from pathlib import Path

from kicad_lib_manager.utils.file_ops import write_atomically

KICAD_COMMON_FILE = "kicad_common.json"
PINNED_SYMBOLS_KEY = "pinned_symbol_libs"
PINNED_FOOTPRINTS_KEY = "pinned_fp_libs"

JsonObject = dict[str, object]


def as_json_object(value: object) -> JsonObject | None:
    """Return ``value`` as a JSON object, or None when it is not one."""
    if not isinstance(value, dict):
        return None
    return {str(key): item for key, item in value.items()}


def as_list(value: object) -> list[object]:
    """Return ``value`` when it is a JSON array, otherwise an empty list."""
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


def save_json_object(path: Path, data: JsonObject) -> None:
    """Replace ``path`` atomically with ``data`` as indented JSON."""
    write_atomically(path, json.dumps(data, indent=2).encode("utf-8"))
