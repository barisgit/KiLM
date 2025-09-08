"""
Unpin command implementation for KiCad Library Manager (Typer version).
"""

import json
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from ...services.library_service import LibraryService
from ...utils.backup import create_backup

console = Console()


def unpin(
    symbols: Optional[list[str]] = typer.Option(
        None,
        "--symbols",
        "-s",
        help="Symbol libraries to unpin (can be specified multiple times)",
    ),
    footprints: Optional[list[str]] = typer.Option(
        None,
        "--footprints",
        "-f",
        help="Footprint libraries to unpin (can be specified multiple times)",
    ),
    all_libraries: bool = typer.Option(False, "--all", help="Unpin all libraries"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be done without making changes"
    ),
    max_backups: int = typer.Option(
        5, "--max-backups", help="Maximum number of backups to keep"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show verbose output for debugging"
    ),
) -> None:
    """Unpin libraries in KiCad"""
    # Handle None values from optional parameters
    symbols = symbols or []
    footprints = footprints or []

    # Enforce mutual exclusivity of --all with --symbols/--footprints
    if all_libraries and (symbols or footprints):
        console.print(
            "[red]Error: '--all' cannot be used with '--symbols' or '--footprints'[/red]"
        )
        raise typer.Exit(1)

    # Find KiCad configuration
    try:
        kicad_config = LibraryService.find_kicad_config()
        if verbose:
            console.print(f"Found KiCad configuration at: [blue]{kicad_config}[/blue]")
    except Exception as e:
        console.print(f"[red]Error finding KiCad configuration: {e}[/red]")
        raise typer.Exit(1) from e

    # Get the kicad_common.json file
    kicad_common = kicad_config / "kicad_common.json"
    if not kicad_common.exists():
        console.print(
            "[yellow]KiCad common configuration file not found, nothing to unpin[/yellow]"
        )
        return

    # If --all is specified, unpin all libraries
    if all_libraries:
        try:
            with kicad_common.open() as f:
                config = json.load(f)

            # Get all pinned libraries from kicad_common.json
            if "session" in config:
                symbols = config["session"].get("pinned_symbol_libs", [])
                footprints = config["session"].get("pinned_fp_libs", [])

                if verbose:
                    if symbols:
                        console.print(
                            f"Found [cyan]{len(symbols)}[/cyan] pinned symbol libraries"
                        )
                    if footprints:
                        console.print(
                            f"Found [cyan]{len(footprints)}[/cyan] pinned footprint libraries"
                        )
            else:
                console.print(
                    "[yellow]No session information found in KiCad configuration, nothing to unpin[/yellow]"
                )
                return

            if not symbols and not footprints:
                console.print(
                    "[yellow]No pinned libraries found, nothing to unpin[/yellow]"
                )
                return
        except Exception as e:
            console.print(f"[red]Error reading pinned libraries: {e}[/red]")
            raise typer.Exit(1) from e

    # If no libraries are specified, print an error
    if not symbols and not footprints and not all_libraries:
        console.print("[red]Error: No libraries specified to unpin[/red]")
        console.print(
            "[yellow]Use --symbols, --footprints, or --all to specify libraries to unpin[/yellow]"
        )
        raise typer.Exit(1)

    # Ensure we have lists (Typer already handles this)
    symbols = symbols or []
    footprints = footprints or []

    # Unpin the libraries by removing them from the kicad_common.json file
    try:
        with kicad_common.open() as f:
            config = json.load(f)

        changes_needed = False

        # Ensure session section exists
        if "session" not in config:
            console.print(
                "[yellow]No session information found in KiCad configuration, nothing to unpin[/yellow]"
            )
            return

        # Handle symbol libraries
        if "pinned_symbol_libs" in config["session"] and symbols:
            current_symbols = config["session"]["pinned_symbol_libs"]
            new_symbols = [lib for lib in current_symbols if lib not in symbols]

            if len(new_symbols) != len(current_symbols):
                changes_needed = True
                if not dry_run:
                    config["session"]["pinned_symbol_libs"] = new_symbols

        # Handle footprint libraries
        if "pinned_fp_libs" in config["session"] and footprints:
            current_footprints = config["session"]["pinned_fp_libs"]
            new_footprints = [
                lib for lib in current_footprints if lib not in footprints
            ]

            if len(new_footprints) != len(current_footprints):
                changes_needed = True
                if not dry_run:
                    config["session"]["pinned_fp_libs"] = new_footprints

        # Write changes if needed
        if changes_needed and not dry_run:
            # Create backup before making changes
            create_backup(kicad_common, max_backups)

            with kicad_common.open("w") as f:
                json.dump(config, f, indent=2)

        if changes_needed:
            if dry_run:
                console.print(
                    f"[yellow]Would unpin {len(symbols) if symbols else 0} symbol and {len(footprints) if footprints else 0} footprint libraries in KiCad[/yellow]"
                )
            else:
                success_msg = f"[green]Unpinned {len(symbols) if symbols else 0} symbol and {len(footprints) if footprints else 0} footprint libraries in KiCad[/green]"
                console.print(
                    Panel(
                        f"{success_msg}\n\n"
                        f"[blue]• Created backup of kicad_common.json[/blue]\n"
                        f"[yellow]• Restart KiCad for changes to take effect[/yellow]",
                        title="✅ Libraries Unpinned",
                        border_style="green",
                    )
                )
        else:
            console.print(
                "[yellow]No changes needed, libraries already unpinned in KiCad[/yellow]"
            )

        if verbose:
            if symbols:
                console.print("\n[bold cyan]Unpinned Symbol Libraries:[/bold cyan]")
                for symbol in sorted(symbols):
                    console.print(f"  • [cyan]{symbol}[/cyan]")

            if footprints:
                console.print("\n[bold cyan]Unpinned Footprint Libraries:[/bold cyan]")
                for footprint in sorted(footprints):
                    console.print(f"  • [cyan]{footprint}[/cyan]")

    except Exception as e:
        console.print(f"[red]Error unpinning libraries: {e}[/red]")
        raise typer.Exit(1) from e
