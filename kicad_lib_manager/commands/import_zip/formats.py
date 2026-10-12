"""KiCad file format versions, which bound what an import may write into a library."""

import re
from pathlib import Path
from typing import Literal, Optional

from .errors import ImportFailure

# KiCad stamps s-expression files with "(version YYYYMMDD)". A KiCad release
# refuses files newer than the format it writes, so an import must not raise
# a shared library's format above what its users' KiCad already reads.
_FORMAT_VERSION_RE = re.compile(r"\(version\s+(\d+)\)")

# The version stamp sits in the file header; this many characters cover it.
_HEADER_CHARS = 1024


def format_version(text: str) -> Optional[int]:
    """Return the format version in a KiCad file header, None when absent."""
    m = _FORMAT_VERSION_RE.search(text[:_HEADER_CHARS])
    return int(m.group(1)) if m else None


def file_format_version(path: Path) -> Optional[int]:
    """format_version of a file, reading only its header."""
    with path.open(encoding="utf-8", errors="replace") as fh:
        return format_version(fh.read(_HEADER_CHARS))


def footprint_lib_version(fp_dir: Path) -> Optional[int]:
    """Newest format among fp_dir's footprints; None when it has none.

    Legacy (module ...) footprints carry no version and count as 0.
    """
    versions = [file_format_version(f) or 0 for f in fp_dir.glob("*.kicad_mod")]
    return max(versions, default=None)


def require_compatible(
    name: str,
    text: str,
    limit: Optional[int],
    library: Path,
    kind: Literal["sym", "fp"],
) -> None:
    """Raise ImportFailure when text's format is newer than limit.

    limit is the format of the target library (None: no limit). Merging a
    newer symbol under the library's older header makes the whole library
    unreadable for the KiCad releases that read it now, and a newer footprint
    fails to load in them. kind is the kicad-cli command group that upgrades
    the library, named in the message as the way forward.
    """
    version = format_version(text)
    if limit is None or version is None or version <= limit:
        return
    raise ImportFailure(
        f"{name} uses format {version}, newer than {library.name} ({limit}), "
        f"which KiCad releases that read the library cannot open. If every "
        f"KiCad using the library reads format {version}, run 'kicad-cli "
        f"{kind} upgrade {library}' and import again"
    )
