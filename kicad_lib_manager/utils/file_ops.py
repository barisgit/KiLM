"""
File operation utilities
"""

import re
from pathlib import Path
from typing import List, Tuple


def read_file_with_encoding(file_path: Path, encodings: List[str] = None) -> str:
    """
    Read a file trying multiple encodings until successful
    
    Args:
        file_path: Path to the file to read
        encodings: List of encodings to try. Defaults to ['utf-8', 'utf-16', 'iso-8859-1']
        
    Returns:
        The file contents as a string
        
    Raises:
        UnicodeDecodeError: If none of the encodings work
    """
    if encodings is None:
        encodings = ['utf-8', 'utf-16', 'iso-8859-1']
    
    last_error = None
    for encoding in encodings:
        try:
            with open(file_path, "r", encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError as e:
            last_error = e
            continue
    
    if last_error:
        raise last_error
    return ""


def write_file_with_encoding(file_path: Path, content: str, encoding: str = 'utf-8') -> None:
    """
    Write content to a file with the specified encoding
    
    Args:
        file_path: Path to the file to write
        content: Content to write
        encoding: Encoding to use (defaults to utf-8)
    """
    with open(file_path, "w", encoding=encoding) as f:
        f.write(content)


def validate_lib_table(table_path: Path, create_if_missing: bool = True) -> None:
    """
    Validate a KiCad library table file
    
    Args:
        table_path: Path to the library table
        create_if_missing: If True, create the table if it doesn't exist
        
    Raises:
        ValueError: If the table format is invalid
    """
    # Determine table type from filename
    table_type = "fp" if table_path.name == "fp-lib-table" else "sym"
    
    # Create table if it doesn't exist
    if not table_path.exists():
        if create_if_missing:
            write_file_with_encoding(table_path, f"({table_type}_lib_table\n  (version 7)\n)\n")
        else:
            raise ValueError(f"Library table not found: {table_path}")
    
    # Read and validate content
    content = read_file_with_encoding(table_path)
    
    # Check if the content starts with the correct table type and ends with a closing parenthesis
    if not content.startswith(f"({table_type}_lib_table") or not content.rstrip().endswith(")"):
        raise ValueError(f"Invalid library table format in {table_path}")


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
    content = read_file_with_encoding(sym_table)
    
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
        
        # Write with UTF-8 encoding
        write_file_with_encoding(sym_table, "\n".join(lines) + "\n")
        
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
    content = read_file_with_encoding(fp_table)
    
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
        
        # Write with UTF-8 encoding
        write_file_with_encoding(fp_table, "\n".join(lines) + "\n")
        
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
        content = read_file_with_encoding(sym_table)
            
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
        content = read_file_with_encoding(fp_table)
            
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