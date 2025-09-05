"""
Add Hook command implementation for KiCad Library Manager.
Adds a git post-merge hook to the current repository to automatically update KiCad libraries.
"""

from pathlib import Path

import click

from ...utils.git_utils import (
    backup_existing_hook,
    create_kilm_hook_content,
    get_git_hooks_directory,
    merge_hook_content,
)


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
    """Add a Git post-merge hook to automatically sync KiCad libraries.

    This command adds a Git post-merge hook to the specified repository
    (or the current directory if none specified) that automatically runs
    'kilm sync' after a 'git pull' or 'git merge' operation.

    This ensures your KiCad libraries are always up-to-date after pulling
    changes from remote repositories.
    """
    # Determine target directory
    target_dir = Path(directory) if directory else Path.cwd()

    click.echo(f"Adding Git hook to repository: {target_dir}")

    try:
        # Get the active hooks directory (handles custom paths, worktrees, etc.)
        hooks_dir = get_git_hooks_directory(target_dir)
        click.echo(f"Using hooks directory: {hooks_dir}")

    except RuntimeError as e:
        raise click.ClickException(f"Error: {e}") from e

    # Check if post-merge hook already exists
    post_merge_hook = hooks_dir / "post-merge"

    if post_merge_hook.exists():
        if not force:
            click.echo(f"Post-merge hook already exists at {post_merge_hook}")
            if not click.confirm("Overwrite existing hook?", default=False):
                click.echo("Hook installation cancelled.")
                return

        # Create backup of existing hook
        backup_path = backup_existing_hook(post_merge_hook)
        click.echo(f"Created backup of existing hook: {backup_path}")

        # Read existing content for potential merging
        try:
            existing_content = post_merge_hook.read_text(encoding="utf-8")

            if force:
                # Force overwrite - don't merge, just replace
                click.echo("Force overwrite requested, replacing existing hook...")
                new_content = create_kilm_hook_content()
            else:
                # Merge with existing content to preserve user logic
                click.echo("Merging KiLM content with existing hook...")
                new_content = merge_hook_content(
                    existing_content, create_kilm_hook_content()
                )

        except (OSError, UnicodeDecodeError):
            click.echo("Warning: Could not read existing hook content, overwriting...")
            new_content = create_kilm_hook_content()
    else:
        # No existing hook, create new one
        new_content = create_kilm_hook_content()

    try:
        # Write the hook content
        with post_merge_hook.open("w") as f:
            f.write(new_content)

        # Make the hook executable
        post_merge_hook.chmod(0o755)

        click.echo(f"Successfully installed post-merge hook at {post_merge_hook}")
        click.echo(
            "The hook will run 'kilm sync' after every 'git pull' or 'git merge' operation."
        )

        if post_merge_hook.exists() and "KiLM-managed section" in new_content:
            click.echo(
                "\nNote: The hook contains clear markers for KiLM-managed sections,"
            )
            click.echo("making future updates safe and idempotent.")

        click.echo(
            "\nNote: You may need to modify the hook script if you want to customize"
        )
        click.echo("the update behavior or automatically set up libraries.")

    except Exception as e:
        raise click.ClickException(f"Error creating hook: {str(e)}") from e
