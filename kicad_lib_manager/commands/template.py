"""
Template commands implementation for KiCad Library Manager.
Provides commands for creating KiCad projects from templates and creating templates from projects.
"""

import os
import sys
import click
import yaml
import json
import shutil
import importlib.util
import traceback
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import jinja2
import pathspec
import questionary

from ..config import Config
from ..utils.template import (
    TEMPLATES_DIR,
    TEMPLATE_METADATA,
    TEMPLATE_CONTENT_DIR,
    HOOKS_DIR,
    POST_CREATE_HOOK,
    get_gitignore_spec,
    list_templates_in_directory,
    find_potential_variables,
    create_template_metadata,
    write_template_metadata,
    create_template_structure,
    render_template_string,
    render_filename,
    find_all_templates,
    render_template_file,
    create_project_from_template,
    run_post_create_hook
)


@click.group()
def template():
    """Manage KiCad project templates.
    
    This command group allows you to create new KiCad projects from templates,
    and create new templates from existing projects.
    """
    pass


@template.command()
@click.argument("name", required=False)
@click.argument("directory", required=False, type=click.Path())
@click.option(
    "--template",
    help="Name of the template to use",
    default=None,
)
@click.option(
    "--library",
    help="Name of the library containing the template",
    default=None,
)
@click.option(
    "--set-var",
    multiple=True,
    help="Set template variable in key=value format",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Show what would be created without making changes",
    show_default=True,
)
@click.option(
    "--skip-hooks",
    is_flag=True,
    default=False,
    help="Skip post-creation hooks",
    show_default=True,
)
def create(name, directory, template, library, set_var, dry_run, skip_hooks):
    """Create a new KiCad project from a template.
    
    Creates a new KiCad project from a template in one of the configured libraries.
    If NAME is provided, it will be used as the project name. If DIRECTORY is provided,
    the project will be created in that directory. Otherwise, it will be created
    in the current directory.
    
    If NAME contains a path separator, it will be treated as a directory path
    and the name will be extracted from the last part of the path.
    
    Examples:
    
    \b
    # Create a project named 'MyProject' in the current directory
    kilm template create MyProject
    
    \b
    # Create a project in a specific directory
    kilm template create MyProject path/to/project
    
    \b
    # Create a project using a full path
    kilm template create path/to/project/MyProject
    
    \b
    # Create a project using a specific template
    kilm template create MyProject --template basic-project
    
    \b
    # Set template variables
    kilm template create MyProject --set-var author="John Doe" --set-var version=1.0
    """
    config = Config()
    
    # Find all available templates
    all_templates = find_all_templates(config)
    
    if not all_templates:
        click.echo("No templates found in any configured libraries.")
        click.echo("Use 'kilm template make' to create a template first.")
        return
    
    # Parse name and directory
    if name and os.path.sep in name:
        # Name contains a path separator, treat it as a path
        path = Path(name)
        directory = str(path.parent)
        name = path.name
    
    # If directory is provided but name is not, extract name from directory
    if directory and not name:
        path = Path(directory)
        name = path.name
        directory = str(path.parent)
    
    # Use current directory if not specified
    if not directory:
        directory = os.getcwd()
    
    # Convert to Path objects
    project_dir = Path(directory)
    
    # Interactive selection of template if not specified
    selected_template = None
    if template:
        # Use the specified template if it exists
        if template in all_templates:
            selected_template = all_templates[template]
        else:
            # Try case-insensitive match
            template_lower = template.lower()
            for t_name, t_data in all_templates.items():
                if t_name.lower() == template_lower:
                    selected_template = t_data
                    break
            
            if not selected_template:
                click.echo(f"Template '{template}' not found.")
                click.echo("Available templates:")
                for t_name, t_data in all_templates.items():
                    library = t_data.get("source_library", "unknown")
                    description = t_data.get("description", "")
                    click.echo(f"  {t_name} ({library}): {description}")
                return
    else:
        # Interactive template selection using questionary
        template_choices = [
            questionary.Choice(
                title=f"{t_name} ({t_data.get('source_library', 'unknown')}) - {t_data.get('description', '')}", 
                value=t_name # Use template name as the value
            )
            for t_name, t_data in all_templates.items()
        ]
        
        selected_template_name = questionary.select(
            "Select template:",
            choices=template_choices,
            use_shortcuts=True
        ).ask()
        
        if selected_template_name is None: # Handle cancellation
            click.echo("Template selection cancelled.")
            return
            
        selected_template = all_templates.get(selected_template_name)
    
    # Ensure selected_template is not None before proceeding
    if not selected_template:
         click.echo("Error: No template selected.", err=True)
         return

    # Get template directory
    template_path_str = selected_template.get("path")
    if not template_path_str:
        click.echo(f"Error: Template metadata for '{selected_template.get('name')}' is missing the 'path'.", err=True)
        return
    template_dir = Path(template_path_str)
    
    # Load template metadata
    metadata_file = template_dir / TEMPLATE_METADATA
    try:
        with open(metadata_file, "r") as f:
            metadata = yaml.safe_load(f)
        if not metadata: # Handle empty metadata file
             click.echo(f"Warning: Template metadata file is empty: {metadata_file}", err=True)
             metadata = {} # Use empty dict to avoid downstream errors
    except Exception as e:
        click.echo(f"Error reading template metadata {metadata_file}: {e}", err=True)
        return
    
    # Get template variables from metadata
    template_variables = metadata.get("variables", {})
    
    # --- Variable Processing ---
    variables = {} # Final variables dictionary
    command_line_vars = {} # Variables set via --set-var

    # Parse --set-var options first
    for var in set_var:
        if "=" in var:
            key, value = var.split("=", 1)
            command_line_vars[key.strip()] = value.strip()

    # Set project_name if provided as argument 'name'
    if name:
        # Only set project_name if it's defined in template or not already set via --set-var
        if "project_name" in template_variables and "project_name" not in command_line_vars:
             variables["project_name"] = name
        elif "project_name" not in template_variables and "project_name" not in command_line_vars:
             # If project_name is not an official template var, still use it if provided
             variables["project_name"] = name
             # Optionally add a warning if it's not a defined variable?
             # click.echo(f"Warning: 'project_name' used but not defined in template variables.", err=True)

    # Show template info
    click.echo()
    click.echo(f"Using Template: {metadata.get('name', 'Unknown')}")
    click.echo(f"Description: {metadata.get('description', 'N/A')}")
    if metadata.get('use_case'):
        click.echo(f"Use case: {metadata.get('use_case')}")
        
    click.echo()
    click.echo("Template Variables:")
    
    # Combine initial variables from args and --set-var
    variables.update(command_line_vars)

    # Sequentially prompt for variables not already provided
    for var_name, var_info in template_variables.items():
        if var_name in variables:
            # Variable already provided, echo its value
            description = var_info.get("description", f"Value for {var_name}")
            source = "argument" if var_name == "project_name" and name and "project_name" not in command_line_vars else "--set-var"
            if var_name in command_line_vars or (var_name == "project_name" and name):
                 click.echo(f"  {var_name}: {variables[var_name]} (from {source}) - {description}")
            continue # Skip prompting

        # Variable not provided, prompt the user
        description = var_info.get("description", f"Value for {var_name}")
        default = var_info.get("default", "")
        
        # Render the default value using already known variables
        rendered_default = default
        if default and "{{" in default and "}}" in default:
            try:
                # Use the 'variables' dict which now contains previously entered answers
                rendered_default = render_template_string(default, variables)
            except jinja2.exceptions.UndefinedError as e:
                 # If a variable needed for the default hasn't been entered yet,
                 # keep the original template string or empty if undefined errors occur early
                 click.echo(f"Debug: Undefined variable for default of {var_name}: {e}. Default might be incomplete.", err=True)
                 rendered_default = "" # Or keep 'default'? Better to show empty than half-rendered?
            except Exception as e:
                click.echo(f"Warning: Could not render default for {var_name}: {e}", err=True)
                rendered_default = default # Use original default on other errors

        # Ask the question using questionary.text
        answer = questionary.text(
            f"{var_name} ({description})",
            default=rendered_default,
            # Add validation if needed, e.g., lambda text: len(text) > 0 or "Value cannot be empty"
        ).ask()

        if answer is None: # Handle Ctrl+C or cancellation
            click.echo("Variable input cancelled.")
            return # Exit the command gracefully

        # Store the answer for use in subsequent default renderings
        variables[var_name] = answer

    # --- End Variable Processing ---

    # --- Post-process defaults for dependent variables ---
    # Store original defaults that were templates
    original_template_defaults = {}
    for var_name, var_info in template_variables.items():
        default = var_info.get("default", "")
        if default and "{{" in default and "}}" in default:
            original_template_defaults[var_name] = default
    
    # Re-render defaults for variables that might not have been rendered correctly initially
    # and update the value if the user accepted the (potentially incorrect) default.
    for var_name, original_default_template in original_template_defaults.items():
        # Check if the variable exists in the final variables set
        if var_name in variables:
            # Calculate the default that was likely *shown* to the user
            # (rendered only with prefilled vars available *before* the prompt)
            try:
                shown_default = render_template_string(original_default_template, variables)
            except Exception:
                shown_default = original_default_template # Fallback if initial render failed

            # Render the default correctly using *all* collected variables
            try:
                correct_default = render_template_string(original_default_template, variables)
            except Exception as e:
                 click.echo(f"Warning: Could not re-render default for {var_name}: {e}", err=True)
                 correct_default = variables[var_name] # Keep existing value on error

            # If the user's final answer matches the *shown* default (meaning they didn't change it),
            # update it with the *correctly* rendered default.
            if variables[var_name] == shown_default and variables[var_name] != correct_default:
                click.echo(f"Updating default for '{var_name}': '{shown_default}' -> '{correct_default}'")
                variables[var_name] = correct_default
    # --- End Post-processing ---

    click.echo()
    click.echo(f"Final variables: {json.dumps(variables, indent=2)}") # Changed message for clarity

    # --- Determine Final Project Directory ---
    final_project_dir = None
    directory_name_template = template_variables.get("directory_name", {}).get("default", "")
    directory_name_value = variables.get("directory_name", "")

    # Try using the 'directory_name' variable value if it exists and is not just the template string
    if directory_name_value and directory_name_value != directory_name_template:
        final_project_dir = project_dir / directory_name_value
    elif directory_name_template and "{{" in directory_name_template:
         # If value wasn't provided/prompted, try rendering the default template
        try:
            dir_name_rendered = render_template_string(directory_name_template, variables)
            final_project_dir = project_dir / dir_name_rendered
            # Store the rendered value back into variables for consistency?
            # variables["directory_name"] = dir_name_rendered
        except Exception as e:
            click.echo(f"Warning: Could not render default directory_name '{directory_name_template}': {e}", err=True)
            # Fallback below
    
    # Fallback to using project_name variable if directory_name failed or wasn't conclusive
    if not final_project_dir and "project_name" in variables:
         project_name_sanitized = variables["project_name"].lower().replace(" ", "-")
         final_project_dir = project_dir / project_name_sanitized
         click.echo(f"Using project_name to determine directory: {final_project_dir}")

    # Final check if we have a directory
    if not final_project_dir:
         click.echo("Error: Cannot determine project directory. Ensure 'project_name' or 'directory_name' variable is properly handled.", err=True)
         return
    # --- End Directory Determination ---

    click.echo()
    click.echo(f"Project will be created in: {final_project_dir}")

    # --- Execution ---
    if dry_run:
        click.echo("Dry run enabled. No changes will be made.")
        # Optionally, list files that *would* be created here
    else:
        # Check if target directory exists and handle overwrite
        if final_project_dir.exists():
            if not click.confirm(f"Directory '{final_project_dir}' already exists. Overwrite?"):
                click.echo("Aborted.")
                return
            else:
                click.echo(f"Removing existing directory: {final_project_dir}")
                try:
                    shutil.rmtree(final_project_dir)
                except Exception as e:
                    click.echo(f"Error removing existing directory: {e}", err=True)
                    return
        
        # Create parent directories if they don't exist
        try:
             final_project_dir.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
             click.echo(f"Error creating parent directories for {final_project_dir}: {e}", err=True)
             return


    # Create project from template using the utility function
    try:
        success = create_project_from_template(
            template_dir=template_dir,
            project_dir=final_project_dir,
            variables=variables,
            dry_run=dry_run,
            skip_hooks=skip_hooks,
            metadata=metadata # Pass metadata for post-hook if needed
        )
    except Exception as e:
         click.echo(f"Error during project creation: {e}", err=True)
         traceback.print_exc() # Print traceback for debugging
         success = False


    if success:
        if not dry_run:
             click.echo()
             click.echo(f"Project '{variables.get('project_name', name)}' created successfully in '{final_project_dir}'")
    else:
        click.echo()
        click.echo("Project creation failed.", err=True)


@template.command()
@click.argument("name", required=False)
@click.argument("source_directory", required=False, type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option(
    "--description",
    help="Template description",
    default=None,
)
@click.option(
    "--use-case",
    help="Template use case description",
    default=None,
)
@click.option(
    "--output-directory",
    help="Directory where the template will be created",
    type=click.Path(),
    default=None,
)
@click.option(
    "--exclude",
    multiple=True,
    help="Additional patterns to exclude (gitignore format)",
)
@click.option(
    "--variable",
    multiple=True,
    help="Define a template variable in name=value format",
)
@click.option(
    "--extends",
    help="Parent template that this template extends",
    default=None,
)
@click.option(
    "--non-interactive",
    is_flag=True,
    default=False,
    help="Non-interactive mode (don't prompt for variables or configuration)",
    show_default=True,
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Show what would be created without making changes",
    show_default=True,
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Overwrite existing template if it exists",
    show_default=True,
)
def make(name, source_directory, description, use_case, output_directory, exclude, 
         variable, extends, non_interactive, dry_run, force):
    """Create a template from an existing project.
    
    Creates a new KiCad project template from an existing project. If NAME
    is provided, it will be used as the template name. If SOURCE_DIRECTORY is
    provided, it will be used as the source project directory. Otherwise,
    the current directory will be used.
    
    By default, the command runs in interactive mode, automatically identifying potential
    template variables and prompting for confirmation. Use --non-interactive to disable prompts.
    
    Examples:
    
    \b
    # Create a template named 'basic-project' from the current directory
    kilm template make basic-project
    
    \b
    # Create a template from a specific directory
    kilm template make basic-project path/to/project
    
    \b
    # Create a template with a description and use case
    kilm template make basic-project --description "Basic KiCad project" \\
        --use-case "Starting point for simple PCB designs"
    
    \b
    # Create a template with variables
    kilm template make basic-project --variable "author=John Doe"
    
    \b
    # Create a template without prompts
    kilm template make basic-project --non-interactive
    
    \b
    # Create a template that extends another template
    kilm template make advanced-project --extends basic-project
    """
    # Get available libraries for later use
    config = Config()
    all_libraries = config.get_libraries(library_type="github")  # Only get GitHub libraries
    library_names = [lib["name"] for lib in all_libraries]
    library_paths = {lib["name"]: lib["path"] for lib in all_libraries}
    
    if not library_names:
        click.echo("No GitHub libraries configured. Use 'kilm init' to create one first.")
        sys.exit(1)
    
    # Set interactive mode - now the default is True, and --non-interactive makes it False
    interactive = not non_interactive
    
    # If interactive mode, prompt for missing values
    if interactive:
        # Ask for source directory if not specified
        if not source_directory:
            default_dir = os.getcwd()
            source_dir_input = click.prompt(
                "Source project directory",
                default=default_dir
            )
            # Handle relative paths
            if not os.path.isabs(source_dir_input):
                source_directory = os.path.join(os.getcwd(), source_dir_input)
            else:
                source_directory = source_dir_input
        
        # Ask for template name if not specified
        if not name:
            default_name = os.path.basename(source_directory)
            name = click.prompt("Template name", default=default_name)
        
        # Ask for description and use case if not specified
        if not description:
            description = click.prompt("Template description", default=f"{name} template")
        if not use_case:
            use_case = click.prompt("Template use case", default="")
        
        # Ask for output directory if not specified
        if not output_directory:
            # Show numbered list of libraries
            click.echo("\nChoose a library to store the template:")
            for i, lib_name in enumerate(library_names):
                click.echo(f"{i+1}. {lib_name} ({library_paths[lib_name]})")
            
            # Get selection
            while True:
                try:
                    lib_selection = click.prompt(
                        "Select library (number)",
                        type=int,
                        default=1
                    )
                    if 1 <= lib_selection <= len(library_names):
                        selected_lib = library_names[lib_selection-1]
                        library_path = library_paths[selected_lib]
                        break
                    else:
                        click.echo(f"Please enter a number between 1 and {len(library_names)}")
                except ValueError:
                    click.echo("Please enter a valid number")
            
            output_directory = Path(library_path) / TEMPLATES_DIR / name
            click.echo(f"Template will be created in: {output_directory}")
    else:
        # Non-interactive mode - use current directory if not specified
        if not source_directory:
            source_directory = os.getcwd()
        
        # If name is not provided, use the directory name
        if not name:
            name = os.path.basename(source_directory)
        
        # Determine the output directory
        if not output_directory:
            # Find the library to add the template to
            library_path = config.get_symbol_library_path()
            if not library_path:
                click.echo("No library configured. Use 'kilm init' to create one first.")
                return
            
            output_directory = Path(library_path) / TEMPLATES_DIR / name
    
    # Convert source_directory to Path object
    source_directory = Path(source_directory)
    
    # Check if template already exists
    if output_directory and Path(output_directory).exists() and not force:
        click.echo(f"Template '{name}' already exists at {output_directory}")
        click.echo("Use --force to overwrite.")
        return
    
    # Get gitignore spec
    gitignore_spec = get_gitignore_spec(source_directory)
    
    # Show what we're going to do
    click.echo(f"Creating template '{name}' from {source_directory}")
    click.echo(f"Output directory: {output_directory}")
    
    if description:
        click.echo(f"Description: {description}")
    if use_case:
        click.echo(f"Use case: {use_case}")
    if exclude:
        click.echo("Additional exclusions:")
        for pattern in exclude:
            click.echo(f"  {pattern}")
    if extends:
        click.echo(f"Extends: {extends}")
    
    # Parse variables from command line
    variable_dict = {}
    for var in variable:
        if "=" in var:
            key, value = var.split("=", 1)
            variable_dict[key.strip()] = {
                "description": f"Value for {key.strip()}",
                "default": value.strip()
            }
    
    if variable_dict:
        click.echo("\nTemplate variables:")
        for key, value in variable_dict.items():
            click.echo(f"  {key}: {value['default']} - {value['description']}")
    
    # If interactive mode is enabled, scan for potential variables
    detected_variables = {}
    if interactive:
        potential_vars = find_potential_variables(source_directory)
        if potential_vars:
            click.echo("\nFound potential template variables:")
            for var_name, values in potential_vars.items():
                value_str = ", ".join(values)
                click.echo(f"  {var_name}: {value_str}")
                
                # Ask if the user wants to use this variable
                if click.confirm(f"  Use '{var_name}' as a template variable?", default=True):
                    # Use the first value as default
                    default_value = values[0] if values else ""
                    description = click.prompt("  Description", default=f"Value for {var_name}")
                    
                    detected_variables[var_name] = {
                        "description": description,
                        "default": default_value
                    }
        
        # Always ask if the user wants to define additional variables
        while click.confirm("Would you like to define additional template variables?", default=False):
            var_name = click.prompt("Variable name")
            var_default = click.prompt("Default value", default="")
            var_description = click.prompt("Description", default=f"Value for {var_name}")
            
            detected_variables[var_name] = {
                "description": var_description,
                "default": var_default
            }
    
    # Merge manual and detected variables, with manual taking precedence
    variables = {**detected_variables, **variable_dict}
    
    # Create metadata
    metadata = create_template_metadata(
        name=name,
        directory=source_directory,
        description=description,
        use_case=use_case,
        variables=variables,
        extends=extends,
        dependencies=None
    )
    
    # Preview what will be included
    if dry_run:
        # Get the list of files that would be included
        included_files = []
        excluded_files = []
        
        additional_spec = None
        if exclude:
            additional_spec = pathspec.PathSpec.from_lines('gitwildmatch', exclude)
        
        for root, dirs, files in os.walk(source_directory):
            rel_root = os.path.relpath(root, source_directory)
            if rel_root == ".":
                rel_root = ""
            
            # Skip directories that should be excluded
            dirs_to_remove = []
            for d in dirs:
                rel_path = os.path.join(rel_root, d)
                # Ensure proper gitignore path format for directories
                git_path = rel_path.replace(os.sep, "/")
                if not git_path.endswith("/"):
                    git_path += "/"
                
                if gitignore_spec and gitignore_spec.match_file(git_path):
                    dirs_to_remove.append(d)
                    excluded_files.append(f"{rel_path}/")
                elif additional_spec and additional_spec.match_file(git_path):
                    dirs_to_remove.append(d)
                    excluded_files.append(f"{rel_path}/")
                    
            for d in dirs_to_remove:
                dirs.remove(d)
            
            # Check files
            for file in files:
                rel_path = os.path.join(rel_root, file)
                # Ensure proper gitignore path format
                git_path = rel_path.replace(os.sep, "/")
                
                # Skip gitignored files and additional excluded files
                if gitignore_spec and gitignore_spec.match_file(git_path):
                    excluded_files.append(rel_path)
                    continue
                if additional_spec and additional_spec.match_file(git_path):
                    excluded_files.append(rel_path)
                    continue
                
                included_files.append(rel_path)
        
        # Sort and display
        included_files.sort()
        excluded_files.sort()
        
        click.echo("\nFiles that will be included in the template:")
        for file in included_files:
            click.echo(f"  + {file}")
        
        # Show which Markdown files will be templated
        md_files = [f for f in included_files if f.lower().endswith('.md')]
        if md_files:
            click.echo("\nMarkdown files that will be converted to Jinja templates:")
            for file in md_files:
                click.echo(f"  * {file}")
        
        # Show which KiCad project files will be templated
        kicad_files = [f for f in included_files if f.lower().endswith(('.kicad_pro', '.kicad_sch', '.kicad_pcb'))]
        if kicad_files:
            click.echo("\nKiCad project files that will be templated:")
            for file in kicad_files:
                # Show the templated filename that will be used
                if file.lower().endswith('.kicad_pro'):
                    templated_name = "{{ project_filename }}.kicad_pro"
                elif file.lower().endswith('.kicad_sch'):
                    templated_name = "{{ project_filename }}.kicad_sch"
                elif file.lower().endswith('.kicad_pcb'):
                    templated_name = "{{ project_filename }}.kicad_pcb"
                else:
                    templated_name = file
                
                click.echo(f"  * {file} → {templated_name}")
        
        click.echo("\nFiles that will be excluded from the template:")
        for file in excluded_files:
            click.echo(f"  - {file}")
    
    # If this is a dry run, stop here
    if dry_run:
        click.echo("\nDry run complete. No changes were made.")
        return
    
    # Create the template
    try:
        # Create the template directory structure
        os.makedirs(output_directory, exist_ok=True)
        
        # Create template structure with special handling for Markdown files
        create_template_structure(
            source_directory=source_directory,
            template_directory=output_directory,
            metadata=metadata,
            gitignore_spec=gitignore_spec,
            additional_excludes=exclude or None
        )
        
        click.echo(f"\nTemplate '{name}' created successfully at {output_directory}")
        
        # Add hints for next steps
        click.echo("\nNext steps:")
        click.echo(f"1. Edit {output_directory / TEMPLATE_METADATA} to customize template metadata")
        click.echo(f"2. Customize template files in {output_directory / TEMPLATE_CONTENT_DIR}")
        click.echo(f"3. Edit post-creation hook in {output_directory / HOOKS_DIR / POST_CREATE_HOOK} if needed")
        click.echo(f"4. Use your template with: kilm template create MyProject --template {name}")
    
    except Exception as e:
        click.echo(f"Error creating template: {str(e)}", err=True)
        traceback.print_exc()
        sys.exit(1)


@template.command()
@click.option(
    "--library",
    help="Filter templates by library name",
    default=None,
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    default=False,
    help="Show detailed information including variables",
    show_default=True,
)
@click.option(
    "--json",
    is_flag=True,
    default=False,
    help="Output in JSON format",
    show_default=True,
)
def list_templates_cmd(library, verbose, json):
    """List all available templates.
    
    Displays all available templates across all configured libraries,
    with their descriptions, source libraries, and other metadata.
    
    Examples:
    
    \b
    # List all templates
    kilm template list
    
    \b
    # List templates with detailed information
    kilm template list --verbose
    
    \b
    # List templates from a specific library
    kilm template list --library my-library
    
    \b
    # Output template list in JSON format
    kilm template list --json
    """
    config = Config()
    
    # Find all available templates
    all_templates = find_all_templates(config)
    
    if not all_templates:
        click.echo("No templates found in any configured libraries.")
        click.echo("Use 'kilm template make' to create a template first.")
        return
    
    # Filter by library if requested
    if library:
        all_templates = {name: data for name, data in all_templates.items() 
                         if data.get("source_library", "").lower() == library.lower()}
        
        if not all_templates:
            click.echo(f"No templates found in library '{library}'.")
            return
    
    # If JSON output is requested
    if json:
        import json as json_lib
        click.echo(json_lib.dumps(all_templates, indent=2))
        return
    
    # Group templates by library for display
    templates_by_library = {}
    for name, data in all_templates.items():
        lib_name = data.get("source_library", "Unknown")
        if lib_name not in templates_by_library:
            templates_by_library[lib_name] = []
        templates_by_library[lib_name].append((name, data))
    
    # Display templates
    click.echo("Available Templates:")
    click.echo("===================")
    click.echo()
    
    for lib_name, templates in templates_by_library.items():
        click.echo(f"Library: {lib_name}")
        click.echo("-" * (len(lib_name) + 9))
        
        for name, data in sorted(templates):
            description = data.get("description", "No description")
            use_case = data.get("use_case", "")
            version = data.get("version", "1.0.0")
            
            click.echo()
            click.echo(f"- {name} (v{version})")
            click.echo(f"  Description: {description}")
            
            if use_case:
                click.echo(f"  Use Case: {use_case}")
                
            if data.get("extends"):
                click.echo(f"  Extends: {data.get('extends')}")
            
            # Show variables if verbose
            if verbose:
                variables = data.get("variables", {})
                if variables:
                    click.echo()
                    click.echo("  Variables:")
                    for var_name, var_info in variables.items():
                        var_desc = var_info.get("description", "")
                        var_default = var_info.get("default", "")
                        click.echo(f"    {var_name}: {var_desc} (default: '{var_default}')")
                
                # Show dependencies if present
                dependencies = data.get("dependencies", {})
                if dependencies:
                    recommended = dependencies.get("recommended", [])
                    if recommended:
                        click.echo()
                        click.echo("  Recommended Dependencies:")
                        for dep in recommended:
                            click.echo(f"    - {dep}")
            
            click.echo("")  # Empty line between templates
        
        click.echo("")  # Empty line between libraries
    
    # Show count
    click.echo(f"Total: {len(all_templates)} template(s) found")


# Register the template command
if __name__ == "__main__":
    template() 