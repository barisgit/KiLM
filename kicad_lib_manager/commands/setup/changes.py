"""The changes ``kilm setup`` makes to the KiCad configuration."""

import re
from dataclasses import dataclass
from pathlib import Path

from kicad_lib_manager.commands.shared import MODELS_DIR_VAR, SYMBOL_DIR_VAR
from kicad_lib_manager.services.library_service import LibraryService
from kicad_lib_manager.utils.backup import create_backup
from kicad_lib_manager.utils.console import get_console
from kicad_lib_manager.utils.env_vars import (
    update_kicad_env_vars,
    update_pinned_libraries,
)
from kicad_lib_manager.utils.file_ops import list_libraries, write_atomically

SYMBOL_TABLE = "sym-lib-table"
FOOTPRINT_TABLE = "fp-lib-table"

# A path wrapped as if it were a variable: ``(uri "${/path/lib}/Lib.kicad_sym")``.
_WRAPPED_URI = re.compile(r'\(uri "\${(\/[^}]+)}\/(.*?)"\)')


@dataclass(frozen=True)
class ChangeOptions:
    """Where and how setup changes the KiCad configuration."""

    kicad_config: Path
    dry_run: bool
    max_backups: int
    verbose: bool


@dataclass(frozen=True)
class SetupLibraries:
    """The library directories setup writes to KiCad.

    Attributes:
        symbol_dir: The main symbol library directory, set as KICAD_USER_LIB.
        models_dir: The main 3D model directory, set as KICAD_3D_LIB.
        library_vars: Each configured library's environment variable and path.
    """

    symbol_dir: str
    models_dir: str | None
    library_vars: dict[str, str]

    def env_vars(self) -> dict[str, str]:
        """Return every environment variable setup sets in KiCad."""
        env_vars = {SYMBOL_DIR_VAR: self.symbol_dir}
        if self.models_dir is not None:
            env_vars[MODELS_DIR_VAR] = self.models_dir
        env_vars.update(self.library_vars)
        return env_vars

    def model_dirs(self) -> dict[str, str]:
        """Return the 3D model directories by environment variable."""
        model_dirs = {
            name: path
            for name, path in self.library_vars.items()
            if name.startswith("KICAD_3D_")
        }
        if self.models_dir is not None:
            model_dirs.setdefault(MODELS_DIR_VAR, self.models_dir)
        return model_dirs


def fix_invalid_uris(
    kicad_config: Path,
    *,
    backup_first: bool = True,
    max_backups: int = 5,
    dry_run: bool = False,
) -> bool:
    """Unwrap library paths written as ``${/path}`` in KiCad's library tables.

    Args:
        kicad_config: The KiCad configuration directory.
        backup_first: Back up each table before changing it.
        max_backups: The number of backups to keep per table.
        dry_run: Only report whether a table needs fixing.

    Returns:
        Whether a table had (or, in a dry run, has) wrapped paths.

    Raises:
        OSError: A table cannot be read, backed up, or written.
    """
    changes_made = False
    for table_path in (kicad_config / SYMBOL_TABLE, kicad_config / FOOTPRINT_TABLE):
        if not table_path.exists():
            continue
        content = table_path.read_text(encoding="utf-8")
        if _WRAPPED_URI.search(content) is None:
            continue
        changes_made = True
        if dry_run:
            continue
        if backup_first:
            create_backup(table_path, max_backups)
        fixed_content = _WRAPPED_URI.sub(r'(uri "\1/\2")', content)
        write_atomically(table_path, fixed_content.encode("utf-8"))
    return changes_made


def update_environment(options: ChangeOptions, env_vars: dict[str, str]) -> bool:
    """Set ``env_vars`` in KiCad and report the outcome.

    Returns:
        Whether variables changed (would change, in a dry run). A failure is
        reported and counts as no change, so setup continues.
    """
    console = get_console()
    try:
        changed = update_kicad_env_vars(
            options.kicad_config,
            env_vars,
            dry_run=options.dry_run,
            max_backups=options.max_backups,
        )
    except (OSError, ValueError) as e:
        console.print(f"[red]Error updating environment variables: {e}[/red]")
        return False

    if not changed:
        console.print(
            "[blue]Environment variables already up to date in KiCad "
            "configuration[/blue]"
        )
    elif options.dry_run:
        console.print(
            "[yellow]Would update environment variables in KiCad configuration[/yellow]"
        )
    else:
        console.print(
            "[green]Updated environment variables in KiCad configuration[/green]"
        )
        console.print("[blue]Created backup of kicad_common.json[/blue]")
        console.print("\n[bold cyan]Environment variables set in KiCad:[/bold cyan]")
        for name, value in env_vars.items():
            console.print(f"  [cyan]{name}[/cyan] = [blue]{value}[/blue]")
    return changed


def add_libraries(options: ChangeOptions, libraries: SetupLibraries) -> bool:
    """Add the libraries to KiCad's library tables and report the outcome.

    The tables are backed up first, and only when they will change.

    Returns:
        Whether the tables changed (would change, in a dry run).
    """
    console = get_console()
    # Plan first: the backup must hold the tables from before the change.
    added, changed = _add_libraries(options, libraries, dry_run=True)
    if changed and not options.dry_run:
        for table, name in ((SYMBOL_TABLE, "symbol"), (FOOTPRINT_TABLE, "footprint")):
            table_path = options.kicad_config / table
            if table_path.exists():
                create_backup(table_path, options.max_backups)
                console.print(f"[blue]Created backup of {name} library table[/blue]")
        added, changed = _add_libraries(options, libraries, dry_run=False)

    if not added:
        console.print("[blue]No new libraries to add[/blue]")
    elif options.dry_run:
        console.print(
            f"[yellow]Would add {len(added)} libraries to KiCad configuration[/yellow]"
        )
    else:
        console.print(
            f"[green]Added {len(added)} libraries to KiCad configuration[/green]"
        )
    return changed


def _add_libraries(
    options: ChangeOptions, libraries: SetupLibraries, *, dry_run: bool
) -> tuple[set[str], bool]:
    """Add (or plan to add) the libraries; return the names and whether needed."""
    return LibraryService.add_libraries(
        libraries.symbol_dir,
        options.kicad_config,
        kicad_3d_dir=libraries.models_dir,
        additional_3d_dirs=libraries.model_dirs(),
        dry_run=dry_run,
    )


def pin_libraries(options: ChangeOptions, symbol_dir: str) -> bool:
    """Pin every library in ``symbol_dir`` in KiCad and report the outcome.

    Returns:
        Whether the pins changed (would change, in a dry run). A failure is
        reported and counts as no change, so setup continues.
    """
    console = get_console()
    symbols: list[str] = []
    footprints: list[str] = []
    try:
        symbols, footprints = list_libraries(symbol_dir)
    except (OSError, ValueError) as e:
        console.print(f"[red]Error listing libraries to pin: {e}[/red]")
    else:
        if options.verbose:
            console.print(
                f"Found {len(symbols)} symbol libraries and {len(footprints)} "
                "footprint libraries to pin"
            )

    try:
        changed = update_pinned_libraries(
            options.kicad_config,
            symbol_libs=symbols,
            footprint_libs=footprints,
            dry_run=options.dry_run,
            max_backups=options.max_backups,
        )
    except (OSError, ValueError) as e:
        console.print(f"[red]Error pinning libraries: {e}[/red]")
        return False

    counts = f"{len(symbols)} symbol and {len(footprints)} footprint libraries"
    if not changed:
        console.print("[blue]All libraries already pinned in KiCad[/blue]")
    elif options.dry_run:
        console.print(f"[yellow]Would pin {counts} in KiCad[/yellow]")
    else:
        console.print(f"[green]Pinned {counts} in KiCad[/green]")
    return changed
