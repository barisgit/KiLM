"""Safe extraction of the KiCad part files in a vendor ZIP."""

import zipfile
import zlib
from pathlib import Path, PurePosixPath

from .errors import ImportFailure

MODEL_SUFFIXES = (".stp", ".step", ".stp.gz", ".step.gz")
_PART_SUFFIXES = (".kicad_sym", ".kicad_mod", *MODEL_SUFFIXES)

# The methods zipfile decompresses; others (AES, shrink, implode, ...) raise
# NotImplementedError in the middle of an extraction.
_SUPPORTED_COMPRESSION = frozenset(
    {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED, zipfile.ZIP_BZIP2, zipfile.ZIP_LZMA}
)
_ENCRYPTED_FLAG = 0x1


def is_model(path: Path) -> bool:
    """Whether path is a 3D model file that the import copies."""
    return path.name.lower().endswith(MODEL_SUFFIXES)


def extract_part_files(zip_path: Path, dest: Path) -> list[Path]:
    """Extract the symbol, footprint, and model files of zip_path into dest.

    Vendor layouts differ (SamacSys/Mouser use "KiCad"/"3D" dirs,
    UltraLibrarian a "KiCADv6" dir with a nested "*.pretty" dir, SnapMagic
    puts the files at the root), so members are chosen by extension, not by
    directory. Other members, hidden files, and macOS metadata
    ("__MACOSX/._<name>" resource forks that share the real files'
    extensions) are not extracted. Returns the extracted paths in member name
    order.

    Raises:
        ImportFailure: The archive is corrupt, has a member that would land
            outside dest, or has a part file that is encrypted or uses a
            compression method zipfile cannot read.
    """
    try:
        with zipfile.ZipFile(zip_path) as zf:
            _reject_unsafe_paths(zf, dest)
            members = sorted(
                (m for m in zf.infolist() if _is_part_file(m)),
                key=lambda m: m.filename,
            )
            for member in members:
                _require_readable(member)
            return [Path(zf.extract(member, dest)) for member in members]
    except (zipfile.BadZipFile, zipfile.LargeZipFile, zlib.error, EOFError) as exc:
        raise ImportFailure(f"invalid or corrupt ZIP: {exc}") from exc
    except (RuntimeError, NotImplementedError) as exc:
        # What zipfile raises for members it cannot decrypt or decompress
        # (e.g. without the bz2 or lzma module) that the checks did not catch.
        raise ImportFailure(f"unreadable archive: {exc}") from exc


def _reject_unsafe_paths(zf: zipfile.ZipFile, dest: Path) -> None:
    """Raise ImportFailure if any member would resolve outside dest (zip-slip).

    zipfile sanitises names on extraction too; an archive built to escape is
    rejected as a whole rather than trusted for its other members.
    """
    root = dest.resolve()
    for name in zf.namelist():
        resolved = (dest / name).resolve()
        if resolved != root and not resolved.is_relative_to(root):
            raise ImportFailure(f"unsafe ZIP entry rejected: {name!r}")


def _is_part_file(member: zipfile.ZipInfo) -> bool:
    parts = PurePosixPath(member.filename.replace("\\", "/")).parts
    return (
        not member.is_dir()
        and not any(p.startswith(".") or p == "__MACOSX" for p in parts)
        and member.filename.lower().endswith(_PART_SUFFIXES)
    )


def _require_readable(member: zipfile.ZipInfo) -> None:
    if member.flag_bits & _ENCRYPTED_FLAG:
        raise ImportFailure(
            f"{member.filename} is encrypted; password-protected ZIPs are not supported"
        )
    if member.compress_type not in _SUPPORTED_COMPRESSION:
        raise ImportFailure(
            f"{member.filename} uses unsupported compression method "
            f"{member.compress_type}"
        )
