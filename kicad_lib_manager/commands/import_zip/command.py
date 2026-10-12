"""
Import command: unpack a SamacSys/Mouser/UltraLibrarian/SnapMagic KiCad ZIP into the configured library.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console

from ...services.config_service import Config, LibraryDict
from ...utils.metadata import read_cloud_metadata, read_github_metadata

console = Console()

# ── Symbol helpers ────────────────────────────────────────────────────────────


def _extract_symbol_blocks(text: str) -> list[str]:
    """Extract top-level `(symbol "...")` blocks by tracking paren depth.

    Depth-based (not indentation-based) so it works regardless of whether
    the generator indents with tabs (SamacSys/Mouser) or spaces
    (UltraLibrarian), and regardless of line endings.
    """
    blocks: list[str] = []
    depth = 0
    in_str = False
    block_start: Optional[int] = None
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if in_str:
            if ch == "\\" and i + 1 < n:
                i += 2
                continue
            if ch == '"':
                in_str = False
            i += 1
            continue
        if ch == '"':
            in_str = True
        elif ch == "(":
            if depth == 1 and text.startswith('(symbol "', i):
                block_start = i
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 1 and block_start is not None:
                blocks.append(text[block_start : i + 1])
                block_start = None
        i += 1
    return blocks


def _symbol_name(block: str) -> str:
    m = re.match(r'\(symbol "([^"]+)"', block)
    return m.group(1) if m else ""


def _fix_footprint_ref(
    block: str, lib_name: str, fp_libs: Optional[dict[str, str]] = None
) -> str:
    """Point the symbol's Footprint field at a library.

    fp_libs maps footprint names from the same ZIP to the library that holds
    them; those win over any vendor prefix. Other bare names get lib_name;
    other prefixed names are left alone.
    """

    def _replace(m: re.Match[str]) -> str:
        val = m.group(1)
        name = val.split(":", 1)[1] if ":" in val else val
        if fp_libs and name in fp_libs:
            val = f"{fp_libs[name]}:{name}"
        elif ":" not in val:
            val = f"{lib_name}:{val}"
        return f'"Footprint" "{val}"'

    return re.sub(r'"Footprint" "([^"]+)"', _replace, block)


def _merge_symbols(
    src_file: Path,
    sym_lib: Path,
    lib_name: str,
    dry_run: bool,
    fp_libs: Optional[dict[str, str]] = None,
    planned: Optional[set[str]] = None,
) -> tuple[list[str], list[str]]:
    """Append the symbols of src_file that sym_lib lacks; return (added, skipped).

    planned holds names added earlier in this run and is updated in place, so
    a dry run, which writes nothing, skips the same repeats a real run does.
    The library keeps its own line endings.
    """
    src_text = src_file.read_text(encoding="utf-8")
    with sym_lib.open(encoding="utf-8", newline="") as fh:
        dest_text = fh.read()
    newline = "\r\n" if "\r\n" in dest_text else "\n"
    existing = {_symbol_name(b) for b in _extract_symbol_blocks(dest_text)}
    existing |= planned or set()

    added: list[str] = []
    skipped: list[str] = []
    new_blocks: list[str] = []

    for block in _extract_symbol_blocks(src_text):
        name = _symbol_name(block)
        if name in existing or name in added:
            skipped.append(name)
            continue
        block = _fix_footprint_ref(block, lib_name, fp_libs)
        new_blocks.append(block.replace("\n", newline))
        added.append(name)

    if new_blocks and not dry_run:
        insert = newline.join(new_blocks) + newline
        last = dest_text.rfind(")")
        with sym_lib.open("w", encoding="utf-8", newline="") as fh:
            fh.write(dest_text[:last] + insert + dest_text[last:])
    if planned is not None:
        planned.update(added)

    return added, skipped


# ── Footprint helpers ─────────────────────────────────────────────────────────


_MODEL_PATH_RE = re.compile(
    # Longer/compound extensions must come before their literal prefixes
    # (e.g. "step.gz" before "step"), or the alternation matches the
    # shorter one first and leaves the rest of the extension dangling.
    r'\(model\s+(?:"([^"]+)"|(\S+\.(?:step\.gz|stp\.gz|step|stp)))'
)


def _fix_3d_path(
    text: str, model_prefix: str, prefixes: Optional[Mapping[str, str]] = None
) -> str:
    """Point every model path at model_prefix, e.g. "${KICAD_3D_MYLIB}".

    prefixes maps model file names to the prefix of the dir that already
    holds them; those win over model_prefix.
    """

    def _replace(m: re.Match[str]) -> str:
        raw = m.group(1) if m.group(1) is not None else m.group(2)
        filename = Path(raw.replace("\\", "/")).name
        prefix = (prefixes or {}).get(filename, model_prefix)
        return f'(model "{prefix}/{filename}"'

    return _MODEL_PATH_RE.sub(_replace, text)


# ── Format versions ───────────────────────────────────────────────────────────

# KiCad stamps s-expression files with "(version YYYYMMDD)". A KiCad release
# refuses files newer than the format it writes, so an import must not raise
# a shared library's format above what its users' KiCad already reads.
_FORMAT_VERSION_RE = re.compile(r"\(version\s+(\d+)\)")

# The version stamp sits in the file header; this many characters cover it.
_HEADER_CHARS = 1024


def _format_version(text: str) -> Optional[int]:
    """Return the format version in a KiCad file header, None when absent."""
    m = _FORMAT_VERSION_RE.search(text[:_HEADER_CHARS])
    return int(m.group(1)) if m else None


def _file_format_version(path: Path) -> Optional[int]:
    """_format_version of a file, reading only its header."""
    with path.open(encoding="utf-8", errors="replace") as fh:
        return _format_version(fh.read(_HEADER_CHARS))


def _footprint_lib_version(fp_dir: Path) -> Optional[int]:
    """Newest format among fp_dir's footprints; None when it has none.

    Legacy (module ...) footprints carry no version and count as 0.
    """
    versions = [_file_format_version(f) or 0 for f in fp_dir.glob("*.kicad_mod")]
    return max(versions, default=None)


def _warn_if_newer(path: Path, limit: Optional[int], target: str) -> None:
    """Warn when path's format is newer than the target library's."""
    version = _file_format_version(path)
    if limit is not None and version is not None and version > limit:
        console.print(
            f"[yellow]  warn: {path.name} uses format {version}, newer than "
            f"{target} ({limit}); older KiCad releases cannot read it[/yellow]"
        )


# ── kicad-cli upgrades ────────────────────────────────────────────────────────


def _run_kicad_cli(kicad_cli: Path, label: str, *args: str) -> bool:
    """Run kicad-cli with args; warn about label and return False on failure."""
    cmd = _build_kicad_cli_cmd(kicad_cli, *args)
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
    except subprocess.TimeoutExpired:
        console.print(
            f"[yellow]  warn: kicad-cli {args[0]} upgrade timed out for {label}, skipping[/yellow]"
        )
        return False
    except subprocess.CalledProcessError as exc:
        console.print(
            f"[yellow]  warn: kicad-cli {args[0]} upgrade failed for {label}: {exc.stderr.strip()}[/yellow]"
        )
        return False
    return True


def _upgrade_fp(path: Path, kicad_cli: Optional[Path], limit: Optional[int]) -> bool:
    """Upgrade a legacy (module ...) footprint in place using kicad-cli.

    The upgrade is dropped when it would produce a format newer than limit,
    the footprint library's newest format (None: no limit). Returns False
    in that case, as every later upgrade in the run would be dropped too.
    """
    if kicad_cli is None or not kicad_cli.exists():
        return True
    first_line = path.read_text(encoding="utf-8", errors="replace").lstrip()[:20]
    if not first_line.startswith("(module"):
        return True

    with tempfile.TemporaryDirectory(prefix="kilm_fp_upgrade_") as tmp:
        in_pretty = Path(tmp) / "in.pretty"
        in_pretty.mkdir()
        shutil.copy2(path, in_pretty / path.name)
        out_dir = Path(tmp) / "out"
        args = ("fp", "upgrade", "--force", "--output", str(out_dir), str(in_pretty))
        upgraded = out_dir / path.name
        if not _run_kicad_cli(kicad_cli, path.name, *args) or not upgraded.exists():
            return True
        if not _within_limit(upgraded, limit):
            return False
        shutil.copy2(upgraded, path)
    return True


def _upgrade_sym(
    sym_file: Path, kicad_cli: Optional[Path], limit: Optional[int]
) -> bool:
    """Upgrade a symbol file in place using kicad-cli.

    The upgrade is dropped when it would produce a format newer than limit,
    the target symbol library's format (None: no limit). Returns False in
    that case, as every later upgrade in the run would be dropped too.
    """
    if kicad_cli is None or not kicad_cli.exists():
        return True
    with tempfile.TemporaryDirectory(prefix="kilm_sym_upgrade_") as tmp:
        upgraded = Path(tmp) / sym_file.name
        shutil.copy2(sym_file, upgraded)
        args = ("sym", "upgrade", "--force", str(upgraded))
        if not _run_kicad_cli(kicad_cli, sym_file.name, *args):
            return True
        if not _within_limit(upgraded, limit):
            return False
        shutil.copy2(upgraded, sym_file)
    return True


def _within_limit(upgraded: Path, limit: Optional[int]) -> bool:
    """Whether an upgraded file's format is at most limit; reports when not."""
    version = _file_format_version(upgraded)
    if limit is None or version is None or version <= limit:
        return True
    console.print(
        f"[dim]  kicad-cli writes format {version}, newer than {limit} in the "
        f"target library; keeping vendor {upgraded.suffix} formats[/dim]"
    )
    return False


def _build_kicad_cli_cmd(kicad_cli: Path, *args: str) -> list[str]:
    """Return the command list for kicad-cli, inserting the subcommand for AppImages."""
    if kicad_cli.suffix.lower() == ".appimage":
        return [str(kicad_cli), "kicad-cli", *args]
    return [str(kicad_cli), *args]


# ── ZIP extraction ───────────────────────────────────────────────────────────


def _safe_extractall(zf: zipfile.ZipFile, dest: Path) -> None:
    """Extract ZIP, rejecting any member whose resolved path escapes dest.

    Defense-in-depth against zip-slip: checks every member before extracting
    regardless of Python version or platform.
    """
    dest_resolved = dest.resolve()
    for member in zf.namelist():
        member_path = (dest / member).resolve()
        if member_path != dest_resolved and not member_path.is_relative_to(
            dest_resolved
        ):
            raise ValueError(f"Unsafe ZIP entry rejected: {member!r}")
    zf.extractall(dest)


def _extracted_files(root: Path) -> list[Path]:
    """Files under root in a stable order, without hidden or macOS metadata.

    ZIPs packed on macOS carry "__MACOSX/._<name>" resource forks that share
    the real files' extensions but hold binary data.
    """
    return sorted(
        p
        for p in root.rglob("*")
        if p.is_file()
        and not any(
            part.startswith(".") or part == "__MACOSX"
            for part in p.relative_to(root).parts
        )
    )


# ── Per-ZIP import ────────────────────────────────────────────────────────────


@dataclass
class _ImportTarget:
    """Where one run imports to, plus what the run has added so far.

    sym_format and fp_format cap kicad-cli upgrades (see _upgrade_sym and
    _upgrade_fp); upgrade_sym and upgrade_fp turn off once an upgrade
    exceeds its cap. models maps model file names already in the library (any
    *.3dshapes dir) or added earlier in the run to the path prefix of their
    dir; footprints and symbols hold names added earlier in the run. The
    run updates all three, so a dry run skips the same repeats a real run
    does even though it writes nothing.
    """

    sym_lib: Path
    fp_dir: Path
    models_dir: Path
    model_prefix: str
    kicad_cli: Optional[Path]
    dry_run: bool
    sym_format: Optional[int] = None
    fp_format: Optional[int] = None
    upgrade_sym: bool = True
    upgrade_fp: bool = True
    models: dict[str, str] = field(default_factory=dict)
    footprints: set[str] = field(default_factory=set)
    symbols: set[str] = field(default_factory=set)


def _is_model(path: Path) -> bool:
    return path.name.lower().endswith((".stp", ".step", ".stp.gz", ".step.gz"))


def _import_zip(zip_path: Path, target: _ImportTarget) -> dict[str, list[str]]:
    """Import one ZIP into target and return the names added per kind."""
    models = target.models
    result: dict[str, list[str]] = {
        "sym": [],
        "sym_skipped": [],
        "fp": [],
        "models": [],
    }

    with tempfile.TemporaryDirectory(prefix="kilm_import_") as tmp:
        tmp_path = Path(tmp)
        with zipfile.ZipFile(zip_path) as zf:
            _safe_extractall(zf, tmp_path)

        # Vendor ZIPs disagree on directory layout (SamacSys/Mouser use
        # "KiCad"/"3D" dirs, UltraLibrarian uses "KiCADv6" with a nested
        # "*.pretty" dir, SnapMagic has no wrapping dir at all) so search
        # the whole extracted tree by extension instead of by dir name.
        files = _extracted_files(tmp_path)

        # 3D models
        for f in filter(_is_model, files):
            dest = target.models_dir / f.name
            if dest.exists() or models.get(f.name) == target.model_prefix:
                console.print(f"  3D   skip (exists): {f.name}")
            elif f.name in models:
                console.print(
                    f"  3D   reuse existing {models[f.name]}/{f.name} for {f.name}"
                )
            else:
                console.print(f"  3D   add: {f.name}")
                if not target.dry_run:
                    target.models_dir.mkdir(exist_ok=True)
                    shutil.copy2(f, dest)
                models[f.name] = target.model_prefix
                result["models"].append(f.name)

        # Footprints
        fp_dir = target.fp_dir
        fp_libs: dict[str, str] = {}
        for f in (f for f in files if f.suffix.lower() == ".kicad_mod"):
            dest = fp_dir / f.name
            fp_libs[f.stem] = fp_dir.stem
            if dest.exists() or f.name in target.footprints:
                console.print(f"  FP   skip (exists): {f.name}")
                continue
            console.print(f"  FP   add: {f.name}")
            if not target.dry_run:
                text = _fix_3d_path(
                    f.read_text(encoding="utf-8"), target.model_prefix, models
                )
                # KiCad writes LF on every platform; so does the import.
                with f.open("w", encoding="utf-8", newline="\n") as fh:
                    fh.write(text)
                if target.upgrade_fp:
                    target.upgrade_fp = _upgrade_fp(
                        f, target.kicad_cli, target.fp_format
                    )
                fp_dir.mkdir(exist_ok=True)
                shutil.copy2(f, dest)
            _warn_if_newer(f, target.fp_format, fp_dir.name)
            target.footprints.add(f.name)
            result["fp"].append(f.name)

        # Symbols
        for f in (f for f in files if f.suffix.lower() == ".kicad_sym"):
            if not target.dry_run and target.upgrade_sym:
                target.upgrade_sym = _upgrade_sym(
                    f, target.kicad_cli, target.sym_format
                )
            added, skipped = _merge_symbols(
                f, target.sym_lib, fp_dir.stem, target.dry_run, fp_libs, target.symbols
            )
            if added:
                _warn_if_newer(f, target.sym_format, target.sym_lib.name)
            for name in added:
                console.print(f"  SYM  add: {name}")
            for name in skipped:
                console.print(f"  SYM  skip (exists): {name}")
            result["sym"].extend(added)
            result["sym_skipped"].extend(skipped)

    return result


# ── Command ───────────────────────────────────────────────────────────────────

_KICAD_CLI_CANDIDATES: tuple[Path, ...] = (
    Path.home() / "AppImages" / "kicad.appimage",
    Path("/usr/bin/kicad-cli"),
    Path("/usr/local/bin/kicad-cli"),
    Path("/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"),
)


def _windows_kicad_cli_candidates() -> list[Path]:
    """kicad-cli.exe of each KiCad under Program Files, newest version first.

    The Windows installer puts KiCad in "KiCad/<version>/bin" and leaves it
    off PATH.
    """
    program_files = Path(os.environ.get("PROGRAMFILES", r"C:\Program Files"))
    found = program_files.glob("KiCad/*/bin/kicad-cli.exe")

    def version_key(path: Path) -> list[int]:
        return [int(n) for n in re.findall(r"\d+", path.parent.parent.name)]

    return sorted(found, key=version_key, reverse=True)


def _detect_kicad_cli() -> Optional[Path]:
    """Return kicad-cli from PATH or a known install location, else None."""
    on_path = shutil.which("kicad-cli")
    if on_path is not None:
        return Path(on_path)
    candidates = list(_KICAD_CLI_CANDIDATES)
    if sys.platform == "win32":
        candidates += _windows_kicad_cli_candidates()
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _pick_lib(
    candidates: list[Path], name: Optional[str], kind: str, option: str
) -> Path:
    """Return the library called name, or the only candidate when name is None."""
    available = ", ".join(c.stem for c in candidates)
    if name is not None:
        for c in candidates:
            if c.stem == name:
                return c
        console.print(f"[red]No {kind} library '{name}'. Available: {available}[/red]")
        raise typer.Exit(1)
    if len(candidates) == 1:
        return candidates[0]
    console.print(
        f"[red]Several {kind} libraries found, choose one with {option}: {available}[/red]"
    )
    raise typer.Exit(1)


def _dir_prefix(models_dir: Path, lib_env_var: object) -> str:
    """Model path prefix for a *.3dshapes dir at the top of the library."""
    if isinstance(lib_env_var, str) and lib_env_var:
        return f"${{{lib_env_var}}}/{models_dir.name}"
    return models_dir.resolve().as_posix()


def _resolve_models(
    lib_path: Path,
    default_name: str,
    cloud_libs: list[LibraryDict],
    metadata: dict[str, object],
) -> tuple[Path, str]:
    """Return (models dir, model path prefix) for the whole library.

    A 3D library registered with 'kilm add-3d' inside lib_path is used via its
    environment variable. Otherwise models go into the library's existing
    *.3dshapes dir (one named after the library, else the first; a new
    <default_name>.3dshapes if there is none), referenced through the
    library's own environment variable from kilm.yaml, which 'kilm setup'
    defines in KiCad; without one, the absolute path is used.
    """
    for lib in cloud_libs:
        models_dir = Path(lib["path"])
        if not models_dir.is_relative_to(lib_path):
            continue
        cloud_metadata = read_cloud_metadata(models_dir) or {}
        env_var = cloud_metadata.get("env_var")
        if isinstance(env_var, str) and env_var:
            return models_dir, f"${{{env_var}}}"
    existing = sorted(d for d in lib_path.glob("*.3dshapes") if d.is_dir())
    preferred = {default_name, str(metadata.get("name", "")), lib_path.name}
    named = [d for d in existing if d.stem in preferred]
    if named:
        models_dir = named[0]
    elif len(existing) == 1:
        models_dir = existing[0]
    elif existing:
        models_dir = existing[0]
        console.print(
            f"[yellow]Several *.3dshapes dirs in {lib_path}; new models go to "
            f"{models_dir.name} (register the right one with 'kilm add-3d')[/yellow]"
        )
    else:
        models_dir = lib_path / f"{default_name}.3dshapes"
    return models_dir, _dir_prefix(models_dir, metadata.get("env_var"))


def _existing_models(
    lib_path: Path, models_dir: Path, model_prefix: str, lib_env_var: object
) -> dict[str, str]:
    """Model file name -> path prefix, for models already in the library.

    Covers the target models dir and every other *.3dshapes dir of the
    library, so an import reuses a model wherever it already lives.
    """
    dirs = [(models_dir, model_prefix)]
    for d in sorted(lib_path.glob("*.3dshapes")):
        if d.is_dir() and d.resolve() != models_dir.resolve():
            dirs.append((d, _dir_prefix(d, lib_env_var)))
    models: dict[str, str] = {}
    for d, prefix in dirs:
        if d.is_dir():
            for f in sorted(d.iterdir()):
                if f.is_file() and not f.name.startswith("."):
                    models.setdefault(f.name, prefix)
    return models


def import_zip(
    zip_files: Annotated[
        list[Path],
        typer.Argument(
            help="SamacSys/Mouser/UltraLibrarian/SnapMagic ZIP file(s) to import"
        ),
    ],
    library: Annotated[
        Optional[str],
        typer.Option(
            "--library",
            "-l",
            help="Target library name (default: the current library)",
        ),
    ] = None,
    symbol_lib: Annotated[
        Optional[str],
        typer.Option(
            "--symbol-lib",
            "-s",
            help="Symbol library to add to, e.g. MyLib_IC (required if there are several)",
        ),
    ] = None,
    footprint_lib: Annotated[
        Optional[str],
        typer.Option(
            "--footprint-lib",
            "-f",
            help="Footprint library to add to, e.g. MyLib_QFN (required if there are several)",
        ),
    ] = None,
    kicad_cli_path: Annotated[
        Optional[Path],
        typer.Option(
            "--kicad-cli", help="Path to kicad-cli or kicad.appimage for format upgrade"
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run", help="Show what would be imported without making changes"
        ),
    ] = False,
) -> None:
    """Import SamacSys/Mouser/UltraLibrarian/SnapMagic KiCad ZIP(s) into the configured library.

    Each ZIP should be a standard SamacSys multi-EDA archive (as downloaded
    from Mouser or component search) or an UltraLibrarian KiCad export.
    The command extracts the KiCad files
    and merges them into the library. Run 'kilm setup' afterwards to register
    any newly added libraries in KiCad.
    """
    config = Config()
    github_libs = config.get_libraries(library_type="github")
    if not github_libs:
        console.print("[red]No github library configured. Run 'kilm init' first.[/red]")
        raise typer.Exit(1)

    # Resolve target library: the named one, else the current one (as in
    # setup and template), which falls back to the first github library.
    if library is None:
        current = config.get_symbol_library_path()
        target_lib = next(
            (lib for lib in github_libs if lib["path"] == current), github_libs[0]
        )
    else:
        target_lib = next(
            (lib for lib in github_libs if lib.get("name") == library), None
        )

    if target_lib is None:
        console.print(f"[red]Library '{library}' not found in config.[/red]")
        raise typer.Exit(1)

    lib_path = Path(target_lib["path"])
    if not lib_path.exists():
        console.print(f"[red]Library path does not exist: {lib_path}[/red]")
        raise typer.Exit(1)

    # Find symbol lib and footprint dir
    sym_candidates = (
        sorted((lib_path / "symbols").glob("*.kicad_sym"))
        if (lib_path / "symbols").exists()
        else []
    )
    fp_candidates = (
        sorted((lib_path / "footprints").glob("*.pretty"))
        if (lib_path / "footprints").exists()
        else []
    )

    if not sym_candidates:
        console.print(
            f"[red]No .kicad_sym file in {lib_path / 'symbols'}. Create a symbol "
            "library there first (KiCad Symbol Editor: File > New Library).[/red]"
        )
        raise typer.Exit(1)
    if not fp_candidates:
        console.print(
            f"[red]No .pretty directory in {lib_path / 'footprints'}. Create a "
            "footprint library there first (KiCad Footprint Editor: File > New "
            "Library).[/red]"
        )
        raise typer.Exit(1)

    sym_lib = _pick_lib(sym_candidates, symbol_lib, "symbol", "--symbol-lib")
    fp_dir = _pick_lib(fp_candidates, footprint_lib, "footprint", "--footprint-lib")
    default_models_name = (
        sym_candidates[0].stem if len(sym_candidates) == 1 else lib_path.name
    )
    lib_metadata = read_github_metadata(lib_path) or {}
    models_dir, model_prefix = _resolve_models(
        lib_path,
        default_models_name,
        config.get_libraries(library_type="cloud"),
        lib_metadata,
    )
    models = _existing_models(
        lib_path, models_dir, model_prefix, lib_metadata.get("env_var")
    )
    if not all(p.startswith("${") for p in [model_prefix, *models.values()]):
        console.print(
            "[yellow]3D model paths will be absolute to this machine. Set env_var "
            "in kilm.yaml (kilm init) or register a 3D library (kilm add-3d) to "
            "share the library.[/yellow]"
        )
    console.print(f"[dim]Target: {sym_lib.stem} / {fp_dir.stem} / {model_prefix}[/dim]")

    # Resolve kicad-cli
    if kicad_cli_path is not None and not kicad_cli_path.exists():
        console.print(f"[red]kicad-cli not found at: {kicad_cli_path}[/red]")
        raise typer.Exit(1)
    kicad_cli = kicad_cli_path if kicad_cli_path else _detect_kicad_cli()
    if kicad_cli:
        console.print(f"[dim]kicad-cli: {kicad_cli}[/dim]")
    else:
        console.print("[dim]kicad-cli not found - format upgrade skipped[/dim]")

    if dry_run:
        console.print("[yellow]Dry run - no changes will be made[/yellow]")

    target = _ImportTarget(
        sym_lib=sym_lib,
        fp_dir=fp_dir,
        models_dir=models_dir,
        model_prefix=model_prefix,
        kicad_cli=kicad_cli,
        dry_run=dry_run,
        sym_format=_file_format_version(sym_lib),
        fp_format=_footprint_lib_version(fp_dir),
        models=models,
    )
    totals: dict[str, list[str]] = {"sym": [], "fp": [], "models": []}
    failed: list[str] = []

    for zip_path in zip_files:
        zip_path = zip_path.expanduser().resolve()
        if not zip_path.exists():
            console.print(f"[red]Skipping {zip_path.name}: file not found[/red]")
            failed.append(zip_path.name)
            continue
        if not zipfile.is_zipfile(zip_path):
            console.print(f"[red]Skipping {zip_path.name}: not a valid ZIP[/red]")
            failed.append(zip_path.name)
            continue

        console.print(f"\n[cyan]Importing {zip_path.name}[/cyan]")
        try:
            r = _import_zip(zip_path, target)
        except (OSError, ValueError, zipfile.BadZipFile) as exc:
            # One broken archive should not stop the rest; items added before
            # the error stay, and a re-run skips them.
            console.print(f"[red]  error: {zip_path.name}: {exc}[/red]")
            failed.append(zip_path.name)
            continue
        totals["sym"].extend(r["sym"])
        totals["fp"].extend(r["fp"])
        totals["models"].extend(r["models"])

    console.print("\n[bold]Summary:[/bold]")
    console.print(f"  Symbols   added: {len(totals['sym'])}")
    console.print(f"  Footprints added: {len(totals['fp'])}")
    console.print(f"  3D models  added: {len(totals['models'])}")

    if any(totals.values()) and not dry_run:
        console.print("\n[green]Import complete.[/green]")
        console.print(
            "[dim]Note: If this library is not yet configured in KiCad, run 'kilm setup' to register it.[/dim]"
        )
    elif dry_run:
        console.print(
            "\n[dim]Dry run complete - run without --dry-run to apply changes.[/dim]"
        )
    else:
        console.print("\n[dim]Nothing new added.[/dim]")

    if failed:
        console.print(f"[red]Failed to import: {', '.join(failed)}[/red]")
        raise typer.Exit(1)
