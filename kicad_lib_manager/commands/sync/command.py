"""The ``sync`` command: ``git pull`` every configured GitHub library.

After pulling, sync reports libraries whose new commits add symbol,
footprint, or template content, since KiCad only sees those after
``kilm setup``.
"""

import shutil
import subprocess
from collections import Counter
from enum import Enum
from pathlib import Path
from typing import Annotated

import typer

from kicad_lib_manager.commands.setup.command import setup
from kicad_lib_manager.services.config_service import Config, LibraryDict
from kicad_lib_manager.utils.console import get_console


class _Outcome(Enum):
    """What syncing one library did."""

    UPDATED = "updated"
    UP_TO_DATE = "up to date"
    SKIPPED = "skipped"
    FAILED = "failed"


NewContent = list[tuple[str, list[str]]]


def _run_git(repository: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run git with ``args`` in ``repository`` and capture its text output.

    Raises:
        FileNotFoundError: git is not installed.
    """
    git = shutil.which("git")
    if git is None:
        msg = "git executable not found"
        raise FileNotFoundError(msg)
    return subprocess.run(  # noqa: S603 -- fixed git subcommands; the variable parts are revisions
        [git, *args],
        cwd=repository,
        capture_output=True,
        text=True,
        check=False,
    )


def _head_revision(repository: Path) -> str | None:
    """Return the commit HEAD points at, or None when git cannot tell."""
    result = _run_git(repository, "rev-parse", "--verify", "--quiet", "HEAD")
    revision = result.stdout.strip()
    return revision if result.returncode == 0 and revision else None


def _skip_reason(path: Path) -> str | None:
    """Return why ``path`` cannot be pulled, or None when it is a git clone."""
    if not path.exists():
        return f"Path does not exist: {path}"
    if not (path / ".git").is_dir():
        return f"Not a git repository: {path}"
    return None


def _pull(path: Path, *, verbose: bool) -> tuple[_Outcome, list[str]]:
    """Pull one library and return the outcome and any new content kinds."""
    console = get_console()
    revision_before_pull = _head_revision(path)
    result = _run_git(path, "pull")
    if result.returncode != 0:
        console.print(f"    [red]Failed: {result.stderr.strip()}[/red]")
        return _Outcome.FAILED, []

    # git words its messages in the user's language; HEAD is exact.
    updated = _head_revision(path) != revision_before_pull
    if verbose:
        output = result.stdout.strip() or "Already up to date."
        console.print(f"    [green]Success: {output}[/green]")
    if not updated:
        console.print("    [blue]Up to date[/blue]")
        return _Outcome.UP_TO_DATE, []

    console.print("    [green]Updated[/green]")
    new_content = check_for_library_changes(path, revision_before_pull or "HEAD~1")
    if verbose and new_content:
        console.print(
            "    [yellow]Detected new library content: "
            f"{', '.join(new_content)}[/yellow]"
        )
    return _Outcome.UPDATED, new_content


def _sync_library(
    library: LibraryDict, *, dry_run: bool, verbose: bool
) -> tuple[_Outcome, list[str]]:
    """Sync one configured library and return the outcome and new content."""
    console = get_console()
    name = library.get("name", "unnamed")
    configured_path = library.get("path")
    if not configured_path:
        console.print(f"  [yellow]Skipping {name}: No path defined[/yellow]")
        return _Outcome.SKIPPED, []
    path = Path(configured_path)
    reason = _skip_reason(path)
    if reason is not None:
        console.print(f"  [yellow]Skipping {name}: {reason}[/yellow]")
        return _Outcome.SKIPPED, []

    console.print(f"  [cyan]Syncing {name} at {path}...[/cyan]")
    if dry_run:
        console.print(f"    [blue]Dry run: would execute 'git pull' in {path}[/blue]")
        return _Outcome.UPDATED, []
    try:
        return _pull(path, verbose=verbose)
    except (OSError, subprocess.SubprocessError) as e:
        console.print(f"    [red]Error: {e!s}[/red]")
        return _Outcome.FAILED, []


def _sync_all(
    libraries: list[LibraryDict], *, dry_run: bool, verbose: bool
) -> tuple[Counter[_Outcome], NewContent]:
    """Sync every library; return the outcome counts and the new content."""
    outcomes: Counter[_Outcome] = Counter()
    new_content: NewContent = []
    for library in libraries:
        outcome, kinds = _sync_library(library, dry_run=dry_run, verbose=verbose)
        outcomes[outcome] += 1
        if kinds:
            new_content.append((library.get("name", "unnamed"), kinds))
    return outcomes, new_content


def _print_summary(outcomes: Counter[_Outcome]) -> None:
    """Print how many libraries ended in each outcome."""
    console = get_console()
    console.print("\n[bold cyan]Sync Summary:[/bold cyan]")
    console.print(f"  [green]{outcomes[_Outcome.UPDATED]}[/green] libraries synced")
    console.print(
        f"  [blue]{outcomes[_Outcome.UP_TO_DATE]}[/blue] libraries up to date"
    )
    console.print(f"  [yellow]{outcomes[_Outcome.SKIPPED]}[/yellow] libraries skipped")
    console.print(f"  [red]{outcomes[_Outcome.FAILED]}[/red] libraries failed")


def _report_new_content(new_content: NewContent, *, auto_setup: bool) -> None:
    """Report new library content, running setup when ``auto_setup`` is set."""
    console = get_console()
    if not new_content:
        console.print(
            "\n[blue]No new libraries detected that would require running "
            "'kilm setup'.[/blue]"
        )
        console.print(
            "[blue]Use 'kilm status' to check your current configuration.[/blue]"
        )
        return

    console.print("\n[yellow]New library content detected in:[/yellow]")
    for name, kinds in new_content:
        console.print(f"  - [cyan]{name}[/cyan]: {', '.join(kinds)}")
    if auto_setup:
        console.print(
            "\n[green]Running 'kilm setup' to configure new libraries...[/green]"
        )
        setup()
        return
    console.print(
        "\n[yellow]You should run 'kilm setup' to configure the new libraries "
        "in KiCad.[/yellow]"
    )
    console.print(
        "[blue]Run 'kilm sync --auto-setup' next time to automatically run "
        "setup after sync.[/blue]"
    )


def sync(
    *,
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
    console = get_console()
    try:
        libraries = Config().get_libraries(library_type="github")
        if not libraries:
            console.print(
                "[yellow]No GitHub libraries configured. Use 'kilm init' to add a "
                "library.[/yellow]"
            )
            return
        console.print(
            f"[cyan]Syncing {len(libraries)} KiCad GitHub libraries...[/cyan]"
        )
        outcomes, new_content = _sync_all(libraries, dry_run=dry_run, verbose=verbose)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from e

    _print_summary(outcomes)
    # Outside the try: setup reports its own errors through typer.Exit.
    _report_new_content(new_content, auto_setup=auto_setup)


def check_for_library_changes(lib_path: Path, since: str = "HEAD~1") -> list[str]:
    """Return the kinds of library content added between ``since`` and HEAD.

    The kinds are ``symbols``, ``footprints``, and ``templates``. Added,
    modified, and renamed paths
    count; deletions do not. When git cannot compare the revisions (for
    example, ``since`` predates the first commit), every kind the library
    currently contains is returned instead.

    Args:
        lib_path: The library's git clone.
        since: The revision to compare HEAD with, normally HEAD before a pull.
    """
    try:
        result = _run_git(
            lib_path, "diff", "--name-only", "--diff-filter=AMR", since, "HEAD"
        )
    except OSError:
        return _check_current_library_state(lib_path)
    if result.returncode != 0:
        return _check_current_library_state(lib_path)

    changes: list[str] = []
    for path in result.stdout.splitlines():
        for kind, matches in _CONTENT_KINDS:
            if kind not in changes and matches(path):
                changes.append(kind)
    return changes


def _is_symbol_library_change(path: str) -> bool:
    """Return whether ``path`` is a symbol library file."""
    return path.startswith("symbols/") and path.endswith(".kicad_sym")


def _is_footprint_library_change(path: str) -> bool:
    """Return whether ``path`` is a footprint library or a file inside one."""
    return path.startswith("footprints/") and (
        path.endswith(".pretty") or ".pretty/" in path
    )


def _is_template_change(path: str) -> bool:
    """Return whether ``path`` is a project template's metadata file."""
    return path.startswith("templates/") and path.endswith("metadata.yaml")


_CONTENT_KINDS = (
    ("symbols", _is_symbol_library_change),
    ("footprints", _is_footprint_library_change),
    ("templates", _is_template_change),
)


def _check_current_library_state(lib_path: Path) -> list[str]:
    """Return every kind of library content ``lib_path`` currently contains."""
    changes: list[str] = []
    if any((lib_path / "symbols").glob("**/*.kicad_sym")):
        changes.append("symbols")
    if any(path.is_dir() for path in (lib_path / "footprints").glob("**/*.pretty")):
        changes.append("footprints")
    if any(
        (path / "metadata.yaml").exists()
        for path in (lib_path / "templates").glob("*")
        if path.is_dir()
    ):
        changes.append("templates")
    return changes
