"""Fixtures for the import command tests: a KiLM library and a mocked config."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from .helpers import SAMPLE_SYM_LIB


@pytest.fixture(autouse=True)
def _fixed_console_width(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin terminal width so Rich doesn't wrap output lines differently per host."""
    monkeypatch.setenv("COLUMNS", "200")


@pytest.fixture
def library_tree(tmp_path: Path) -> Path:
    """A library with one symbol library, one footprint library, and kilm.yaml."""
    lib = tmp_path / "mylib"
    (lib / "symbols").mkdir(parents=True)
    (lib / "footprints" / "SAMPLELIB.pretty").mkdir(parents=True)
    (lib / "symbols" / "SAMPLELIB.kicad_sym").write_text(
        SAMPLE_SYM_LIB, encoding="utf-8"
    )
    (lib / "kilm.yaml").write_text("name: mylib\n", encoding="utf-8")
    return lib


@pytest.fixture
def mock_config(library_tree: Path, monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Config listing library_tree as the only github library; append to .libs."""
    config_mock = MagicMock()
    libs = [{"name": "mylib", "path": str(library_tree), "type": "github"}]
    config_mock.libs = libs
    config_mock.get_libraries.side_effect = lambda library_type=None: [
        lib for lib in libs if library_type in (None, lib["type"])
    ]
    monkeypatch.setattr(
        "kicad_lib_manager.commands.import_zip.command.Config", lambda: config_mock
    )
    return config_mock


@pytest.fixture
def category_tree(library_tree: Path, mock_config: MagicMock) -> Path:
    """Split library: two symbol libs, two footprint libs, a registered 3D lib."""
    (library_tree / "symbols" / "CAT_IC.kicad_sym").write_text(
        SAMPLE_SYM_LIB, encoding="utf-8"
    )
    (library_tree / "footprints" / "CAT_QFN.pretty").mkdir()
    models = library_tree / "CAT.3dshapes"
    models.mkdir()
    (models / ".kilm_metadata").write_text(
        '{"env_var": "KICAD_3D_CAT_MODELS"}', encoding="utf-8"
    )
    mock_config.libs.append({"name": "cat-3d", "path": str(models), "type": "cloud"})
    return library_tree
