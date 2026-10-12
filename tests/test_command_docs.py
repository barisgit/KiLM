"""Drift checks between the registered CLI commands and their documentation.

Every top-level command registered on ``kicad_lib_manager.main.app`` must have a
collocated ``commands/<package>/docs.mdx`` page that the docs site publishes under
the command's name and lists in its sidebar. That page must mention every option
flag the command, or any of its subcommands, shows in ``--help``. In the other
direction, every long flag that a docs page attributes to a ``kilm`` command must
still exist, so renamed or removed options cannot linger in the documentation.
"""

from __future__ import annotations

import re
from pathlib import Path

import click
import pytest
import typer

from kicad_lib_manager.main import app

REPO_ROOT = Path(__file__).resolve().parent.parent
COMMANDS_DIR = REPO_ROOT / "kicad_lib_manager" / "commands"
COMMANDS_PACKAGE = "kicad_lib_manager.commands."
DOCS_DIR = REPO_ROOT / "docs"
SITE_CONTENT_DIR = DOCS_DIR / "src" / "content" / "docs"
# Pages under this directory, except the index, are generated from docs.mdx files.
GENERATED_REFERENCE_DIR = SITE_CONTENT_DIR / "reference" / "cli"

# Click adds the help option to every command outside ``Command.params``.
HELP_FLAGS = frozenset({"--help", "-h"})
# Programs other than kilm whose flags appear on command pages (pip install --user).
EXTERNAL_PROGRAMS = frozenset({"git", "pip", "pipx", "uv"})
LONG_FLAG = re.compile(r"(?<![\w-])--[a-z0-9][a-z0-9-]*")
# Shell commands start at a line, inline code span, or after a shell separator.
SEGMENT_SEPARATOR = re.compile(r"`|&&|\|\||\||;")


def _root_group() -> click.Group:
    root = typer.main.get_command(app)
    assert isinstance(root, click.Group)
    return root


ROOT = _root_group()
COMMAND_NAMES = sorted(ROOT.commands)


def _own_flags(command: click.Command) -> frozenset[str]:
    """Return the flags of ``command`` itself that ``--help`` shows."""
    return frozenset(
        flag
        for param in command.params
        if isinstance(param, click.Option) and not param.hidden
        for flag in (*param.opts, *param.secondary_opts)
    )


def _subtree(command: click.Command) -> list[click.Command]:
    """Return ``command`` and, for groups, all of its nested subcommands."""
    nested = command.commands.values() if isinstance(command, click.Group) else ()
    return [command, *(sub for child in nested for sub in _subtree(child))]


def _subtree_flags(command: click.Command) -> frozenset[str]:
    """Return the flags of ``command`` and every nested subcommand."""
    return frozenset(flag for sub in _subtree(command) for flag in _own_flags(sub))


def _package_dir(command: click.Command) -> Path:
    """Return the ``commands/<package>`` directory implementing ``command``."""
    packages = {
        callback.__module__.removeprefix(COMMANDS_PACKAGE).split(".")[0]
        for sub in _subtree(command)
        if (callback := sub.callback) is not None
        and callback.__module__.startswith(COMMANDS_PACKAGE)
    }
    assert len(packages) == 1, f"expected one command package, found {packages}"
    return COMMANDS_DIR / packages.pop()


def _docs_page(name: str) -> Path:
    return _package_dir(ROOT.commands[name]) / "docs.mdx"


def _mentions(text: str, flag: str) -> bool:
    return re.search(rf"(?<![\w-]){re.escape(flag)}(?![\w-])", text) is not None


def _resolve(words: list[str]) -> tuple[click.Command, str]:
    """Resolve the words after ``kilm`` to the deepest matching command."""
    command: click.Command = ROOT
    path = ["kilm"]
    for word in words:
        if not isinstance(command, click.Group) or word not in command.commands:
            break
        command = command.commands[word]
        path.append(word)
    return command, " ".join(path)


def _segment_flags(
    segment: str, page_command: str | None
) -> tuple[frozenset[str], str] | None:
    """Return the flags valid in a text segment and their owner, or None to skip.

    A segment that runs another program, such as ``pip install kilm --user``, is
    skipped. A ``kilm`` invocation before the first flag owns the flags, and only
    the options of the (sub)command it names are valid, so ``kilm update --force``
    fails although ``kilm update perform --force`` exists. Other flags on a
    command page may belong to the page's command or any of its subcommands;
    on site pages they are not checked.
    """
    words = segment.split()
    if words[0] in EXTERNAL_PROGRAMS:
        return None
    first_flag = next(i for i, word in enumerate(words) if LONG_FLAG.search(word))
    before_flags = words[:first_flag]
    if "kilm" in before_flags:
        last_kilm = len(before_flags) - 1 - before_flags[::-1].index("kilm")
        command, path = _resolve(words[last_kilm + 1 :])
        return _own_flags(command), path
    if page_command is None:
        return None
    return _subtree_flags(ROOT.commands[page_command]), f"kilm {page_command}"


def _logical_lines(text: str) -> list[tuple[int, str]]:
    """Join backslash-continued shell lines, numbering each by its last line."""
    logical: list[tuple[int, str]] = []
    pending = ""
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.rstrip()
        if stripped.endswith("\\"):
            pending += stripped[:-1] + " "
            continue
        logical.append((number, pending + line))
        pending = ""
    return logical


def _stale_flags(page: Path, page_command: str | None) -> list[str]:
    """List long flags on ``page`` that the command they belong to lacks."""
    stale: list[str] = []
    for number, line in _logical_lines(page.read_text(encoding="utf-8")):
        for segment in SEGMENT_SEPARATOR.split(line):
            flags = LONG_FLAG.findall(segment)
            target = _segment_flags(segment, page_command) if flags else None
            if target is None:
                continue
            known, owner = target
            stale.extend(
                f"{page.name}:{number}: {flag} is not an option of {owner}"
                for flag in flags
                if flag not in known | HELP_FLAGS
            )
    return stale


def _site_pages() -> list[Path]:
    return sorted(
        page
        for page in SITE_CONTENT_DIR.rglob("*.md*")
        if page.parent != GENERATED_REFERENCE_DIR or page.stem == "index"
    )


@pytest.mark.parametrize("name", COMMAND_NAMES)
def test_command_docs_page_is_published(name: str) -> None:
    """The page exists and the docs sync publishes it at the command's URL."""
    page = _docs_page(name)
    assert page.is_file(), f"missing {page.relative_to(REPO_ROOT)}"

    # docs/scripts/sync-embedded-docs.ts names the page after .command or the directory.
    command_file = page.parent / ".command"
    published = (
        command_file.read_text(encoding="utf-8").strip()
        if command_file.is_file()
        else page.parent.name
    )
    assert published == name, f"add {command_file.relative_to(REPO_ROOT)} = {name}"

    sidebar = (DOCS_DIR / "astro.config.mjs").read_text(encoding="utf-8")
    assert f'link: "/reference/cli/{name}/"' in sidebar


@pytest.mark.parametrize("name", COMMAND_NAMES)
def test_command_docs_page_mentions_every_flag(name: str) -> None:
    """Every flag of the command and its subcommands appears on its page."""
    text = _docs_page(name).read_text(encoding="utf-8")
    flags = _subtree_flags(ROOT.commands[name])
    missing = sorted(flag for flag in flags if not _mentions(text, flag))
    assert not missing, f"{_docs_page(name)} does not document: {', '.join(missing)}"


@pytest.mark.parametrize("name", COMMAND_NAMES)
def test_command_docs_page_has_no_stale_flags(name: str) -> None:
    """Every long flag on a command page still exists on the command it names."""
    stale = _stale_flags(_docs_page(name), name)
    assert not stale, "\n".join(stale)


def _site_page_id(page: Path) -> str:
    return page.relative_to(SITE_CONTENT_DIR).as_posix()


@pytest.mark.parametrize("page", _site_pages(), ids=_site_page_id)
def test_site_page_has_no_stale_kilm_flags(page: Path) -> None:
    """Flags in ``kilm`` invocations on guide and reference pages still exist."""
    stale = _stale_flags(page, None)
    assert not stale, "\n".join(stale)
