"""
Update command implementation for KiCad Library Manager.
Performs 'git pull' on all configured GitHub libraries (symbols/footprints).
"""

import os
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
def update(dry_run, verbose):
    """Update all configured GitHub libraries with git pull.
    
    This command updates all configured GitHub libraries (symbols/footprints)
    by performing a 'git pull' operation in each library directory. 
    It will only attempt to update directories that are valid git repositories.
    
    After updating, you can use 'kilm setup' to configure any new libraries 
    that might have been added to the repositories.
    """
    config = Config()
    
    # Get GitHub libraries from config (symbols/footprints)
    libraries = config.get_libraries(library_type="github")
    
    if not libraries:
        click.echo("No GitHub libraries configured. Use 'kilm init' to add a library.")
        return
    
    click.echo(f"Updating {len(libraries)} KiCad GitHub libraries...")
    
    updated_count = 0
    skipped_count = 0
    failed_count = 0
    
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
                    status = "Updated" if is_updated else "Up to date"
                    click.echo(f"    {status}")
                updated_count += 1
            else:
                click.echo(f"    Failed: {result.stderr.strip()}")
                failed_count += 1
                
        except Exception as e:
            click.echo(f"    Error: {str(e)}")
            failed_count += 1
    
    # Summary
    click.echo("\nUpdate Summary:")
    click.echo(f"  {updated_count} libraries updated")
    click.echo(f"  {skipped_count} libraries skipped")
    click.echo(f"  {failed_count} libraries failed")
    
    click.echo("\nUse 'kilm status' to check your current configuration.")
    click.echo("Use 'kilm setup' to configure any new libraries in KiCad.")