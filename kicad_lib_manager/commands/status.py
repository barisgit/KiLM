"""
Status command implementation for KiCad Library Manager.
"""

import json
import click

from ..library_manager import find_kicad_config, list_configured_libraries


@click.command()
def status():
    """Show the current KiCad configuration status"""
    try:
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
        pinned_libs = kicad_config / "pinned"
        if pinned_libs.exists():
            try:
                with open(pinned_libs, "r") as f:
                    pinned_config = json.load(f)
                
                click.echo("\nPinned Libraries in KiCad:")
                if "pinned_symbol_libs" in pinned_config:
                    sym_libs = pinned_config["pinned_symbol_libs"]
                    if sym_libs:
                        click.echo("  Symbol Libraries:")
                        for lib in sym_libs:
                            click.echo(f"    - {lib}")
                
                if "pinned_footprint_libs" in pinned_config:
                    fp_libs = pinned_config["pinned_footprint_libs"]
                    if fp_libs:
                        click.echo("  Footprint Libraries:")
                        for lib in fp_libs:
                            click.echo(f"    - {lib}")
                
                if "pinned_symbol_libs" not in pinned_config and "pinned_footprint_libs" not in pinned_config:
                    click.echo("  No pinned libraries found")
            except Exception as e:
                click.echo(f"  Error reading pinned libraries: {e}", err=True)
        else:
            click.echo("\nNo pinned libraries file found")
        
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