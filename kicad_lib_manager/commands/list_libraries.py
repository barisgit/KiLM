"""
List command implementation for KiCad Library Manager.
"""

import sys
import click

from ..library_manager import list_libraries
from ..utils.env_vars import find_environment_variables, expand_user_path


@click.command()
@click.option(
    "--kicad-lib-dir",
    envvar="KICAD_USER_LIB",
    help="KiCad library directory (uses KICAD_USER_LIB env var if not specified)",
)
def list_cmd(kicad_lib_dir):
    """List available libraries in the specified directory"""
    # Find environment variables if not provided
    if not kicad_lib_dir:
        kicad_lib_dir = find_environment_variables("KICAD_USER_LIB")
        if not kicad_lib_dir:
            click.echo("Error: KICAD_USER_LIB not set and not provided", err=True)
            sys.exit(1)
    
    # Expand user home directory if needed
    kicad_lib_dir = expand_user_path(kicad_lib_dir)
    
    try:
        symbols, footprints = list_libraries(kicad_lib_dir)
        
        if symbols:
            click.echo("\nAvailable Symbol Libraries:")
            for symbol in sorted(symbols):
                click.echo(f"  - {symbol}")
        else:
            click.echo("No symbol libraries found")
        
        if footprints:
            click.echo("\nAvailable Footprint Libraries:")
            for footprint in sorted(footprints):
                click.echo(f"  - {footprint}")
        else:
            click.echo("No footprint libraries found")
    except Exception as e:
        click.echo(f"Error listing libraries: {e}", err=True)
        sys.exit(1) 