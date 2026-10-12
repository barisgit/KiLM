"""Choosing the files of a source project that a new template copies.

``plan_template_files`` is the one place that decides what ``template make``
copies, so the dry-run preview, the copy, and the variable scan agree.
"""

# PEP 810: on Python 3.15+ these imports load on first use.
__lazy_modules__ = {"pathspec"}

import os
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path, PurePath

import click
import pathspec

from kicad_lib_manager.utils.template.constants import (
    ALWAYS_IGNORED_PATTERNS,
    DEFAULT_VARIABLE_PATTERNS,
    EXCLUDED_DIRECTORIES,
    KICAD_PCB_EXT,
    KICAD_PRL_EXT,
    KICAD_PROJECT_EXT,
    KICAD_SCHEMATIC_EXT,
    MAX_SCANNED_FILE_BYTES,
)

GITIGNORE = ".gitignore"
GITIGNORE_SYNTAX = "gitwildmatch"


class MainFileKind(Enum):
    """The KiCad files of a project that are renamed after ``project_filename``."""

    PROJECT = KICAD_PROJECT_EXT
    SCHEMATIC = KICAD_SCHEMATIC_EXT
    PCB = KICAD_PCB_EXT

    @property
    def label(self) -> str:
        """How messages name this kind of file."""
        return "PCB" if self is MainFileKind.PCB else self.name.lower()


@dataclass(frozen=True)
class Exclusion:
    """A path left out of a template and the message that explains why.

    ``path`` is relative to the source in POSIX form; directories end in ``/``.
    """

    path: str
    message: str


@dataclass
class TemplatePlan:
    """What a template made from a source project contains.

    Paths are relative to the source directory, in ``os.walk`` order.
    ``main_files`` maps each kind to the first such file in the source
    directory or one level below it.
    """

    directories: list[PurePath] = field(default_factory=list)
    files: list[PurePath] = field(default_factory=list)
    excluded: list[Exclusion] = field(default_factory=list)
    main_files: dict[MainFileKind, PurePath] = field(default_factory=dict)

    def main_kind(self, relative: PurePath) -> MainFileKind | None:
        """Return the kind of main KiCad file ``relative`` is, if it is one."""
        return next(
            (kind for kind, path in self.main_files.items() if path == relative),
            None,
        )


def get_gitignore_spec(directory: Path) -> pathspec.PathSpec | None:
    """Return the ``.gitignore`` patterns of ``directory`` plus common ignores.

    Returns None when there is no ``.gitignore``. A file that cannot be read is
    reported on stderr and also gives None.
    """
    gitignore_file = directory / GITIGNORE
    if not gitignore_file.exists():
        return None
    try:
        lines = gitignore_file.read_text(encoding="utf-8").splitlines(keepends=True)
    except (OSError, UnicodeDecodeError) as error:
        click.echo(f"Warning: Error reading .gitignore file: {error}", err=True)
        return None
    lines += [
        f"{pattern}\n"
        for pattern in ALWAYS_IGNORED_PATTERNS
        if not any(pattern in line for line in lines)
    ]
    return pathspec.PathSpec.from_lines(GITIGNORE_SYNTAX, lines)


def plan_template_files(
    source_directory: Path,
    *,
    template_directory: Path | None = None,
    gitignore_spec: pathspec.PathSpec | None = None,
    additional_excludes: list[str] | None = None,
) -> TemplatePlan:
    """Decide which files and directories of a source project a template copies.

    Left out are the directories in ``EXCLUDED_DIRECTORIES`` at any depth, the
    template's own directory when it lies inside the source, paths matched by
    ``gitignore_spec`` or the gitignore-style ``additional_excludes``, and
    ``.kicad_prl`` preference files.
    """
    rules = _ExclusionRules(
        source=source_directory,
        template_root=template_directory,
        gitignore=gitignore_spec,
        additional=None
        if additional_excludes is None
        else pathspec.PathSpec.from_lines(GITIGNORE_SYNTAX, additional_excludes),
    )
    plan = TemplatePlan()
    for root, directories, files in os.walk(source_directory):
        relative_root = PurePath(os.path.relpath(root, source_directory))
        if relative_root.parts:
            plan.directories.append(relative_root)
        kept = []
        for name in directories:
            reason = rules.directory_exclusion(relative_root / name)
            if reason is None:
                kept.append(name)
            else:
                plan.excluded.append(reason)
        directories[:] = kept
        for name in files:
            reason = rules.file_exclusion(relative_root / name)
            if reason is None:
                plan.files.append(relative_root / name)
            else:
                plan.excluded.append(reason)
    plan.main_files = _find_main_files(plan.files)
    return plan


def find_potential_variables(
    directory: Path, patterns: list[str] | None = None
) -> dict[str, list[str]]:
    """Scan the files a template of ``directory`` would copy for variable values.

    Args:
        directory: The source project.
        patterns: Regexes whose first group, or whole match when they have no
            group, is a candidate value; defaults to DEFAULT_VARIABLE_PATTERNS.

    Returns:
        Distinct values in order of discovery, keyed by a variable name made
        from the lower-cased value. Files over 1 MiB or not UTF-8 are skipped.
    """
    compiled = [
        re.compile(pattern) for pattern in patterns or DEFAULT_VARIABLE_PATTERNS
    ]
    plan = plan_template_files(directory, gitignore_spec=get_gitignore_spec(directory))
    variables: dict[str, list[str]] = {}
    for relative in plan.files:
        content = _read_small_text(directory / relative)
        if content is None:
            continue
        for pattern in compiled:
            for match in pattern.finditer(content):
                value = match.group(1) if pattern.groups else match.group(0)
                if not value:
                    continue
                values = variables.setdefault(_variable_name(value), [])
                if value not in values:
                    values.append(value)
    return variables


@dataclass(frozen=True)
class _ExclusionRules:
    """The exclusion checks of ``plan_template_files``, in their order."""

    source: Path
    template_root: Path | None
    gitignore: pathspec.PathSpec | None
    additional: pathspec.PathSpec | None

    def directory_exclusion(self, relative: PurePath) -> Exclusion | None:
        path = f"{relative.as_posix()}/"
        if relative.name in EXCLUDED_DIRECTORIES:
            return Exclusion(path, f"Excluding common directory: {relative.name}")
        if self.template_root is not None and _is_within(
            self.source / relative, self.template_root
        ):
            message = f"Preventing recursive template copy: {relative.as_posix()}"
            return Exclusion(path, message)
        if self.gitignore is not None and self.gitignore.match_file(path):
            return Exclusion(path, f"Excluding directory from gitignore: {path}")
        if self.additional is not None and self.additional.match_file(path):
            message = f"Excluding directory from additional patterns: {path}"
            return Exclusion(path, message)
        return None

    def file_exclusion(self, relative: PurePath) -> Exclusion | None:
        path = relative.as_posix()
        if self.gitignore is not None and self.gitignore.match_file(path):
            return Exclusion(path, f"Excluding file from gitignore: {path}")
        if self.additional is not None and self.additional.match_file(path):
            return Exclusion(path, f"Excluding file from additional patterns: {path}")
        if relative.name.lower().endswith(KICAD_PRL_EXT):
            message = f"Excluding KiCad project preferences file: {path}"
            return Exclusion(path, message)
        return None


def _is_within(path: Path, directory: Path) -> bool:
    """Whether ``path`` is ``directory`` or inside it, after resolving links."""
    try:
        path.resolve().relative_to(directory.resolve())
    except ValueError:
        return False
    return True


def _find_main_files(files: list[PurePath]) -> dict[MainFileKind, PurePath]:
    """Pick the first file of each main kind at most one directory deep."""
    main_files: dict[MainFileKind, PurePath] = {}
    for relative in files:
        if len(relative.parent.parts) > 1:
            continue
        name = relative.name.lower()
        for kind in MainFileKind:
            if name.endswith(kind.value):
                main_files.setdefault(kind, relative)
                break
    return main_files


def _read_small_text(path: Path) -> str | None:
    """Return the text of a UTF-8 file of at most 1 MiB, otherwise None."""
    try:
        if path.stat().st_size > MAX_SCANNED_FILE_BYTES:
            return None
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _variable_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", value.lower())
