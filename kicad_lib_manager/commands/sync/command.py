"""
Sync command implementation for KiCad Library Manager.
Performs 'git pull' on all configured GitHub libraries (symbols/footprints).
"""

import subprocess
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from ...services.config_service import Config

console = Console()


def sync(
    dry_run: Annotated[
        bool, typer.Option(help="Show what would be synced without making changes")
    ] = False,
    verbose: Annotated[bool, typer.Option(help="Show detailed output")] = False,
    auto_setup: Annotated[
        bool,
        typer.Option(
            help="Run 'kilm setup' automatically if new libraries are detected"
        ),
    ] = False,
) -> None:
    """Sync all configured GitHub libraries with git pull.

    This command syncs all configured GitHub libraries (symbols/footprints)
    by performing a 'git pull' operation in each library directory.
    It will only attempt to sync directories that are valid git repositories.

    After syncing, the command will check if new libraries have been added
    and recommend running 'kilm setup' if needed. Use --auto-setup to run
    setup automatically when new libraries are detected.
    """
    try:
        config = Config()

        # Get GitHub libraries from config (symbols/footprints)
        libraries = config.get_libraries(library_type="github")

        if not libraries:
            console.print(
                "[yellow]No GitHub libraries configured. Use 'kilm init' to add a library.[/yellow]"
            )
            return

        console.print(
            f"[cyan]Syncing {len(libraries)} KiCad GitHub libraries...[/cyan]"
        )

        updated_count = 0  # Actually changed
        up_to_date_count = 0  # Already at latest version
        skipped_count = 0  # Could not sync (not git, etc.)
        failed_count = 0  # Git pull failed

        # Track libraries that have changes that might require setup
        libraries_with_changes: list[tuple[str, Path, list[str]]] = []

        for lib in libraries:
            lib_name = lib.get("name", "unnamed")
            lib_path = lib.get("path")

            if not lib_path:
                console.print(
                    f"  [yellow]Skipping {lib_name}: No path defined[/yellow]"
                )
                skipped_count += 1
                continue

            lib_path = Path(lib_path)
            if not lib_path.exists():
                console.print(
                    f"  [yellow]Skipping {lib_name}: Path does not exist: {lib_path}[/yellow]"
                )
                skipped_count += 1
                continue

            git_dir = lib_path / ".git"
            if not git_dir.exists() or not git_dir.is_dir():
                console.print(
                    f"  [yellow]Skipping {lib_name}: Not a git repository: {lib_path}[/yellow]"
                )
                skipped_count += 1
                continue

            # Prepare to run git pull
            console.print(f"  [cyan]Syncing {lib_name} at {lib_path}...[/cyan]")

            if dry_run:
                console.print(
                    f"    [blue]Dry run: would execute 'git pull' in {lib_path}[/blue]"
                )
                updated_count += 1
                continue

            try:
                # Run git pull
                result = subprocess.run(
                    ["git", "pull"],
                    cwd=lib_path,
                    capture_output=True,
                    text=True,
                    check=False,
                )

                if result.returncode == 0:
                    output = result.stdout.strip() or "Already up to date."
                    is_updated = "Already up to date" not in output

                    if verbose:
                        console.print(f"    [green]Success: {output}[/green]")
                        # Also show the short status for consistency
                        if is_updated:
                            console.print("    [green]Updated[/green]")
                        else:
                            console.print("    [blue]Up to date[/blue]")
                    else:
                        if is_updated:
                            console.print("    [green]Updated[/green]")
                        else:
                            console.print("    [blue]Up to date[/blue]")

                    # Update counters regardless of verbose flag
                    if is_updated:
                        updated_count += 1
                    else:
                        up_to_date_count += 1

                    # Check if there are new library files that would require setup
                    if is_updated:
                        changes_require_setup = check_for_library_changes(lib_path)
                        if changes_require_setup:
                            libraries_with_changes.append(
                                (lib_name, lib_path, changes_require_setup)
                            )
                            if verbose:
                                console.print(
                                    f"    [yellow]Detected new library content: {', '.join(changes_require_setup)}[/yellow]"
                                )
                else:
                    console.print(f"    [red]Failed: {result.stderr.strip()}[/red]")
                    failed_count += 1

            except Exception as e:
                console.print(f"    [red]Error: {str(e)}[/red]")
                failed_count += 1

        # Summary
        console.print("\n[bold cyan]Sync Summary:[/bold cyan]")
        console.print(f"  [green]{updated_count}[/green] libraries synced")
        console.print(f"  [blue]{up_to_date_count}[/blue] libraries up to date")
        console.print(f"  [yellow]{skipped_count}[/yellow] libraries skipped")
        console.print(f"  [red]{failed_count}[/red] libraries failed")

        # If libraries with changes were detected, suggest running setup
        if libraries_with_changes:
            console.print("\n[yellow]New library content detected in:[/yellow]")
            for lib_name, _lib_path, changes in libraries_with_changes:
                console.print(f"  - [cyan]{lib_name}[/cyan]: {', '.join(changes)}")

            if auto_setup:
                console.print(
                    "\n[green]Running 'kilm setup' to configure new libraries...[/green]"
                )
                # Import at runtime to avoid circular imports
                try:
                    from ...commands.setup.command import setup as setup_cmd

                    setup_cmd()
                except ImportError:
                    console.print(
                        "[red]Error: Could not import setup command. Please run 'kilm setup' manually.[/red]"
                    )
            else:
                console.print(
                    "\n[yellow]You should run 'kilm setup' to configure the new libraries in KiCad.[/yellow]"
                )
                console.print(
                    "[blue]Run 'kilm sync --auto-setup' next time to automatically run setup after sync.[/blue]"
                )
        else:
            console.print(
                "\n[blue]No new libraries detected that would require running 'kilm setup'.[/blue]"
            )
            console.print(
                "[blue]Use 'kilm status' to check your current configuration.[/blue]"
            )

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from e


# TODO: Should be in services or utils
def check_for_library_changes(lib_path: Path) -> list[str]:
    """
    Check if git pull changes indicate new libraries that would require setup.
    Uses git diff to analyze what files were added/changed in the pull.

    Args:
        lib_path: Path to the library directory

    Returns:
        List of change types found ('symbols', 'footprints', 'templates') or empty list if none
    """
    changes = []

    try:
        # Get the diff between HEAD~1 and HEAD to see what changed in the pull
        result = subprocess.run(
            ["git", "diff", "--name-status", "HEAD~1", "HEAD"],
            cwd=lib_path,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            # If we can't get the diff (e.g., first commit), fall back to checking current state
            return _check_current_library_state(lib_path)

        diff_output = result.stdout.strip()
        if not diff_output:
            return changes

        # Parse the diff output to find relevant changes
        for line in diff_output.split("\n"):
            if not line.strip():
                continue

            # Parse git diff --name-status format: STATUS\tPATH
            parts = line.split("\t", 1)
            if len(parts) != 2:
                continue

            status, path = parts
            # Only consider added (A) or modified (M) files, ignore deletions
            if status not in ["A", "M", "R"]:
                continue

            # Check for symbol library changes
            if _is_symbol_library_change(path) and "symbols" not in changes:
                changes.append("symbols")

            # Check for footprint library changes
            if _is_footprint_library_change(path) and "footprints" not in changes:
                changes.append("footprints")

            # Check for template changes
            if _is_template_change(path) and "templates" not in changes:
                changes.append("templates")

    except Exception:
        # If git diff fails, fall back to checking current state
        return _check_current_library_state(lib_path)

    return changes


def _is_symbol_library_change(path: str) -> bool:
    """Check if a path change indicates a symbol library change."""
    # Look for .kicad_sym files in symbols directory
    return path.startswith("symbols/") and path.endswith(".kicad_sym")


def _is_footprint_library_change(path: str) -> bool:
    """Check if a path change indicates a footprint library change."""
    # Look for .pretty directories or files within them
    return (path.startswith("footprints/") and path.endswith(".pretty")) or (
        path.startswith("footprints/") and ".pretty/" in path
    )


def _is_template_change(path: str) -> bool:
    """Check if a path change indicates a template change."""
    # Look for metadata.yaml files in template directories
    return path.startswith("templates/") and path.endswith("metadata.yaml")


def _check_current_library_state(lib_path: Path) -> list[str]:
    """
    Fallback method to check current library state when git diff is not available.
    This is used when we can't determine what changed in the pull.
    """
    changes = []

    # Check for symbol libraries (.kicad_sym files)
    symbols_path = lib_path / "symbols"
    if (
        symbols_path.exists()
        and symbols_path.is_dir()
        and any(
            f.name.endswith(".kicad_sym") for f in symbols_path.glob("**/*.kicad_sym")
        )
    ):
        changes.append("symbols")

    # Check for footprint libraries (.pretty directories)
    footprints_path = lib_path / "footprints"
    if (
        footprints_path.exists()
        and footprints_path.is_dir()
        and any(
            f.is_dir() and f.name.endswith(".pretty")
            for f in footprints_path.glob("**/*.pretty")
        )
    ):
        changes.append("footprints")

    # Check for project templates (directories with metadata.yaml)
    templates_path = lib_path / "templates"
    if (
        templates_path.exists()
        and templates_path.is_dir()
        and any(
            (f / "metadata.yaml").exists()
            for f in templates_path.glob("*")
            if f.is_dir()
        )
    ):
        changes.append("templates")

    return changes
