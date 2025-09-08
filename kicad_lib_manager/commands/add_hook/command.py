"""
Add Hook command implementation for KiCad Library Manager.
Adds a git post-merge hook to the current repository to automatically update KiCad libraries.
"""

from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console

from ...utils.git_utils import (
    backup_existing_hook,
    create_kilm_hook_content,
    get_git_hooks_directory,
    merge_hook_content,
)

console = Console()


def add_hook(
    directory: Annotated[
        Optional[Path],
        typer.Option(
            help="Target git repository directory (defaults to current directory)"
        ),
    ] = None,
    force: Annotated[
        bool, typer.Option(help="Overwrite existing hook if present")
    ] = False,
) -> None:
    """Add a Git post-merge hook to automatically sync KiCad libraries.

    This command adds a Git post-merge hook to the specified repository
    (or the current directory if none specified) that automatically runs
    'kilm sync' after a 'git pull' or 'git merge' operation.

    This ensures your KiCad libraries are always up-to-date after pulling
    changes from remote repositories.
    """
    try:
        # Determine target directory
        target_dir = directory if directory else Path.cwd()

        console.print(f"[cyan]Adding Git hook to repository: {target_dir}[/cyan]")

        try:
            # Get the active hooks directory (handles custom paths, worktrees, etc.)
            hooks_dir = get_git_hooks_directory(target_dir)
            console.print(f"[blue]Using hooks directory: {hooks_dir}[/blue]")

        except RuntimeError as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1) from e

        # Check if post-merge hook already exists
        post_merge_hook = hooks_dir / "post-merge"

        if post_merge_hook.exists():
            if not force:
                console.print(
                    f"[yellow]Post-merge hook already exists at {post_merge_hook}[/yellow]"
                )
                overwrite = typer.confirm("Overwrite existing hook?", default=False)
                if not overwrite:
                    console.print("[yellow]Hook installation cancelled.[/yellow]")
                    return

            # Create backup of existing hook
            backup_path = backup_existing_hook(post_merge_hook)
            console.print(
                f"[green]Created backup of existing hook: {backup_path}[/green]"
            )

            # Read existing content for potential merging
            try:
                existing_content = post_merge_hook.read_text(encoding="utf-8")

                if force:
                    # Force overwrite - don't merge, just replace
                    console.print(
                        "[yellow]Force overwrite requested, replacing existing hook...[/yellow]"
                    )
                    new_content = create_kilm_hook_content()
                else:
                    # Merge with existing content to preserve user logic
                    console.print(
                        "[cyan]Merging KiLM content with existing hook...[/cyan]"
                    )
                    new_content = merge_hook_content(
                        existing_content, create_kilm_hook_content()
                    )

            except (OSError, UnicodeDecodeError):
                console.print(
                    "[yellow]Warning: Could not read existing hook content, overwriting...[/yellow]"
                )
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

            console.print(
                f"[green]Successfully installed post-merge hook at {post_merge_hook}[/green]"
            )
            console.print(
                "[blue]The hook will run 'kilm sync' after every 'git pull' or 'git merge' operation.[/blue]"
            )

            if post_merge_hook.exists() and "KiLM-managed section" in new_content:
                console.print(
                    "\n[cyan]Note: The hook contains clear markers for KiLM-managed sections,[/cyan]"
                )
                console.print("[cyan]making future updates safe and idempotent.[/cyan]")

            console.print(
                "\n[blue]Note: You may need to modify the hook script if you want to customize[/blue]"
            )
            console.print(
                "[blue]the update behavior or automatically set up libraries.[/blue]"
            )

        except Exception as e:
            console.print(f"[red]Error creating hook: {str(e)}[/red]")
            raise typer.Exit(1) from e

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from e
