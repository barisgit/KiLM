"""
Import command: unpack a SamacSys/Mouser/UltraLibrarian/SnapMagic KiCad ZIP into the configured library.
"""

import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console

from ...services.config_service import Config

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


def _fix_footprint_ref(block: str, lib_name: str) -> str:
    def _replace(m: re.Match[str]) -> str:
        val = m.group(1)
        if ":" not in val:
            val = f"{lib_name}:{val}"
        return f'"Footprint" "{val}"'

    return re.sub(r'"Footprint" "([^"]+)"', _replace, block)


def _merge_symbols(
    src_file: Path, sym_lib: Path, lib_name: str, dry_run: bool
) -> tuple[list[str], list[str]]:
    src_text = src_file.read_text(encoding="utf-8")
    lpp_text = sym_lib.read_text(encoding="utf-8")
    existing = {_symbol_name(b) for b in _extract_symbol_blocks(lpp_text)}

    added: list[str] = []
    skipped: list[str] = []
    new_blocks: list[str] = []

    for block in _extract_symbol_blocks(src_text):
        name = _symbol_name(block)
        if name in existing:
            skipped.append(name)
            continue
        block = _fix_footprint_ref(block, lib_name)
        new_blocks.append(block)
        added.append(name)

    if new_blocks and not dry_run:
        insert = "\n".join(new_blocks) + "\n"
        last = lpp_text.rfind(")")
        sym_lib.write_text(lpp_text[:last] + insert + lpp_text[last:], encoding="utf-8")

    return added, skipped


# ── Footprint helpers ─────────────────────────────────────────────────────────


_MODEL_PATH_RE = re.compile(
    # Longer/compound extensions must come before their literal prefixes
    # (e.g. "step.gz" before "step"), or the alternation matches the
    # shorter one first and leaves the rest of the extension dangling.
    r'\(model\s+(?:"([^"]+)"|(\S+\.(?:step\.gz|stp\.gz|step|stp)))'
)


def _fix_3d_path(text: str, models_dir_name: str) -> str:
    def _replace(m: re.Match[str]) -> str:
        raw = m.group(1) if m.group(1) is not None else m.group(2)
        filename = Path(raw).name
        return f'(model "${{KICAD_3RD_PARTY}}/{models_dir_name}/{filename}"'

    return _MODEL_PATH_RE.sub(_replace, text)


def _upgrade_fp(path: Path, kicad_cli: Optional[Path]) -> None:
    """Upgrade legacy (module ...) footprint format in-place using kicad-cli."""
    if kicad_cli is None or not kicad_cli.exists():
        return
    first_line = path.read_text(encoding="utf-8", errors="replace").lstrip()[:20]
    if not first_line.startswith("(module"):
        return

    with tempfile.TemporaryDirectory(prefix="kilm_fp_upgrade_") as tmp:
        in_pretty = Path(tmp) / "in.pretty"
        in_pretty.mkdir()
        shutil.copy2(path, in_pretty / path.name)
        out_dir = Path(tmp) / "out"

        cmd = _build_kicad_cli_cmd(
            kicad_cli,
            "fp",
            "upgrade",
            "--force",
            "--output",
            str(out_dir),
            str(in_pretty),
        )

        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
        except subprocess.TimeoutExpired:
            console.print(
                f"[yellow]  warn: kicad-cli fp upgrade timed out for {path.name}, skipping[/yellow]"
            )
            return
        except subprocess.CalledProcessError as exc:
            console.print(
                f"[yellow]  warn: kicad-cli fp upgrade failed for {path.name}: {exc.stderr.strip()}[/yellow]"
            )
            return
        upgraded = out_dir / path.name
        if upgraded.exists():
            shutil.copy2(upgraded, path)


def _upgrade_sym(sym_file: Path, kicad_cli: Optional[Path]) -> None:
    """Upgrade symbol file format in-place using kicad-cli."""
    if kicad_cli is None or not kicad_cli.exists():
        return
    cmd = _build_kicad_cli_cmd(kicad_cli, "sym", "upgrade", "--force", str(sym_file))
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
    except subprocess.TimeoutExpired:
        console.print(
            f"[yellow]  warn: kicad-cli sym upgrade timed out for {sym_file.name}, skipping[/yellow]"
        )
    except subprocess.CalledProcessError as exc:
        console.print(
            f"[yellow]  warn: kicad-cli sym upgrade failed for {sym_file.name}: {exc.stderr.strip()}[/yellow]"
        )


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


# ── Per-ZIP import ────────────────────────────────────────────────────────────


def _import_zip(
    zip_path: Path,
    sym_lib: Path,
    fp_dir: Path,
    models_dir: Path,
    lib_name: str,
    kicad_cli: Optional[Path],
    dry_run: bool,
) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {
        "sym": [],
        "sym_skipped": [],
        "fp": [],
        "models": [],
    }
    models_dir_name = models_dir.name

    with tempfile.TemporaryDirectory(prefix="kilm_import_") as tmp:
        tmp_path = Path(tmp)
        with zipfile.ZipFile(zip_path) as zf:
            _safe_extractall(zf, tmp_path)

        # Vendor ZIPs disagree on directory layout (SamacSys/Mouser use
        # "KiCad"/"3D" dirs, UltraLibrarian uses "KiCADv6" with a nested
        # "*.pretty" dir, SnapMagic has no wrapping dir at all) so search
        # the whole extracted tree by extension instead of by dir name.

        # 3D models
        for f in tmp_path.rglob("*"):
            if f.suffix.lower() in (".stp", ".step") or f.name.lower().endswith(
                (".stp.gz", ".step.gz")
            ):
                dest = models_dir / f.name
                if dest.exists():
                    console.print(f"  3D   skip (exists): {f.name}")
                else:
                    console.print(f"  3D   add: {f.name}")
                    if not dry_run:
                        models_dir.mkdir(exist_ok=True)
                        shutil.copy2(f, dest)
                    result["models"].append(f.name)

        # Footprints
        for f in tmp_path.rglob("*.kicad_mod"):
            dest = fp_dir / f.name
            if dest.exists():
                console.print(f"  FP   skip (exists): {f.name}")
                continue
            console.print(f"  FP   add: {f.name}")
            if not dry_run:
                text = _fix_3d_path(f.read_text(encoding="utf-8"), models_dir_name)
                f.write_text(text, encoding="utf-8")
                _upgrade_fp(f, kicad_cli)
                fp_dir.mkdir(exist_ok=True)
                shutil.copy2(f, dest)
            result["fp"].append(f.name)

        # Symbols
        for f in tmp_path.rglob("*.kicad_sym"):
            if not dry_run:
                _upgrade_sym(f, kicad_cli)
            added, skipped = _merge_symbols(f, sym_lib, lib_name, dry_run)
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


def _detect_kicad_cli() -> Optional[Path]:
    """Return kicad-cli path if found on PATH or a location in _KICAD_CLI_CANDIDATES."""
    on_path = shutil.which("kicad-cli")
    if on_path is not None:
        return Path(on_path)
    for candidate in _KICAD_CLI_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


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
            help="Target library name (default: first github library)",
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

    # Resolve target library
    target_lib = None
    for lib in github_libs:
        if library is None or lib.get("name") == library:
            target_lib = lib
            break

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
        console.print(f"[red]No .kicad_sym file found under {lib_path}/symbols/[/red]")
        raise typer.Exit(1)
    if not fp_candidates:
        console.print(
            f"[red]No .pretty directory found under {lib_path}/footprints/[/red]"
        )
        raise typer.Exit(1)

    sym_lib = sym_candidates[0]
    fp_dir = fp_candidates[0]
    lib_name = sym_lib.stem
    models_dir = lib_path / f"{lib_name}.3dshapes"

    # Resolve kicad-cli
    kicad_cli = kicad_cli_path if kicad_cli_path else _detect_kicad_cli()
    if kicad_cli:
        console.print(f"[dim]kicad-cli: {kicad_cli}[/dim]")
    else:
        console.print("[dim]kicad-cli not found - format upgrade skipped[/dim]")

    if dry_run:
        console.print("[yellow]Dry run - no changes will be made[/yellow]")

    totals: dict[str, list[str]] = {"sym": [], "fp": [], "models": []}

    for zip_path in zip_files:
        zip_path = zip_path.expanduser().resolve()
        if not zip_path.exists():
            console.print(f"[yellow]Skipping {zip_path.name}: file not found[/yellow]")
            continue
        if not zipfile.is_zipfile(zip_path):
            console.print(f"[yellow]Skipping {zip_path.name}: not a valid ZIP[/yellow]")
            continue

        console.print(f"\n[cyan]Importing {zip_path.name}[/cyan]")
        try:
            r = _import_zip(
                zip_path, sym_lib, fp_dir, models_dir, lib_name, kicad_cli, dry_run
            )
        except Exception as exc:
            console.print(f"[red]  error: {zip_path.name}: {exc}[/red]")
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
