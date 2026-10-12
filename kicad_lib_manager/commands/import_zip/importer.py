"""Importing one vendor ZIP into a library: plan every write, then apply it."""

import re
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from rich.console import Console

from ...utils.backup import create_backup
from ...utils.file_ops import write_atomically
from .archive import extract_part_files, is_model
from .errors import ImportFailure
from .formats import require_compatible
from .kicad_cli import Upgrader
from .symbols import SymbolMerge, merge_symbols

console = Console()


@dataclass(frozen=True)
class ModelRef:
    """A model file as footprints reference it: <prefix>/<name>."""

    prefix: str
    name: str

    @property
    def path(self) -> str:
        return f"{self.prefix}/{self.name}"


@dataclass
class ImportTarget:
    """The libraries a run imports into, plus what the run has added so far.

    models maps the case-folded names of the model files in any *.3dshapes
    dir of the library to their location; footprints holds the case-folded
    file names in fp_dir; symbols holds symbol names added in the run.
    File names compare case-insensitively, so a run adds the same files on
    case-sensitive and case-insensitive filesystems and the library stays
    usable on both. Each ZIP adds what it planned to these, in a dry run
    too, so a dry run skips the same repeats a real run does.

    sym_format and fp_format are the library formats imported files must
    not exceed (None: no limit). backup is the symbol library backup taken
    before its first change in the run.
    """

    sym_lib: Path
    fp_dir: Path
    models_dir: Path
    model_prefix: str
    upgrader: Upgrader
    dry_run: bool
    sym_format: Optional[int] = None
    fp_format: Optional[int] = None
    models: dict[str, ModelRef] = field(default_factory=dict)
    footprints: set[str] = field(default_factory=set)
    symbols: set[str] = field(default_factory=set)
    backup: Optional[Path] = None


@dataclass
class ZipResult:
    """Names of the symbols, footprint files, and model files a ZIP added."""

    symbols: list[str] = field(default_factory=list)
    footprints: list[str] = field(default_factory=list)
    models: list[str] = field(default_factory=list)

    def extend(self, other: "ZipResult") -> None:
        self.symbols.extend(other.symbols)
        self.footprints.extend(other.footprints)
        self.models.extend(other.models)


@dataclass
class _Plan:
    """What importing one ZIP writes, worked out before the first write.

    models starts as the target's and gains the ZIP's new models, so the
    ZIP's footprints can reference them.
    """

    models: dict[str, ModelRef]
    model_copies: list[tuple[Path, Path]] = field(default_factory=list)
    footprints: dict[str, tuple[Path, str]] = field(default_factory=dict)
    fp_refs: dict[str, str] = field(default_factory=dict)
    symbols: Optional[SymbolMerge] = None
    lines: list[str] = field(default_factory=list)

    def result(self) -> ZipResult:
        return ZipResult(
            symbols=list(self.symbols.added) if self.symbols else [],
            footprints=[dest.name for dest, _ in self.footprints.values()],
            models=[dest.name for _, dest in self.model_copies],
        )


def import_zip_file(zip_path: Path, target: ImportTarget) -> ZipResult:
    """Import one ZIP into target and return what it added.

    Every input is extracted, decoded, upgraded, and checked before the
    first write, so a dry run fails where a real run would, and a ZIP that
    fails these checks changes nothing. Writes go models, footprints, then
    symbols, each file replaced atomically; the symbol library is backed up
    before its first change in the run.

    Raises:
        ImportFailure: The ZIP is unreadable or holds files the library
            cannot take.
        OSError: A write failed. Files written before it stay; a re-run
            skips them.
    """
    with tempfile.TemporaryDirectory(prefix="kilm_import_") as tmp:
        files = extract_part_files(zip_path, Path(tmp))
        plan = _Plan(models=dict(target.models))
        _plan_models(files, target, plan)
        _plan_footprints(files, target, plan)
        _plan_symbols(files, target, plan)
        for line in plan.lines:
            console.print(line, markup=False, highlight=False)
        if not target.dry_run:
            _apply(plan, target)
    target.models = plan.models
    target.footprints.update(plan.footprints)
    if plan.symbols:
        target.symbols.update(plan.symbols.added)
    return plan.result()


_MODEL_PATH_RE = re.compile(
    # Longer/compound extensions must come before their literal prefixes
    # (e.g. "step.gz" before "step"), or the alternation matches the
    # shorter one first and leaves the rest of the extension dangling.
    r'\(model\s+(?:"([^"]+)"|(\S+\.(?:step\.gz|stp\.gz|step|stp)))'
)


def fix_3d_path(text: str, models: Mapping[str, ModelRef]) -> str:
    """Point the footprint's model references at the library's models.

    models maps case-folded model file names to their location in the
    library. A reference whose file name is not in it, such as one into
    KiCad's own model libraries, is left alone.
    """

    def _replace(m: re.Match[str]) -> str:
        raw = m.group(1) if m.group(1) is not None else m.group(2)
        ref = models.get(Path(raw.replace("\\", "/")).name.casefold())
        return f'(model "{ref.path}"' if ref else m.group(0)

    return _MODEL_PATH_RE.sub(_replace, text)


def _read_utf8(path: Path) -> str:
    """Text of path, decoded strictly so bad input fails before any write."""
    try:
        return path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ImportFailure(
            f"{path.name} is not valid UTF-8 ({exc.reason} at byte {exc.start})"
        ) from exc


def _read_vendor_text(path: Path) -> str:
    """Vendor file text with LF line endings, which KiCad writes everywhere."""
    return _read_utf8(path).replace("\r\n", "\n")


def _plan_models(files: list[Path], target: ImportTarget, plan: _Plan) -> None:
    for f in filter(is_model, files):
        key = f.name.casefold()
        known = plan.models.get(key)
        if known is not None and known.prefix == target.model_prefix:
            plan.lines.append(f"  3D   skip (exists): {f.name}")
        elif known is not None:
            plan.lines.append(f"  3D   reuse existing {known.path} for {f.name}")
        else:
            plan.lines.append(f"  3D   add: {f.name}")
            plan.models[key] = ModelRef(target.model_prefix, f.name)
            plan.model_copies.append((f, target.models_dir / f.name))


def _plan_footprints(files: list[Path], target: ImportTarget, plan: _Plan) -> None:
    lib = target.fp_dir.stem
    for f in (f for f in files if f.suffix.lower() == ".kicad_mod"):
        plan.fp_refs[f.stem] = f"{lib}:{f.stem}"
        key = f.name.casefold()
        if key in target.footprints or key in plan.footprints:
            plan.lines.append(f"  FP   skip (exists): {f.name}")
            continue
        text = _read_vendor_text(f)
        text = target.upgrader.footprint(f.name, text, target.fp_format)
        require_compatible(f.name, text, target.fp_format, target.fp_dir, "fp")
        plan.footprints[key] = (target.fp_dir / f.name, fix_3d_path(text, plan.models))
        plan.lines.append(f"  FP   add: {f.name}")


def _plan_symbols(files: list[Path], target: ImportTarget, plan: _Plan) -> None:
    sym_files = [f for f in files if f.suffix.lower() == ".kicad_sym"]
    if not sym_files:
        return
    merged = SymbolMerge(_read_utf8(target.sym_lib), [], [])
    for f in sym_files:
        text = target.upgrader.symbols(f.name, _read_vendor_text(f), target.sym_format)
        merge = merge_symbols(
            text, merged.text, target.fp_dir.stem, plan.fp_refs, target.symbols
        )
        if merge.added:
            require_compatible(f.name, text, target.sym_format, target.sym_lib, "sym")
        merged = SymbolMerge(
            merge.text, merged.added + merge.added, merged.skipped + merge.skipped
        )
    plan.symbols = merged
    plan.lines.extend(f"  SYM  add: {name}" for name in merged.added)
    plan.lines.extend(f"  SYM  skip (exists): {name}" for name in merged.skipped)


def _apply(plan: _Plan, target: ImportTarget) -> None:
    for src, dest in plan.model_copies:
        dest.parent.mkdir(parents=True, exist_ok=True)
        write_atomically(dest, src.read_bytes())
    for dest, text in plan.footprints.values():
        dest.parent.mkdir(parents=True, exist_ok=True)
        write_atomically(dest, text.encode("utf-8"))
    if plan.symbols and plan.symbols.added:
        if target.backup is None:
            target.backup = create_backup(target.sym_lib)
            console.print(f"  Backup: {target.backup}", style="dim", markup=False)
        write_atomically(target.sym_lib, plan.symbols.text.encode("utf-8"))
