"""Resolving the libraries an import writes to from the KiLM configuration."""

from dataclasses import dataclass
from pathlib import Path

import typer

from kicad_lib_manager.commands.import_zip.formats import (
    file_format_version,
    footprint_lib_version,
)
from kicad_lib_manager.commands.import_zip.importer import ImportTarget, ModelRef
from kicad_lib_manager.commands.import_zip.kicad_cli import Upgrader
from kicad_lib_manager.services.config_service import Config, LibraryDict
from kicad_lib_manager.utils.console import get_console
from kicad_lib_manager.utils.metadata import read_cloud_metadata, read_github_metadata


@dataclass(frozen=True)
class LibrarySelection:
    """The libraries the user asked to import into; None leaves the choice to KiLM.

    library names the KiLM library (default: the current one); symbol_lib
    and footprint_lib pick among several symbol and footprint libraries in it.
    """

    library: str | None = None
    symbol_lib: str | None = None
    footprint_lib: str | None = None


def build_target(
    config: Config,
    selection: LibrarySelection,
    upgrader: Upgrader,
    *,
    dry_run: bool,
) -> ImportTarget:
    """Resolve the symbol library, footprint library, and models dir to import into.

    Reports the problem and raises typer.Exit(1) when there is no usable
    target.
    """
    lib_path = _library_path(config, selection.library)
    sym_candidates = sorted((lib_path / "symbols").glob("*.kicad_sym"))
    fp_candidates = sorted(
        d for d in (lib_path / "footprints").glob("*.pretty") if d.is_dir()
    )
    if not sym_candidates:
        get_console().print(
            f"[red]No .kicad_sym file in {lib_path / 'symbols'}. Create a symbol "
            "library there first (KiCad Symbol Editor: File > New Library).[/red]"
        )
        raise typer.Exit(1)
    if not fp_candidates:
        get_console().print(
            f"[red]No .pretty directory in {lib_path / 'footprints'}. Create a "
            "footprint library there first (KiCad Footprint Editor: File > New "
            "Library).[/red]"
        )
        raise typer.Exit(1)

    sym_lib = _pick_lib(sym_candidates, selection.symbol_lib, "symbol", "--symbol-lib")
    fp_dir = _pick_lib(
        fp_candidates, selection.footprint_lib, "footprint", "--footprint-lib"
    )
    default_models_name = (
        sym_candidates[0].stem if len(sym_candidates) == 1 else lib_path.name
    )
    metadata: dict[str, object] = dict(read_github_metadata(lib_path) or {})
    models_dir, model_prefix = _resolve_models(
        lib_path,
        default_models_name,
        config.get_libraries(library_type="cloud"),
        metadata,
    )
    models = _existing_models(
        lib_path, models_dir, model_prefix, metadata.get("env_var")
    )
    if not all(
        p.startswith("${") for p in [model_prefix, *(m.prefix for m in models.values())]
    ):
        get_console().print(
            "[yellow]3D model paths will be absolute to this machine. Set env_var "
            "in kilm.yaml (kilm init) or register a 3D library (kilm add-3d) to "
            "share the library.[/yellow]"
        )
    get_console().print(
        f"[dim]Target: {sym_lib.stem} / {fp_dir.stem} / {model_prefix}[/dim]"
    )

    return ImportTarget(
        sym_lib=sym_lib,
        fp_dir=fp_dir,
        models_dir=models_dir,
        model_prefix=model_prefix,
        upgrader=upgrader,
        dry_run=dry_run,
        sym_format=file_format_version(sym_lib),
        fp_format=footprint_lib_version(fp_dir),
        models=models,
        footprints={
            p.name.casefold(): p.name for p in sorted(fp_dir.iterdir()) if p.is_file()
        },
    )


def _library_path(config: Config, library: str | None) -> Path:
    """Path of the named github library, else of the current one."""
    github_libs = config.get_libraries(library_type="github")
    if not github_libs:
        get_console().print(
            "[red]No github library configured. Run 'kilm init' first.[/red]"
        )
        raise typer.Exit(1)

    if library is None:
        # The current library, as in setup and template; it falls back to
        # the first github library.
        current = config.get_symbol_library_path()
        target_lib = next(
            (lib for lib in github_libs if lib["path"] == current), github_libs[0]
        )
    else:
        target_lib = next(
            (lib for lib in github_libs if lib.get("name") == library), None
        )
    if target_lib is None:
        get_console().print(f"[red]Library '{library}' not found in config.[/red]")
        raise typer.Exit(1)

    lib_path = Path(target_lib["path"])
    if not lib_path.exists():
        get_console().print(f"[red]Library path does not exist: {lib_path}[/red]")
        raise typer.Exit(1)
    return lib_path


def _pick_lib(candidates: list[Path], name: str | None, kind: str, option: str) -> Path:
    """Return the library called name, or the only candidate when name is None."""
    available = ", ".join(c.stem for c in candidates)
    if name is not None:
        for c in candidates:
            if c.stem == name:
                return c
        get_console().print(
            f"[red]No {kind} library '{name}'. Available: {available}[/red]"
        )
        raise typer.Exit(1)
    if len(candidates) == 1:
        return candidates[0]
    get_console().print(
        f"[red]Several {kind} libraries found, choose one with {option}: "
        f"{available}[/red]"
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
        get_console().print(
            f"[yellow]Several *.3dshapes dirs in {lib_path}; new models go to "
            f"{models_dir.name} (register the right one with 'kilm add-3d')[/yellow]"
        )
    else:
        models_dir = lib_path / f"{default_name}.3dshapes"
    return models_dir, _dir_prefix(models_dir, metadata.get("env_var"))


def _existing_models(
    lib_path: Path, models_dir: Path, model_prefix: str, lib_env_var: object
) -> dict[str, ModelRef]:
    """Case-folded model file name -> location, for models already in the library.

    Covers the target models dir, which wins, and every other *.3dshapes dir
    of the library, so an import reuses a model wherever it already lives.
    """
    dirs = [(models_dir, model_prefix)]
    dirs.extend(
        (d, _dir_prefix(d, lib_env_var))
        for d in sorted(lib_path.glob("*.3dshapes"))
        if d.is_dir() and d.resolve() != models_dir.resolve()
    )
    models: dict[str, ModelRef] = {}
    for d, prefix in dirs:
        if d.is_dir():
            for f in sorted(d.iterdir()):
                if f.is_file() and not f.name.startswith("."):
                    models.setdefault(f.name.casefold(), ModelRef(prefix, f.name))
    return models
