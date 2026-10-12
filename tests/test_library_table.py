"""Tests for adding KiLM libraries to KiCad's library tables."""

import sys
from pathlib import Path

import pytest

from kicad_lib_manager.services.library_table import (
    DESCRIPTIONS_FILE,
    TableEntry,
    add_entries_to_table,
    add_libraries,
    format_uri,
)
from kicad_lib_manager.utils.file_ops import list_configured_libraries

EMPTY_TABLES = {
    "sym-lib-table": "(sym_lib_table\n  (version 7)\n)\n",
    "fp-lib-table": "(fp_lib_table\n  (version 7)\n)\n",
}


@pytest.mark.parametrize(
    ("base_path", "lib_type", "expected"),
    [
        ("/path/to/lib", "symbols", "/path/to/lib/symbols/test_lib.kicad_sym"),
        ("/path/to/lib", "footprints", "/path/to/lib/footprints/test_lib.pretty"),
        ("C:\\path\\to\\lib", "symbols", "C:/path/to/lib/symbols/test_lib.kicad_sym"),
        ("C:/path\\to/lib", "footprints", "C:/path/to/lib/footprints/test_lib.pretty"),
        ("KICAD_LIB", "symbols", "${KICAD_LIB}/symbols/test_lib.kicad_sym"),
        ("${KICAD_LIB}", "footprints", "${KICAD_LIB}/footprints/test_lib.pretty"),
        ("${/path/to/lib}", "symbols", "/path/to/lib/symbols/test_lib.kicad_sym"),
        ("/path/to /šžć ", "symbols", "/path/to /šžć /symbols/test_lib.kicad_sym"),
    ],
)
def test_format_uri(base_path: str, lib_type: str, expected: str) -> None:
    """Absolute paths stay paths with forward slashes; other bases are variables."""
    assert format_uri(base_path, "test_lib", lib_type) == expected


@pytest.mark.parametrize(
    ("base_path", "lib_type"),
    [("", "symbols"), ("/path/to/lib", "invalid_type"), ("${unclosed", "symbols")],
)
def test_format_uri_rejects_invalid_input(base_path: str, lib_type: str) -> None:
    """An empty base, unknown kind, or unclosed variable is rejected."""
    with pytest.raises(ValueError, match=r"empty|Invalid"):
        format_uri(base_path, "test_lib", lib_type)


def write_table(path: Path) -> Path:
    """Write an empty library table of the kind path's name says."""
    path.write_text(EMPTY_TABLES[path.name], encoding="utf-8")
    return path


def test_add_entries_keeps_utf8_and_unwraps_absolute_paths(tmp_path: Path) -> None:
    """Entries go before the closing parenthesis with `${/abs}` unwrapped."""
    table = write_table(tmp_path / "fp-lib-table")

    add_entries_to_table(
        table,
        [
            TableEntry("TestLib1", "${/Users/test/žćš/a.pretty}", "First"),
            TableEntry("TestLib2", "/Users/test/b.pretty", "Second"),
        ],
    )

    assert table.read_text(encoding="utf-8") == (
        "(fp_lib_table\n"
        "  (version 7)\n"
        '  (lib (name "TestLib1")(type "KiCad")(uri "/Users/test/žćš/a.pretty")'
        '(options "")(descr "First"))\n'
        '  (lib (name "TestLib2")(type "KiCad")(uri "/Users/test/b.pretty")'
        '(options "")(descr "Second"))\n'
        ")\n"
    )


def test_add_entries_escapes_quotes_and_backslashes(tmp_path: Path) -> None:
    """Quotes, backslashes, and newlines are escaped as KiCad writes them."""
    table = write_table(tmp_path / "sym-lib-table")

    add_entries_to_table(
        table, [TableEntry("Quoted", "C:\\libs\\a.kicad_sym", 'The "main"\nparts')]
    )

    content = table.read_text(encoding="utf-8")
    assert '(uri "C:\\\\libs\\\\a.kicad_sym")' in content
    assert '(descr "The \\"main\\"\\nparts")' in content


def test_written_entries_read_back_unchanged(tmp_path: Path) -> None:
    """Escaped names, URIs, and descriptions decode to what was written."""
    table = write_table(tmp_path / "sym-lib-table")
    entries = [
        TableEntry("back\\slash", "C:\\libs\\a.kicad_sym", 'The "main"\nparts\\t'),
        TableEntry('quote"d (name "x")', "/žćš/b.kicad_sym", "Ünïcode"),
    ]

    add_entries_to_table(table, entries)

    symbols, _footprints = list_configured_libraries(tmp_path)
    assert symbols == [
        {"name": e.name, "type": "KiCad", "uri": e.uri, "description": e.description}
        for e in entries
    ]


def test_reader_decodes_strings_as_kicad_does(tmp_path: Path) -> None:
    """Unquoted atoms, hex and octal bytes, and unknown escapes read like KiCad."""
    (tmp_path / "sym-lib-table").write_text(
        "(sym_lib_table\n"
        '  (lib (name "\\x41\\101\\305\\276\\q\\8")(type Legacy)(uri ${X}/a.lib)'
        '(descr "tab\\there"))\n'
        ")\n",
        encoding="utf-8",
    )

    symbols, _footprints = list_configured_libraries(tmp_path)

    assert symbols == [
        {
            "name": "AAž\\q\\8",
            "type": "Legacy",
            "uri": "${X}/a.lib",
            "description": "tab\there",
        }
    ]


def test_add_entries_requires_an_existing_table(tmp_path: Path) -> None:
    """A missing table is an error rather than created."""
    with pytest.raises(ValueError, match="not found"):
        add_entries_to_table(tmp_path / "sym-lib-table", [])


@pytest.fixture
def library(tmp_path: Path) -> Path:
    """A KiLM library with a UTF-8 named symbol and footprint library."""
    library = tmp_path / "lib_žćš"
    (library / "symbols").mkdir(parents=True)
    (library / "footprints" / "test_šž.pretty").mkdir(parents=True)
    (library / "symbols" / "test_čš.kicad_sym").touch()
    return library


@pytest.fixture
def kicad_config(tmp_path: Path) -> Path:
    """A KiCad configuration directory with empty library tables."""
    config = tmp_path / "config"
    config.mkdir()
    for name in EMPTY_TABLES:
        write_table(config / name)
    return config


def test_add_libraries_writes_new_entries_once(
    library: Path, kicad_config: Path
) -> None:
    """New libraries are added with described entries; known ones are skipped."""
    (library / DESCRIPTIONS_FILE).write_text(
        "symbols:\n  test_čš: Hand-made symbols\n", encoding="utf-8"
    )

    added, changed = add_libraries(str(library), kicad_config)

    assert added == {"test_čš", "test_šž"}
    assert changed
    symbols, footprints = list_configured_libraries(kicad_config)
    assert symbols == [
        {
            "name": "test_čš",
            "type": "KiCad",
            "uri": f"{library.as_posix()}/symbols/test_čš.kicad_sym",
            "description": "Hand-made symbols",
        }
    ]
    assert footprints[0]["description"] == "test_šž footprint library"
    assert add_libraries(str(library), kicad_config) == (set(), False)


@pytest.mark.skipif(sys.platform == "win32", reason="names a file with a backslash")
def test_backslash_named_library_is_added_once(
    tmp_path: Path, kicad_config: Path
) -> None:
    """A second setup finds the escaped entry and adds no duplicate."""
    library = tmp_path / "lib"
    (library / "symbols").mkdir(parents=True)
    (library / "symbols" / "a\\b.kicad_sym").touch()

    assert add_libraries(str(library), kicad_config) == ({"a\\b"}, True)
    assert add_libraries(str(library), kicad_config) == (set(), False)
    symbols, _footprints = list_configured_libraries(kicad_config)
    assert [entry["name"] for entry in symbols] == ["a\\b"]


@pytest.mark.parametrize("reference", ["KICAD_LIB", "${KICAD_LIB}"])
def test_add_libraries_resolves_environment_variables(
    library: Path,
    kicad_config: Path,
    monkeypatch: pytest.MonkeyPatch,
    reference: str,
) -> None:
    """A variable name, bare or in `${}`, names the library directory."""
    monkeypatch.setenv("KICAD_LIB", str(library))

    added, changed = add_libraries(reference, kicad_config, dry_run=True)

    assert added == {"test_čš", "test_šž"}
    assert changed
    assert list_configured_libraries(kicad_config) == ([], [])


def test_add_libraries_rejects_unset_variable(
    kicad_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unset variable is reported by name."""
    monkeypatch.delenv("KILM_UNSET", raising=False)

    with pytest.raises(FileNotFoundError, match="KILM_UNSET"):
        add_libraries("KILM_UNSET", kicad_config)


def test_add_libraries_checks_3d_directories(
    library: Path, kicad_config: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A missing main 3D directory fails; missing additional ones only warn."""
    missing = str(library / "missing")

    with pytest.raises(FileNotFoundError, match="3D models directory"):
        add_libraries(str(library), kicad_config, kicad_3d_dir=missing)

    add_libraries(
        str(library), kicad_config, additional_3d_dirs={"EXTRA": missing}, dry_run=True
    )
    assert "3D models directory not found" in capsys.readouterr().err


def test_add_libraries_requires_libraries(tmp_path: Path, kicad_config: Path) -> None:
    """A directory without symbols or footprints is rejected."""
    with pytest.raises(ValueError, match="No libraries found"):
        add_libraries(str(tmp_path), kicad_config)
