"""Option handling shared by several commands."""

import typer

from kicad_lib_manager.utils.console import get_console
from kicad_lib_manager.utils.env_vars import (
    expand_user_path,
    find_environment_variables,
)

SYMBOL_DIR_VAR = "KICAD_USER_LIB"
"""The variable naming the main symbol and footprint library directory."""

MODELS_DIR_VAR = "KICAD_3D_LIB"
"""The variable naming the main 3D model library directory."""


def given(value: str | None) -> str | None:
    """Return ``value``, or None when an option was omitted or set to ``""``.

    Commands treat an empty option or environment variable as not given, so
    callers can test for None afterwards.
    """
    return None if value == "" else value


def parse_assignments(assignments: list[str]) -> dict[str, str]:
    """Parse ``name=value`` options into a mapping.

    Splits at the first ``=`` and strips both sides. Entries without ``=``
    are ignored, and a later assignment to a name replaces an earlier one.
    """
    parsed: dict[str, str] = {}
    for assignment in assignments:
        key, separator, value = assignment.partition("=")
        if separator:
            parsed[key.strip()] = value.strip()
    return parsed


def resolve_kicad_lib_dir(option: str | None) -> str:
    """Return the symbol and footprint library directory with ``~`` expanded.

    Uses ``option`` when given, otherwise ``KICAD_USER_LIB`` from the places
    ``find_environment_variables`` searches. Prints an error and exits with
    status 1 when neither names a directory.
    """
    directory = given(option) or given(find_environment_variables(SYMBOL_DIR_VAR))
    if directory is None:
        get_console().print("[red]Error: KICAD_USER_LIB not set and not provided[/red]")
        raise typer.Exit(1)
    return expand_user_path(directory)
