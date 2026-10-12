"""The ``add-hook`` command: run ``kilm sync`` after every git pull or merge.

The command installs a git ``post-merge`` hook. An existing hook is backed up
and, unless ``--force`` is given, keeps its own commands next to the KiLM
section.
"""

from pathlib import Path
from typing import Annotated

import typer

from kicad_lib_manager.utils.console import get_console
from kicad_lib_manager.utils.file_ops import write_atomically
from kicad_lib_manager.utils.git_utils import (
    backup_existing_hook,
    create_kilm_hook_content,
    get_git_hooks_directory,
    merge_hook_content,
)

HOOK_NAME = "post-merge"
MANAGED_SECTION_MARKER = "KiLM-managed section"


def _hooks_directory(repository: Path) -> Path:
    """Return the hooks directory git uses for ``repository``; exit if none."""
    try:
        hooks_dir = get_git_hooks_directory(repository)
    except RuntimeError as e:
        get_console().print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from e
    get_console().print(f"[blue]Using hooks directory: {hooks_dir}[/blue]")
    return hooks_dir


def _content_replacing(hook: Path, *, force: bool) -> str | None:
    """Back up the existing ``hook`` and return the content to replace it with.

    Without ``force`` the user must confirm, and the existing commands are
    kept around the KiLM section. Returns None when the user declines.
    """
    console = get_console()
    if not force:
        console.print(f"[yellow]Post-merge hook already exists at {hook}[/yellow]")
        if not typer.confirm("Overwrite existing hook?", default=False):
            console.print("[yellow]Hook installation cancelled.[/yellow]")
            return None

    backup_path = backup_existing_hook(hook)
    console.print(f"[green]Created backup of existing hook: {backup_path}[/green]")
    try:
        existing_content = hook.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        console.print(
            "[yellow]Warning: Could not read existing hook content, "
            "overwriting...[/yellow]"
        )
        return create_kilm_hook_content()
    if force:
        console.print(
            "[yellow]Force overwrite requested, replacing existing hook...[/yellow]"
        )
        return create_kilm_hook_content()
    console.print("[cyan]Merging KiLM content with existing hook...[/cyan]")
    return merge_hook_content(existing_content, create_kilm_hook_content())


def _install(hook: Path, content: str) -> None:
    """Write ``content`` to ``hook``, make it executable, and explain it."""
    console = get_console()
    try:
        # Bytes, because text mode would give the shell script CRLF endings on
        # Windows.
        write_atomically(hook, content.encode("utf-8"))
        hook.chmod(0o755)
    except Exception as e:
        console.print(f"[red]Error creating hook: {e!s}[/red]")
        raise typer.Exit(1) from e

    console.print(f"[green]Successfully installed post-merge hook at {hook}[/green]")
    console.print(
        "[blue]The hook will run 'kilm sync' after every 'git pull' or "
        "'git merge' operation.[/blue]"
    )
    if MANAGED_SECTION_MARKER in content:
        console.print(
            "\n[cyan]Note: The hook contains clear markers for KiLM-managed "
            "sections,[/cyan]"
        )
        console.print("[cyan]making future updates safe and idempotent.[/cyan]")
    console.print(
        "\n[blue]Note: You may need to modify the hook script if you want to "
        "customize[/blue]"
    )
    console.print("[blue]the update behavior or automatically set up libraries.[/blue]")


def add_hook(
    *,
    directory: Annotated[
        Path | None,
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
    target_dir = Path.cwd() if directory is None else directory
    get_console().print(f"[cyan]Adding Git hook to repository: {target_dir}[/cyan]")
    hook = _hooks_directory(target_dir) / HOOK_NAME

    if not hook.exists():
        content = create_kilm_hook_content()
    else:
        try:
            content = _content_replacing(hook, force=force)
        except Exception as e:
            get_console().print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1) from e
        if content is None:
            return
    _install(hook, content)
