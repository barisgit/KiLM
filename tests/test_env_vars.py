"""Tests for KiCad environment variables and pinned libraries."""

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from kicad_lib_manager.utils import env_vars
from kicad_lib_manager.utils.env_vars import (
    find_library_variable,
    update_kicad_env_vars,
    update_pinned_libraries,
)
from tests.fault_injection import fail_writes


def test_update_kicad_env_vars(tmp_path: Path) -> None:
    """Test updating environment variables in KiCad configuration."""
    # Create a temporary KiCad configuration directory
    kicad_config = tmp_path / "kicad"
    kicad_config.mkdir()

    # Create a test kicad_common.json file
    kicad_common = kicad_config / "kicad_common.json"
    initial_config = {"environment": {"vars": {"EXISTING_VAR": "/existing/path"}}}
    with Path(kicad_common).open("w") as f:
        json.dump(initial_config, f)

    # Test 1: Update with valid environment variables
    env_vars = {"KICAD_USER_LIB": "/path/to/lib", "KICAD_3D_LIB": "/path/to/3d"}
    changes = update_kicad_env_vars(kicad_config, env_vars)
    assert changes is True

    # Verify the changes
    with Path(kicad_common).open() as f:
        config = json.load(f)
    assert config["environment"]["vars"]["KICAD_USER_LIB"] == "/path/to/lib"
    assert config["environment"]["vars"]["KICAD_3D_LIB"] == "/path/to/3d"
    assert config["environment"]["vars"]["EXISTING_VAR"] == "/existing/path"

    # Test 2: Update with no changes (same values)
    changes = update_kicad_env_vars(kicad_config, env_vars)
    assert changes is False

    # Test 3: Update with empty dictionary
    changes = update_kicad_env_vars(kicad_config, {})
    assert changes is False

    # Test 4: Update with None values
    env_vars_with_none = {"KICAD_USER_LIB": None, "KICAD_3D_LIB": "/path/to/3d"}
    changes = update_kicad_env_vars(kicad_config, env_vars_with_none)
    assert (
        changes is True
    )  # Changes should be True because we're removing KICAD_USER_LIB

    # Verify KICAD_USER_LIB was removed and KICAD_3D_LIB remains unchanged
    with Path(kicad_common).open() as f:
        config = json.load(f)
    assert "KICAD_USER_LIB" not in config["environment"]["vars"]
    assert config["environment"]["vars"]["KICAD_3D_LIB"] == "/path/to/3d"

    # Test 5: Update with empty strings
    env_vars_with_empty = {
        "KICAD_USER_LIB": "",
        "KICAD_3D_LIB": "   ",  # whitespace only
    }
    changes = update_kicad_env_vars(kicad_config, env_vars_with_empty)
    assert changes is False

    # Test 6: Update with mixed valid and invalid values
    env_vars_mixed = {
        "KICAD_USER_LIB": "/new/path",
        "KICAD_3D_LIB": None,
        "INVALID_VAR": "",
        "ANOTHER_VAR": "   ",  # whitespace only
    }
    changes = update_kicad_env_vars(kicad_config, env_vars_mixed)
    assert changes is True

    # Verify only valid values were updated
    with Path(kicad_common).open() as f:
        config = json.load(f)
    assert config["environment"]["vars"]["KICAD_USER_LIB"] == "/new/path"
    assert "KICAD_3D_LIB" not in config["environment"]["vars"]
    assert "INVALID_VAR" not in config["environment"]["vars"]
    assert "ANOTHER_VAR" not in config["environment"]["vars"]

    # Test 7: Dry run mode
    env_vars_new = {"KICAD_USER_LIB": "/another/path"}
    changes = update_kicad_env_vars(kicad_config, env_vars_new, dry_run=True)
    assert changes is True

    # Verify no changes were made in dry run mode
    with Path(kicad_common).open() as f:
        config = json.load(f)
    assert config["environment"]["vars"]["KICAD_USER_LIB"] == "/new/path"

    # Test 8: Non-existent config file
    with pytest.raises(FileNotFoundError):
        update_kicad_env_vars(Path("/nonexistent"), env_vars)

    # Test 9: Invalid JSON in config file
    with Path(kicad_common).open("w") as f:
        f.write("invalid json")

    with pytest.raises(ValueError, match="Invalid JSON format"):
        update_kicad_env_vars(kicad_config, env_vars)


@pytest.mark.parametrize(
    "update",
    [
        lambda config: update_kicad_env_vars(config, {"KICAD_USER_LIB": "/new"}),
        lambda config: update_pinned_libraries(config, symbol_libs=["NewLib"]),
    ],
    ids=["env_vars", "pinned_libraries"],
)
def test_failed_write_keeps_kicad_common(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    update: Callable[[Path], bool],
) -> None:
    """A write that fails part way leaves kicad_common.json as it was."""
    kicad_common = tmp_path / "kicad_common.json"
    original = json.dumps({"environment": {"vars": {}}, "session": {}})
    kicad_common.write_text(original, encoding="utf-8")
    fail_writes(monkeypatch)

    with pytest.raises(OSError, match="No space left on device"):
        update(tmp_path)

    assert kicad_common.read_text(encoding="utf-8") == original


def test_pinning_adds_new_libraries_once(tmp_path: Path) -> None:
    """Pins are appended to those already there; repeats and dry runs write nothing."""
    kicad_common = tmp_path / "kicad_common.json"
    session = {"pinned_symbol_libs": ["Old"], "pinned_fp_libs": []}
    kicad_common.write_text(json.dumps({"session": session}), encoding="utf-8")

    assert not update_pinned_libraries(tmp_path, symbol_libs=["Old"])
    assert update_pinned_libraries(tmp_path, footprint_libs=["Fp"], dry_run=True)
    assert json.loads(kicad_common.read_text(encoding="utf-8"))["session"] == session

    assert update_pinned_libraries(
        tmp_path, symbol_libs=["New", "Old", "New"], footprint_libs=["Fp"]
    )
    assert json.loads(kicad_common.read_text(encoding="utf-8"))["session"] == {
        "pinned_symbol_libs": ["Old", "New"],
        "pinned_fp_libs": ["Fp"],
    }
    assert not update_pinned_libraries(tmp_path, symbol_libs=["New"])


class _FakeConfig:
    """A KiLM configuration whose current symbol library is library_path."""

    library_path: str | None = None

    def get_symbol_library_path(self) -> str | None:
        """The configured symbol library path."""
        return self.library_path


@pytest.fixture
def isolated_sources(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """No source defines KICAD_USER_LIB; returns the empty home directory."""
    monkeypatch.delenv("KICAD_USER_LIB", raising=False)
    monkeypatch.setattr(env_vars, "Config", _FakeConfig)
    monkeypatch.setattr(env_vars.shutil, "which", lambda _name: None)
    monkeypatch.chdir(tmp_path)
    return home


def test_sources_are_tried_in_order(
    isolated_sources: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Shell files < environment < library in cwd < KiLM configuration."""
    assert find_library_variable("KICAD_USER_LIB") is None

    (isolated_sources / ".zshrc").write_text(
        'export KICAD_USER_LIB="/from/zshrc"\n', encoding="utf-8"
    )
    assert find_library_variable("KICAD_USER_LIB") == "/from/zshrc"

    monkeypatch.setenv("KICAD_USER_LIB", "/from/environment")
    assert find_library_variable("KICAD_USER_LIB") == "/from/environment"

    (tmp_path / "kilm.yaml").write_text("name: here\n", encoding="utf-8")
    assert find_library_variable("KICAD_USER_LIB") == str(tmp_path.resolve())

    monkeypatch.setattr(_FakeConfig, "library_path", "/from/config")
    assert find_library_variable("KICAD_USER_LIB") == "/from/config"
