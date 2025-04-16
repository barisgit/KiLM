"""
Update command implementation for KiCad Library Manager.
Performs 'git pull' on all configured GitHub libraries (symbols/footprints).
"""

import os
import re
import subprocess
import click
from pathlib import Path

from ..config import Config


@click.command()
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Show what would be updated without making changes",
    show_default=True,
)
@click.option(
    "--verbose",
    is_flag=True,
    default=False,
    help="Show detailed output",
    show_default=True,
)
@click.option(
    "--auto-setup",
    is_flag=True,
    default=False,
    help="Run 'kilm setup' automatically if new libraries are detected",
    show_default=True,
)
def update(dry_run, verbose, auto_setup):
    """Update all configured GitHub libraries with git pull.
    
    This command updates all configured GitHub libraries (symbols/footprints)
    by performing a 'git pull' operation in each library directory. 
    It will only attempt to update directories that are valid git repositories.
    
    After updating, the command will check if new libraries have been added
    and recommend running 'kilm setup' if needed. Use --auto-setup to run
    setup automatically when new libraries are detected.
    """
    config = Config()
    
    # Get GitHub libraries from config (symbols/footprints)
    libraries = config.get_libraries(library_type="github")
    
    if not libraries:
        click.echo("No GitHub libraries configured. Use 'kilm init' to add a library.")
        return
    
    click.echo(f"Updating {len(libraries)} KiCad GitHub libraries...")
    
    updated_count = 0  # Actually changed
    up_to_date_count = 0  # Already at latest version
    skipped_count = 0  # Could not update (not git, etc.)
    failed_count = 0  # Git pull failed
    
    # Track libraries that have changes that might require setup
    libraries_with_changes = []
    
    for lib in libraries:
        lib_name = lib.get("name", "unnamed")
        lib_path = lib.get("path")
        
        if not lib_path:
            click.echo(f"  Skipping {lib_name}: No path defined")
            skipped_count += 1
            continue
        
        lib_path = Path(lib_path)
        if not lib_path.exists():
            click.echo(f"  Skipping {lib_name}: Path does not exist: {lib_path}")
            skipped_count += 1
            continue
        
        git_dir = lib_path / ".git"
        if not git_dir.exists() or not git_dir.is_dir():
            click.echo(f"  Skipping {lib_name}: Not a git repository: {lib_path}")
            skipped_count += 1
            continue
        
        # Prepare to run git pull
        click.echo(f"  Updating {lib_name} at {lib_path}...")
        
        if dry_run:
            click.echo(f"    Dry run: would execute 'git pull' in {lib_path}")
            updated_count += 1
            continue
            
        try:
            # Run git pull
            result = subprocess.run(
                ["git", "pull"],
                cwd=lib_path,
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                output = result.stdout.strip() or 'Already up to date.'
                if verbose:
                    click.echo(f"    Success: {output}")
                else:
                    is_updated = "Already up to date" not in output
                    if is_updated:
                        click.echo(f"    Updated")
                        updated_count += 1
                    else:
                        click.echo(f"    Up to date")
                        up_to_date_count += 1
                
                # Check if there are new library files that would require setup
                if "Already up to date" not in output:
                    changes_require_setup = check_for_library_changes(result.stdout, lib_path)
                    if changes_require_setup:
                        libraries_with_changes.append((lib_name, lib_path, changes_require_setup))
                        if verbose:
                            click.echo(f"    Detected new library content: {', '.join(changes_require_setup)}")
            else:
                click.echo(f"    Failed: {result.stderr.strip()}")
                failed_count += 1
                
        except Exception as e:
            click.echo(f"    Error: {str(e)}")
            failed_count += 1
    
    # Summary
    click.echo("\nUpdate Summary:")
    click.echo(f"  {updated_count} libraries updated")
    click.echo(f"  {up_to_date_count} libraries up to date")
    click.echo(f"  {skipped_count} libraries skipped")
    click.echo(f"  {failed_count} libraries failed")
    
    # If libraries with changes were detected, suggest running setup
    if libraries_with_changes:
        click.echo("\nNew library content detected in:")
        for lib_name, lib_path, changes in libraries_with_changes:
            click.echo(f"  - {lib_name}: {', '.join(changes)}")
        
        if auto_setup:
            click.echo("\nRunning 'kilm setup' to configure new libraries...")
            # Import at runtime to avoid circular imports
            try:
                from .setup import setup as setup_cmd
                ctx = click.Context(setup_cmd)
                setup_cmd.invoke(ctx)
            except ImportError:
                click.echo("Error: Could not import setup command. Please run 'kilm setup' manually.")
        else:
            click.echo("\nYou should run 'kilm setup' to configure the new libraries in KiCad.")
            click.echo("Run 'kilm update --auto-setup' next time to automatically run setup after updates.")
    else:
        click.echo("\nNo new libraries detected that would require running 'kilm setup'.")
        click.echo("Use 'kilm status' to check your current configuration.")


def check_for_library_changes(git_output, lib_path):
    """
    Check if git pull output and filesystem changes indicate new libraries that would require setup.
    
    Args:
        git_output: Output from git pull command
        lib_path: Path to the library directory
        
    Returns:
        List of change types found ('symbols', 'footprints', 'templates') or empty list if none
    """
    changes = []
    
    # Check git output for new files in key directories
    pattern = r"[^\s]+\s+\|\s+\d+ [+]+(?:-+)?\s+(?:symbols|footprints|templates|3d)"
    if re.search(pattern, git_output, re.IGNORECASE):
        # This is a basic heuristic that indicates changes in library directories
        # For more accuracy, we'll check the actual directories
        pass
    
    # Check for specific library file types
    symbols_path = lib_path / "symbols"
    footprints_path = lib_path / "footprints"
    templates_path = lib_path / "templates"
    
    # Look for symbol libraries (.kicad_sym files)
    if symbols_path.exists() and symbols_path.is_dir():
        if any(f.name.endswith(".kicad_sym") for f in symbols_path.glob("**/*.kicad_sym")):
            changes.append("symbols")
    
    # Look for footprint libraries (.pretty directories)
    if footprints_path.exists() and footprints_path.is_dir():
        if any(f.is_dir() and f.name.endswith(".pretty") for f in footprints_path.glob("**/*.pretty")):
            changes.append("footprints")
    
    # Look for project templates (directories with metadata.yaml)
    if templates_path.exists() and templates_path.is_dir():
        if any((f / "metadata.yaml").exists() for f in templates_path.glob("*") if f.is_dir()):
            changes.append("templates")
    
    return changes