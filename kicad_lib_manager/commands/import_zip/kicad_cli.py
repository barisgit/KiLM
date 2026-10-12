"""Finding kicad-cli and upgrading vendor files with it."""

import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console

from .formats import format_version

console = Console()

_KICAD_CLI_CANDIDATES: tuple[Path, ...] = (
    Path.home() / "AppImages" / "kicad.appimage",
    Path("/usr/bin/kicad-cli"),
    Path("/usr/local/bin/kicad-cli"),
    Path("/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"),
)

_TIMEOUT_SECONDS = 30


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


def detect_kicad_cli() -> Path | None:
    """Return kicad-cli from PATH or a known install location, else None."""
    on_path = shutil.which("kicad-cli")
    if on_path is not None:
        return Path(on_path)
    candidates = list(_KICAD_CLI_CANDIDATES)
    if sys.platform == "win32":
        candidates += _windows_kicad_cli_candidates()
    return next((c for c in candidates if c.exists()), None)


def _build_kicad_cli_cmd(kicad_cli: Path, *args: str) -> list[str]:
    """Return the command list for kicad-cli, inserting the subcommand for AppImages."""
    if kicad_cli.suffix.lower() == ".appimage":
        return [str(kicad_cli), "kicad-cli", *args]
    return [str(kicad_cli), *args]


@dataclass
class Upgrader:
    """Upgrades vendor files to the installed KiCad's format, never past a limit.

    The limit is the target library's format: an upgrade that would exceed
    it is dropped and the vendor format kept. kicad-cli always writes the
    same format, so after one such drop the upgrades of that kind are
    skipped for the rest of the run. kicad_cli None disables upgrades.
    """

    kicad_cli: Path | None
    footprints_enabled: bool = True
    symbols_enabled: bool = True

    def footprint(self, name: str, text: str, limit: int | None) -> str:
        """Return text upgraded if it is a legacy (module ...) footprint."""
        cli = self.kicad_cli
        if cli is None or not self.footprints_enabled:
            return text
        if not text.lstrip().startswith("(module"):
            return text
        with tempfile.TemporaryDirectory(prefix="kilm_fp_upgrade_") as tmp:
            in_pretty = Path(tmp) / "in.pretty"
            in_pretty.mkdir()
            (in_pretty / name).write_bytes(text.encode("utf-8"))
            out_dir = Path(tmp) / "out"
            args = ("--force", "--output", str(out_dir), str(in_pretty))
            upgraded = out_dir / name
            if not _run(cli, name, "fp", "upgrade", *args) or not upgraded.exists():
                return text
            new_text = upgraded.read_text(encoding="utf-8")
        if not _within_limit(new_text, limit, ".kicad_mod"):
            self.footprints_enabled = False
            return text
        return new_text

    def symbols(self, name: str, text: str, limit: int | None) -> str:
        """Return the symbol library text upgraded."""
        cli = self.kicad_cli
        if cli is None or not self.symbols_enabled:
            return text
        with tempfile.TemporaryDirectory(prefix="kilm_sym_upgrade_") as tmp:
            path = Path(tmp) / name
            path.write_bytes(text.encode("utf-8"))
            if not _run(cli, name, "sym", "upgrade", "--force", str(path)):
                return text
            new_text = path.read_text(encoding="utf-8")
        if not _within_limit(new_text, limit, ".kicad_sym"):
            self.symbols_enabled = False
            return text
        return new_text


def _run(kicad_cli: Path, label: str, *args: str) -> bool:
    """Run kicad-cli with args; warn about label and return False on failure."""
    cmd = _build_kicad_cli_cmd(kicad_cli, *args)
    try:
        subprocess.run(
            cmd, capture_output=True, text=True, check=True, timeout=_TIMEOUT_SECONDS
        )
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


def _within_limit(text: str, limit: int | None, suffix: str) -> bool:
    """Whether upgraded text's format is at most limit; reports when not."""
    version = format_version(text)
    if limit is None or version is None or version <= limit:
        return True
    console.print(
        f"[dim]  kicad-cli writes format {version}, newer than {limit} in the "
        f"target library; keeping vendor {suffix} formats[/dim]"
    )
    return False
