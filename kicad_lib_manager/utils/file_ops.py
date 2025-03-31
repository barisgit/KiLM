"""
File operation utilities
"""

import re
from pathlib import Path
from typing import List, Tuple


def validate_lib_table(table_path: Path, dry_run: bool = False) -> bool:
    """
    Validate a KiCad library table file and fix it if needed
    
    Args:
        table_path: Path to the library table file
        dry_run: If True, don't make any changes
        
    Returns:
        True if the table is valid, False otherwise
    """
    if not table_path.exists():
        if not dry_run:
            # Create a new file with the correct format
            table_type = table_path.stem.split("-")[0]
            with open(table_path, "w", encoding='utf-8') as f:
                f.write(f"({table_type}_lib_table\\n)")
        return True
    
    with open(table_path, "r", encoding='utf-8') as f:
        content = f.read()
    
    # Check if file begins with table declaration and ends with closing parenthesis
    table_type = table_path.stem.split("-")[0]
    if not re.match(rf"^\\({table_type}_lib_table", content) or not content.rstrip().endswith(")"):
        if not dry_run:
            # Fix the file, ensuring UTF-8 encoding
            with open(table_path, "w", encoding='utf-8') as f:
                f.write(f"({table_type}_lib_table\\n)")
                # Add any existing entries that might be salvageable
                lib_entries = re.findall(r"  \(lib \(name .+?\)\)", content, re.DOTALL)
                for entry in lib_entries:
                    f.write(entry + "\\n")
                f.write(")")
        return False
    
    return True


def add_symbol_lib(
    lib_name: str,
    lib_path: str,
    description: str,
    sym_table: Path,
    dry_run: bool = False,
) -> bool:
    """
    Add a symbol library to the KiCad configuration
    
    Args:
        lib_name: The name of the library
        lib_path: The path to the library file
        description: A description of the library
        sym_table: Path to the symbol library table file
        dry_run: If True, don't make any changes
        
    Returns:
        True if the library was added, False if it already exists
    """
    with open(sym_table, "r", encoding='utf-8') as f:
        content = f.read()
    
    # Check if library already exists
    if re.search(rf'\(lib \(name "{re.escape(lib_name)}"\)', content):
        return False
    
    if dry_run:
        return True
    
    # Add the library
    lines = content.splitlines()
    last_line = lines[-1]
    
    if last_line.strip() == ")":
        lines = lines[:-1]
        
        # Add the new library entry
        entry = f'  (lib (name "{lib_name}")(type "KiCad")(uri "{lib_path}")(options "")(descr "{description}"))'
        lines.append(entry)
        lines.append(")")
        
        # Ensure UTF-8 encoding when writing
        with open(sym_table, "w", encoding='utf-8') as f:
            f.write("\\n".join(lines) + "\\n")
        
        return True
    else:
        raise ValueError(f"Invalid symbol library table format: missing closing parenthesis")


def add_footprint_lib(
    lib_name: str,
    lib_path: str,
    description: str,
    fp_table: Path,
    dry_run: bool = False,
) -> bool:
    """
    Add a footprint library to the KiCad configuration
    
    Args:
        lib_name: The name of the library
        lib_path: The path to the library directory
        description: A description of the library
        fp_table: Path to the footprint library table file
        dry_run: If True, don't make any changes
        
    Returns:
        True if the library was added, False if it already exists
    """
    with open(fp_table, "r", encoding='utf-8') as f:
        content = f.read()
    
    # Check if library already exists
    if re.search(rf'\(lib \(name "{re.escape(lib_name)}"\)', content):
        return False
    
    if dry_run:
        return True
    
    # Add the library
    lines = content.splitlines()
    last_line = lines[-1]
    
    if last_line.strip() == ")":
        lines = lines[:-1]
        
        # Add the new library entry
        entry = f'  (lib (name "{lib_name}")(type "KiCad")(uri "{lib_path}")(options "")(descr "{description}"))'
        lines.append(entry)
        lines.append(")")
        
        # Ensure UTF-8 encoding when writing
        with open(fp_table, "w", encoding='utf-8') as f:
            f.write("\\n".join(lines) + "\\n")
        
        return True
    else:
        raise ValueError(f"Invalid footprint library table format: missing closing parenthesis")


def list_libraries(kicad_lib_dir: str) -> Tuple[List[str], List[str]]:
    """
    List all available libraries in the repository
    
    Args:
        kicad_lib_dir: The KiCad library directory
        
    Returns:
        A tuple of (symbol libraries, footprint libraries)
        
    Raises:
        FileNotFoundError: If the KiCad library directory is not found
    """
    kicad_lib_path = Path(kicad_lib_dir)
    
    if not kicad_lib_path.exists():
        raise FileNotFoundError(f"KiCad library directory not found at {kicad_lib_dir}")
    
    symbols = []
    footprints = []
    
    # Find symbol libraries
    symbols_dir = kicad_lib_path / "symbols"
    if symbols_dir.exists():
        symbols = [f.stem for f in symbols_dir.glob("*.kicad_sym") if f.is_file()]
    
    # Find footprint libraries
    footprints_dir = kicad_lib_path / "footprints"
    if footprints_dir.exists():
        footprints = [d.stem for d in footprints_dir.glob("*.pretty") if d.is_dir()]
    
    return symbols, footprints


def list_configured_libraries(kicad_config: Path) -> Tuple[List[dict], List[dict]]:
    """
    List all libraries currently configured in KiCad
    
    Args:
        kicad_config: Path to the KiCad configuration directory
        
    Returns:
        A tuple of (symbol libraries, footprint libraries) as lists of dictionaries
        containing library details
        
    Raises:
        FileNotFoundError: If library tables are not found
    """
    sym_table = kicad_config / "sym-lib-table"
    fp_table = kicad_config / "fp-lib-table"
    
    symbol_libs = []
    footprint_libs = []
    
    if sym_table.exists():
        with open(sym_table, "r", encoding='utf-8') as f:
            content = f.read()
            
        # Extract all library entries
        lib_entries = re.findall(r'\(lib \(name "([^"]+)"\)(.+?)\)', content, re.DOTALL)
        for name, details in lib_entries:
            lib_info = {"name": name}
            
            # Extract other properties
            uri_match = re.search(r'\(uri "([^"]+)"\)', details)
            if uri_match:
                lib_info["uri"] = uri_match.group(1)
                
            type_match = re.search(r'\(type "([^"]+)"\)', details)
            if type_match:
                lib_info["type"] = type_match.group(1)
                
            descr_match = re.search(r'\(descr "([^"]+)"\)', details)
            if descr_match:
                lib_info["description"] = descr_match.group(1)
                
            symbol_libs.append(lib_info)
    
    if fp_table.exists():
        with open(fp_table, "r", encoding='utf-8') as f:
            content = f.read()
            
        # Extract all library entries
        lib_entries = re.findall(r'\(lib \(name "([^"]+)"\)(.+?)\)', content, re.DOTALL)
        for name, details in lib_entries:
            lib_info = {"name": name}
            
            # Extract other properties
            uri_match = re.search(r'\(uri "([^"]+)"\)', details)
            if uri_match:
                lib_info["uri"] = uri_match.group(1)
                
            type_match = re.search(r'\(type "([^"]+)"\)', details)
            if type_match:
                lib_info["type"] = type_match.group(1)
                
            descr_match = re.search(r'\(descr "([^"]+)"\)', details)
            if descr_match:
                lib_info["description"] = descr_match.group(1)
                
            footprint_libs.append(lib_info)
    
    return symbol_libs, footprint_libs 