"""
Core functionality for managing KiCad libraries
"""

import os
import platform
import re
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Set

from .utils.env_vars import find_environment_variables, expand_user_path
from .utils.backup import create_backup
from .utils.file_ops import list_libraries, list_configured_libraries


def find_kicad_config() -> Path:
    """
    Find the KiCad configuration directory for the current platform
    
    Returns:
        Path to the KiCad configuration directory
    
    Raises:
        FileNotFoundError: If KiCad configuration directory is not found
    """
    system = platform.system()
    
    if system == "Darwin":  # macOS
        config_dir = Path.home() / "Library" / "Preferences" / "kicad"
    elif system == "Linux":
        config_dir = Path.home() / ".config" / "kicad"
    elif system == "Windows":
        appdata = os.environ.get("APPDATA")
        if not appdata:
            raise FileNotFoundError("APPDATA environment variable not found")
        config_dir = Path(appdata) / "kicad"
    else:
        raise FileNotFoundError(f"Unsupported platform: {system}")
    
    if not config_dir.exists():
        raise FileNotFoundError(
            f"KiCad configuration directory not found at {config_dir}. "
            "Please run KiCad at least once before using this tool."
        )
    
    # Find the most recent KiCad version directory
    version_dirs = [d for d in config_dir.iterdir() if d.is_dir()]
    if not version_dirs:
        raise FileNotFoundError(
            f"No KiCad version directories found in {config_dir}. "
            "Please run KiCad at least once before using this tool."
        )
    
    # Sort directories by version number (assuming directories with numbers are version dirs)
    version_dirs = [d for d in version_dirs if any(c.isdigit() for c in d.name)]
    if not version_dirs:
        raise FileNotFoundError(
            f"No KiCad version directories found in {config_dir}. "
            "Please run KiCad at least once before using this tool."
        )
    
    latest_dir = sorted(version_dirs, key=lambda d: d.name)[-1]
    
    # Check for required files
    sym_table = latest_dir / "sym-lib-table"
    fp_table = latest_dir / "fp-lib-table"
    
    if not sym_table.exists() and not fp_table.exists():
        raise FileNotFoundError(
            f"KiCad library tables not found in {latest_dir}. "
            "Please run KiCad at least once before using this tool."
        )
    
    return latest_dir


def get_library_description(
    lib_type: str, lib_name: str, kicad_lib_dir: str
) -> str:
    """
    Get a description for a library from the YAML file or generate a default one
    
    Args:
        lib_type: Either 'symbols' or 'footprints'
        lib_name: The name of the library
        kicad_lib_dir: The KiCad library directory
        
    Returns:
        A description for the library
    """
    yaml_file = Path(kicad_lib_dir) / "library_descriptions.yaml"
    
    # Check if YAML file exists
    if yaml_file.exists():
        try:
            with open(yaml_file, "r") as f:
                data = yaml.safe_load(f)
                
            if data and isinstance(data, dict):
                if lib_type in data and isinstance(data[lib_type], dict):
                    if lib_name in data[lib_type]:
                        return data[lib_type][lib_name]
        except Exception:
            pass
    
    # Default description if YAML file doesn't exist or doesn't contain the library
    if lib_type == "symbols":
        return f"{lib_name} symbol library"
    else:
        return f"{lib_name} footprint library"


def add_libraries(
    kicad_lib_dir: str,
    kicad_config: Path,
    kicad_3d_dir: Optional[str] = None,
    dry_run: bool = False,
) -> Tuple[Set[str], bool]:
    """
    Add all libraries from the repository to KiCad configuration
    
    Args:
        kicad_lib_dir: The KiCad library directory
        kicad_config: The KiCad configuration directory
        kicad_3d_dir: The KiCad 3D models directory
        dry_run: If True, don't make any changes
        
    Returns:
        A tuple containing:
        - A set of added library names
        - A boolean indicating whether any changes were made
        
    Raises:
        FileNotFoundError: If required directories are not found
        ValueError: If library tables have an invalid format
    """
    from .utils.file_ops import validate_lib_table, add_symbol_lib, add_footprint_lib
    
    kicad_lib_path = Path(kicad_lib_dir)
    sym_table = kicad_config / "sym-lib-table"
    fp_table = kicad_config / "fp-lib-table"
    
    if not kicad_lib_path.exists():
        raise FileNotFoundError(f"KiCad library directory not found at {kicad_lib_dir}")
    
    # Validate library tables
    changes_made = False
    for table_path in [sym_table, fp_table]:
        if not validate_lib_table(table_path, dry_run):
            changes_made = True
            if dry_run:
                print(f"Would fix invalid library table format at {table_path}")
            else:
                print(f"Fixed invalid library table format at {table_path}")
                
    if not changes_made and any(not validate_lib_table(table_path, True) for table_path in [sym_table, fp_table]):
        # Tables need fixing but we're in dry_run mode
        changes_made = True
    
    added_libraries = set()
    
    # Add symbol libraries
    symbols_dir = kicad_lib_path / "symbols"
    if symbols_dir.exists():
        for sym_file in symbols_dir.glob("*.kicad_sym"):
            lib_name = sym_file.stem
            lib_path = str(sym_file.absolute())
            description = get_library_description("symbols", lib_name, kicad_lib_dir)
            
            if add_symbol_lib(lib_name, lib_path, description, sym_table, dry_run):
                added_libraries.add(f"symbol:{lib_name}")
                changes_made = True
    
    # Add footprint libraries
    footprints_dir = kicad_lib_path / "footprints"
    if footprints_dir.exists():
        for pretty_dir in footprints_dir.glob("*.pretty"):
            if pretty_dir.is_dir():
                lib_name = pretty_dir.stem
                lib_path = str(pretty_dir.absolute())
                description = get_library_description("footprints", lib_name, kicad_lib_dir)
                
                if add_footprint_lib(lib_name, lib_path, description, fp_table, dry_run):
                    added_libraries.add(f"footprint:{lib_name}")
                    changes_made = True
    
    return added_libraries, changes_made 