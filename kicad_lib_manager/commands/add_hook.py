"""
Add Hook command implementation for KiCad Library Manager.
Adds a git post-merge hook to the current repository to automatically update KiCad libraries.
"""

import os
import click
from pathlib import Path


@click.command()
@click.option(
    "--directory",
    help="Target git repository directory (defaults to current directory)",
    default=None,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, resolve_path=True),
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Overwrite existing hook if present",
    show_default=True,
)
def add_hook(directory, force):
    """Add a Git post-merge hook to automatically update KiCad libraries.
    
    This command adds a Git post-merge hook to the specified repository
    (or the current directory if none specified) that automatically runs
    'kilm update' after a 'git pull' or 'git merge' operation.
    
    This ensures your KiCad libraries are always up-to-date after pulling
    changes from remote repositories.
    """
    # Determine target directory
    if directory:
        target_dir = Path(directory)
    else:
        target_dir = Path.cwd()
    
    click.echo(f"Adding Git hook to repository: {target_dir}")
    
    # Check if this is a git repository
    git_dir = target_dir / ".git"
    if not git_dir.exists() or not git_dir.is_dir():
        click.echo(f"Error: {target_dir} is not a git repository", err=True)
        return
    
    # Check if hooks directory exists, create if not
    hooks_dir = git_dir / "hooks"
    if not hooks_dir.exists():
        os.makedirs(hooks_dir, exist_ok=True)
        click.echo(f"Created hooks directory: {hooks_dir}")
    
    # Check if post-merge hook already exists
    post_merge_hook = hooks_dir / "post-merge"
    
    if post_merge_hook.exists() and not force:
        click.echo(f"Post-merge hook already exists at {post_merge_hook}")
        if not click.confirm("Overwrite existing hook?", default=False):
            click.echo("Hook installation cancelled.")
            return
    
    # Create the post-merge hook script
    hook_content = """#!/bin/sh
# KiCad Library Manager auto-update hook
# Added by kilm add-hook command

echo "Running KiCad Library Manager update..."
kilm update

# Uncomment to set up libraries automatically (use with caution)
# kilm setup

echo "KiCad libraries update complete."
"""
    
    try:
        with open(post_merge_hook, "w") as f:
            f.write(hook_content)
        
        # Make the hook executable
        os.chmod(post_merge_hook, 0o755)
        
        click.echo(f"Successfully installed post-merge hook at {post_merge_hook}")
        click.echo("The hook will run 'kilm update' after every 'git pull' or 'git merge' operation.")
        click.echo("\nNote: You may need to modify the hook script if you want to customize")
        click.echo("the update behavior or automatically set up libraries.")
        
    except Exception as e:
        click.echo(f"Error creating hook: {str(e)}", err=True) 