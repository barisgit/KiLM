import os
from pathlib import Path

import pytest

from kicad_lib_manager.services.library_service import LibraryService


def test_format_uri_absolute_path():
    """Test URI formatting with absolute paths."""
    # Test Unix-style paths
    assert (
        LibraryService.format_uri("/path/to/lib", "test_lib", "symbols")
        == "/path/to/lib/symbols/test_lib.kicad_sym"
    )
    assert (
        LibraryService.format_uri("/path/to/lib", "test_lib", "footprints")
        == "/path/to/lib/footprints/test_lib.pretty"
    )

    # Test Windows-style paths
    assert (
        LibraryService.format_uri("C:\\path\\to\\lib", "test_lib", "symbols")
        == "C:/path/to/lib/symbols/test_lib.kicad_sym"
    )
    assert (
        LibraryService.format_uri("C:\\path\\to\\lib", "test_lib", "footprints")
        == "C:/path/to/lib/footprints/test_lib.pretty"
    )


def test_format_uri_env_var():
    """Test URI formatting with environment variable names."""
    assert (
        LibraryService.format_uri("KICAD_LIB", "test_lib", "symbols")
        == "${KICAD_LIB}/symbols/test_lib.kicad_sym"
    )
    assert (
        LibraryService.format_uri("KICAD_LIB", "test_lib", "footprints")
        == "${KICAD_LIB}/footprints/test_lib.pretty"
    )


def test_format_uri_path_in_curly():
    """Test URI formatting with paths already in ${} format."""
    # Test absolute paths in ${}
    assert (
        LibraryService.format_uri("${/path/to/lib}", "test_lib", "symbols")
        == "/path/to/lib/symbols/test_lib.kicad_sym"
    )

    # Test environment variables in ${}
    assert (
        LibraryService.format_uri("${KICAD_LIB}", "test_lib", "symbols")
        == "${KICAD_LIB}/symbols/test_lib.kicad_sym"
    )


def test_format_uri_edge_cases():
    """Test URI formatting with edge cases."""
    # Test with empty library name
    assert (
        LibraryService.format_uri("/path/to/lib", "", "symbols")
        == "/path/to/lib/symbols/.kicad_sym"
    )

    # Test with special characters in library name
    assert (
        LibraryService.format_uri("/path/to/lib", "test-lib_123", "symbols")
        == "/path/to/lib/symbols/test-lib_123.kicad_sym"
    )

    # Test with mixed slashes
    assert (
        LibraryService.format_uri("C:/path\\to/lib", "test_lib", "symbols")
        == "C:/path/to/lib/symbols/test_lib.kicad_sym"
    )

    # Test with UTF-8 characters in path
    assert (
        LibraryService.format_uri("/path/to/šžć", "test_lib", "symbols")
        == "/path/to/šžć/symbols/test_lib.kicad_sym"
    )

    # Test with UTF-8 characters and spaces in path
    assert (
        LibraryService.format_uri("/path/to /šžć ", "test_lib", "symbols")
        == "/path/to /šžć /symbols/test_lib.kicad_sym"
    )


def test_format_uri_invalid_input():
    """Test URI formatting with invalid inputs."""
    with pytest.raises(ValueError):
        LibraryService.format_uri("", "test_lib", "symbols")  # Empty base path

    with pytest.raises(ValueError):
        LibraryService.format_uri(
            "/path/to/lib", "test_lib", "invalid_type"
        )  # Invalid library type

    with pytest.raises(ValueError):
        LibraryService.format_uri("${unclosed", "test_lib", "symbols")  # Unclosed ${


def test_add_libraries_integration(tmp_path):
    """Test the full add_libraries function with different path formats."""
    # Create temporary directories
    lib_dir = tmp_path / "lib"
    config_dir = tmp_path / "config"
    lib_dir.mkdir()
    config_dir.mkdir()

    # Create test library structure
    (lib_dir / "symbols").mkdir()
    (lib_dir / "footprints").mkdir()
    (lib_dir / "symbols" / "test_lib.kicad_sym").touch()
    (lib_dir / "footprints" / "test_lib.pretty").touch()

    # Create LibraryService instance
    service = LibraryService()

    # Test with absolute path
    added_libs, changes = service.add_libraries(str(lib_dir), config_dir, dry_run=True)
    assert "test_lib" in added_libs
    assert changes

    # Test with environment variable path - we need to set up the environment variable first
    os.environ["KICAD_LIB"] = str(lib_dir)
    added_libs, changes = service.add_libraries("KICAD_LIB", config_dir, dry_run=True)
    assert "test_lib" in added_libs
    assert changes

    # Test with path in ${} - use a proper environment variable name
    os.environ["TEST_LIB"] = str(lib_dir)
    added_libs, changes = service.add_libraries("${TEST_LIB}", config_dir, dry_run=True)
    assert "test_lib" in added_libs
    assert changes


def test_add_libraries_utf8(tmp_path):
    """Test add_libraries with UTF-8 characters in paths and filenames."""
    # Create temporary directories with UTF-8 characters
    lib_dir = tmp_path / "lib_žćš"
    config_dir = tmp_path / "config_žćš"
    lib_dir.mkdir()
    config_dir.mkdir()

    # Create test library structure with UTF-8 characters
    (lib_dir / "symbols").mkdir()
    (lib_dir / "footprints").mkdir()
    (lib_dir / "symbols" / "test_čš.kicad_sym").touch()
    (
        lib_dir / "footprints" / "test_šž.pretty"
    ).mkdir()  # Footprint libs are directories

    # Create LibraryService instance
    service = LibraryService()

    # Test adding libraries with UTF-8 paths/names
    added_libs, changes = service.add_libraries(str(lib_dir), config_dir, dry_run=True)

    # Assert that the libraries with UTF-8 names were detected
    assert "test_čš" in added_libs
    assert "test_šž" in added_libs
    assert changes


def test_add_entries_with_special_chars(tmp_path):
    """Test adding entries with special characters in paths."""
    # Create a temporary library table
    table_path = tmp_path / "fp-lib-table"
    with Path(table_path).open("w", encoding="utf-8") as f:
        f.write("(fp_lib_table\n  (version 7)\n)\n")

    # Test entries with special characters
    entries = [
        {
            "name": "TestLib1",
            "uri": "${/Users/test/žćš/footprints.pretty}",
            "options": "",
            "description": "Test library with special chars",
        },
        {
            "name": "TestLib2",
            "uri": "${/Users/test/žćš/symbols.kicad_sym}",
            "options": "",
            "description": "Another test library",
        },
    ]

    # Add entries
    LibraryService.add_entries_to_table(table_path, entries)

    # Read the updated table
    with Path(table_path).open(encoding="utf-8") as f:
        content = f.read()

    # Verify the entries were added correctly
    assert "TestLib1" in content
    assert "TestLib2" in content
    assert "/Users/test/žćš/footprints.pretty" in content
    assert "/Users/test/žćš/symbols.kicad_sym" in content
    assert "žćš" in content  # Verify special characters are preserved
