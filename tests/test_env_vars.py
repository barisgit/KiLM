import json
import pytest
from pathlib import Path
from kicad_lib_manager.utils.env_vars import update_kicad_env_vars

def test_update_kicad_env_vars(tmp_path):
    """Test updating environment variables in KiCad configuration."""
    # Create a temporary KiCad configuration directory
    kicad_config = tmp_path / "kicad"
    kicad_config.mkdir()
    
    # Create a test kicad_common.json file
    kicad_common = kicad_config / "kicad_common.json"
    initial_config = {
        "environment": {
            "vars": {
                "EXISTING_VAR": "/existing/path"
            }
        }
    }
    with open(kicad_common, "w") as f:
        json.dump(initial_config, f)
    
    # Test 1: Update with valid environment variables
    env_vars = {
        "KICAD_USER_LIB": "/path/to/lib",
        "KICAD_3D_LIB": "/path/to/3d"
    }
    changes = update_kicad_env_vars(kicad_config, env_vars)
    assert changes is True
    
    # Verify the changes
    with open(kicad_common, "r") as f:
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
    env_vars_with_none = {
        "KICAD_USER_LIB": None,
        "KICAD_3D_LIB": "/path/to/3d"
    }
    changes = update_kicad_env_vars(kicad_config, env_vars_with_none)
    assert changes is True  # Changes should be True because we're removing KICAD_USER_LIB
    
    # Verify KICAD_USER_LIB was removed and KICAD_3D_LIB remains unchanged
    with open(kicad_common, "r") as f:
        config = json.load(f)
    assert "KICAD_USER_LIB" not in config["environment"]["vars"]
    assert config["environment"]["vars"]["KICAD_3D_LIB"] == "/path/to/3d"
    
    # Test 5: Update with empty strings
    env_vars_with_empty = {
        "KICAD_USER_LIB": "",
        "KICAD_3D_LIB": "   "  # whitespace only
    }
    changes = update_kicad_env_vars(kicad_config, env_vars_with_empty)
    assert changes is False
    
    # Test 6: Update with mixed valid and invalid values
    env_vars_mixed = {
        "KICAD_USER_LIB": "/new/path",
        "KICAD_3D_LIB": None,
        "INVALID_VAR": "",
        "ANOTHER_VAR": "   "  # whitespace only
    }
    changes = update_kicad_env_vars(kicad_config, env_vars_mixed)
    assert changes is True
    
    # Verify only valid values were updated
    with open(kicad_common, "r") as f:
        config = json.load(f)
    assert config["environment"]["vars"]["KICAD_USER_LIB"] == "/new/path"
    assert "KICAD_3D_LIB" not in config["environment"]["vars"]
    assert "INVALID_VAR" not in config["environment"]["vars"]
    assert "ANOTHER_VAR" not in config["environment"]["vars"]
    
    # Test 7: Dry run mode
    env_vars_new = {
        "KICAD_USER_LIB": "/another/path"
    }
    changes = update_kicad_env_vars(kicad_config, env_vars_new, dry_run=True)
    assert changes is True
    
    # Verify no changes were made in dry run mode
    with open(kicad_common, "r") as f:
        config = json.load(f)
    assert config["environment"]["vars"]["KICAD_USER_LIB"] == "/new/path"
    
    # Test 8: Non-existent config file
    with pytest.raises(FileNotFoundError):
        update_kicad_env_vars(Path("/nonexistent"), env_vars)
    
    # Test 9: Invalid JSON in config file
    with open(kicad_common, "w") as f:
        f.write("invalid json")
    
    with pytest.raises(ValueError):
        update_kicad_env_vars(kicad_config, env_vars)