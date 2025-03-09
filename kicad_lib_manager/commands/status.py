"""
Status command implementation for KiCad Library Manager.
"""

import json
import yaml
from pathlib import Path
import click

from ..library_manager import find_kicad_config, list_configured_libraries
from ..config import Config
from ..utils.metadata import read_github_metadata, read_cloud_metadata


@click.command()
def status():
    """Show the current KiCad configuration status"""
    try:
        # Show KILM configuration first
        try:
            config_file = Path.home() / ".config" / "kicad-lib-manager" / "config.yaml"
            if config_file.exists():
                click.echo("KILM Configuration:")
                try:
                    with open(config_file, "r") as f:
                        config_data = yaml.safe_load(f)
                    
                    # Show libraries
                    if "libraries" in config_data and config_data["libraries"]:
                        click.echo("  Configured Libraries:")
                        
                        # Group by type
                        github_libs = [lib for lib in config_data["libraries"] if lib.get("type") == "github"]
                        cloud_libs = [lib for lib in config_data["libraries"] if lib.get("type") == "cloud"]
                        
                        if github_libs:
                            click.echo("    GitHub Libraries (symbols/footprints):")
                            for lib in github_libs:
                                name = lib.get("name", "unnamed")
                                path = lib.get("path", "unknown")
                                current = " (current)" if config_data.get("current_library") == path else ""
                                click.echo(f"      - {name}: {path}{current}")
                                
                                # Check if metadata file exists
                                try:
                                    if read_github_metadata(Path(path)):
                                        click.echo(f"        Metadata: Yes")
                                except Exception:
                                    pass
                        
                        if cloud_libs:
                            click.echo("    Cloud Libraries (3D models):")
                            for lib in cloud_libs:
                                name = lib.get("name", "unnamed")
                                path = lib.get("path", "unknown")
                                current = " (current)" if config_data.get("current_library") == path else ""
                                click.echo(f"      - {name}: {path}{current}")
                                
                                # Check if metadata file exists
                                try:
                                    if read_cloud_metadata(Path(path)):
                                        click.echo(f"        Metadata: Yes")
                                except Exception:
                                    pass
                    else:
                        click.echo("  No libraries configured")
                    
                    # Show current library
                    if "current_library" in config_data and config_data["current_library"]:
                        click.echo(f"  Current Library: {config_data['current_library']}")
                    else:
                        click.echo("  No current library set")
                    
                    # Show other settings
                    if "max_backups" in config_data:
                        click.echo(f"  Max Backups: {config_data['max_backups']}")
                    
                except Exception as e:
                    click.echo(f"  Error reading configuration: {e}", err=True)
            else:
                click.echo("No KILM configuration file found. Run 'kilm init' to create one.")
        except Exception as e:
            click.echo(f"Error reading KILM configuration: {e}", err=True)
            
        click.echo("\n--- KiCad Configuration ---")
        
        kicad_config = find_kicad_config()
        click.echo(f"KiCad configuration directory: {kicad_config}")
        
        # Check environment variables in KiCad common
        kicad_common = kicad_config / "kicad_common.json"
        if kicad_common.exists():
            try:
                with open(kicad_common, "r") as f:
                    common_config = json.load(f)
                
                click.echo("\nEnvironment Variables in KiCad:")
                if "environment" in common_config and "vars" in common_config["environment"]:
                    env_vars = common_config["environment"]["vars"]
                    if env_vars:
                        for key, value in env_vars.items():
                            click.echo(f"  {key} = {value}")
                    else:
                        click.echo("  No environment variables set")
                else:
                    click.echo("  No environment variables found")
            except Exception as e:
                click.echo(f"  Error reading KiCad common configuration: {e}", err=True)
        
        # Check pinned libraries
        check_pinned_libraries(kicad_config)
        
        # Check configured libraries
        try:
            sym_libs, fp_libs = list_configured_libraries(kicad_config)
            
            click.echo("\nConfigured Symbol Libraries:")
            if sym_libs:
                for lib in sym_libs:
                    lib_name = lib["name"]
                    lib_uri = lib["uri"]
                    click.echo(f"  - {lib_name}: {lib_uri}")
            else:
                click.echo("  No symbol libraries configured")
            
            click.echo("\nConfigured Footprint Libraries:")
            if fp_libs:
                for lib in fp_libs:
                    lib_name = lib["name"]
                    lib_uri = lib["uri"]
                    click.echo(f"  - {lib_name}: {lib_uri}")
            else:
                click.echo("  No footprint libraries configured")
        except Exception as e:
            click.echo(f"Error listing configured libraries: {e}", err=True)
    
    except Exception as e:
        click.echo(f"Error getting KiCad configuration: {e}", err=True)


def check_pinned_libraries(kicad_config):
    """Check and display pinned libraries"""
    # First look in kicad_common.json
    kicad_common = kicad_config / "kicad_common.json"
    if kicad_common.exists():
        try:
            with open(kicad_common, "r") as f:
                common_config = json.load(f)
            
            found_pinned = False
            click.echo("\nPinned Libraries in KiCad:")
            
            # Check for pinned symbol libraries
            if "session" in common_config and "pinned_symbol_libs" in common_config["session"]:
                sym_libs = common_config["session"]["pinned_symbol_libs"]
                if sym_libs:
                    found_pinned = True
                    click.echo("  Symbol Libraries:")
                    for lib in sym_libs:
                        click.echo(f"    - {lib}")
            
            # Check for pinned footprint libraries
            if "session" in common_config and "pinned_fp_libs" in common_config["session"]:
                fp_libs = common_config["session"]["pinned_fp_libs"]
                if fp_libs:
                    found_pinned = True
                    click.echo("  Footprint Libraries:")
                    for lib in fp_libs:
                        click.echo(f"    - {lib}")
            
            if not found_pinned:
                click.echo("  No pinned libraries found in kicad_common.json")
                
            return
        except Exception as e:
            click.echo(f"  Error reading pinned libraries from kicad_common.json: {e}", err=True)
    
    # Fall back to the old method of looking for a separate pinned file
    pinned_libs = kicad_config / "pinned"
    if pinned_libs.exists():
        try:
            with open(pinned_libs, "r") as f:
                pinned_config = json.load(f)
            
            click.echo("\nPinned Libraries in KiCad (legacy format):")
            found_pinned = False
            
            if "pinned_symbol_libs" in pinned_config:
                sym_libs = pinned_config["pinned_symbol_libs"]
                if sym_libs:
                    found_pinned = True
                    click.echo("  Symbol Libraries:")
                    for lib in sym_libs:
                        click.echo(f"    - {lib}")
            
            if "pinned_footprint_libs" in pinned_config:
                fp_libs = pinned_config["pinned_footprint_libs"]
                if fp_libs:
                    found_pinned = True
                    click.echo("  Footprint Libraries:")
                    for lib in fp_libs:
                        click.echo(f"    - {lib}")
            
            if not found_pinned:
                click.echo("  No pinned libraries found")
        except Exception as e:
            click.echo(f"  Error reading pinned libraries: {e}", err=True)
    else:
        click.echo("\nNo pinned libraries file found") 