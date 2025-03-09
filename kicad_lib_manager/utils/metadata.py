"""
Metadata management utilities for KiCad Library Manager.
"""

import os
import yaml
import json
from pathlib import Path
from typing import Dict, Any, Optional


# Metadata filenames
GITHUB_METADATA_FILE = "kilm.yaml"
CLOUD_METADATA_FILE = ".kilm_metadata"


def read_github_metadata(directory: Path) -> Optional[Dict[str, Any]]:
    """
    Read metadata from a GitHub library directory.
    
    Args:
        directory: Path to the GitHub library directory
        
    Returns:
        Dictionary of metadata or None if not found
    """
    metadata_file = directory / GITHUB_METADATA_FILE
    if not metadata_file.exists():
        return None
    
    try:
        with open(metadata_file, "r") as f:
            metadata = yaml.safe_load(f)
        
        if not isinstance(metadata, dict):
            return {}
            
        return metadata
    except Exception as e:
        print(f"Error reading metadata file: {e}")
        return None


def write_github_metadata(directory: Path, metadata: Dict[str, Any]) -> bool:
    """
    Write metadata to a GitHub library directory.
    
    Args:
        directory: Path to the GitHub library directory
        metadata: Dictionary of metadata to write
        
    Returns:
        True if successful, False otherwise
    """
    metadata_file = directory / GITHUB_METADATA_FILE
    
    try:
        with open(metadata_file, "w") as f:
            yaml.dump(metadata, f, default_flow_style=False)
        return True
    except Exception as e:
        print(f"Error writing metadata file: {e}")
        return False


def read_cloud_metadata(directory: Path) -> Optional[Dict[str, Any]]:
    """
    Read metadata from a cloud 3D model directory.
    
    Args:
        directory: Path to the cloud 3D model directory
        
    Returns:
        Dictionary of metadata or None if not found
    """
    metadata_file = directory / CLOUD_METADATA_FILE
    if not metadata_file.exists():
        return None
    
    try:
        with open(metadata_file, "r") as f:
            metadata = json.load(f)
        
        if not isinstance(metadata, dict):
            return {}
            
        return metadata
    except Exception as e:
        print(f"Error reading cloud metadata file: {e}")
        return None


def write_cloud_metadata(directory: Path, metadata: Dict[str, Any]) -> bool:
    """
    Write metadata to a cloud 3D model directory.
    
    Args:
        directory: Path to the cloud 3D model directory
        metadata: Dictionary of metadata to write
        
    Returns:
        True if successful, False otherwise
    """
    metadata_file = directory / CLOUD_METADATA_FILE
    
    try:
        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)
        return True
    except Exception as e:
        print(f"Error writing cloud metadata file: {e}")
        return False


def get_default_github_metadata(directory: Path) -> Dict[str, Any]:
    """
    Generate default metadata for a GitHub library.
    
    Args:
        directory: Path to the GitHub library directory
        
    Returns:
        Dictionary of metadata
    """
    # Try to get a sensible name from the directory
    name = directory.name
    
    # Look for existing folders to determine capabilities
    has_symbols = (directory / "symbols").exists()
    has_footprints = (directory / "footprints").exists()
    has_templates = (directory / "templates").exists()
    
    return {
        "name": name,
        "description": f"KiCad library {name}",
        "type": "github",
        "version": "1.0.0",
        "capabilities": {
            "symbols": has_symbols,
            "footprints": has_footprints,
            "templates": has_templates
        },
        "created_with": "kilm",
        "updated_with": "kilm"
    }


def get_default_cloud_metadata(directory: Path) -> Dict[str, Any]:
    """
    Generate default metadata for a cloud 3D model directory.
    
    Args:
        directory: Path to the cloud 3D model directory
        
    Returns:
        Dictionary of metadata
    """
    # Try to get a sensible name from the directory
    name = directory.name
    
    # Count 3D model files
    model_count = 0
    for ext in ['.step', '.stp', '.wrl', '.wings']:
        model_count += len(list(directory.glob(f'**/*{ext}')))
    
    return {
        "name": name,
        "description": f"KiCad 3D model library {name}",
        "type": "cloud",
        "version": "1.0.0",
        "model_count": model_count,
        "created_with": "kilm",
        "updated_with": "kilm"
    } 