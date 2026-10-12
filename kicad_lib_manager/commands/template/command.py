"""Template commands implementation for KiCad Library Manager.
Provides commands for creating KiCad projects from templates and creating templates from projects.
"""

# PEP 810: on Python 3.15+ these imports load on first use.
__lazy_modules__ = {"jinja2", "pathspec", "questionary", "yaml"}

import json
import os
import shutil
import sys
import traceback
from pathlib import Path
from typing import Annotated

import jinja2
import pathspec
import questionary
import typer
import yaml
from rich.panel import Panel
from rich.table import Table

from kicad_lib_manager.utils.console import get_console

from ...services.config_service import Config
from ...utils.template import (
    FILENAME_VAR_PATTERN,
    HOOKS_DIR,
    POST_CREATE_HOOK,
    TEMPLATE_CONTENT_DIR,
    TEMPLATE_METADATA,
    TEMPLATES_DIR,
    TemplateVariable,
    create_project_from_template,
    create_template_metadata,
    create_template_structure,
    find_all_templates,
    find_potential_variables,
    get_gitignore_spec,
    render_template_string,
)


def main_callback() -> None:
    """Manage KiCad project templates.

    This command group allows you to create new KiCad projects from templates,
    and create new templates from existing projects.
    """


def create(
    name: Annotated[
        str | None, typer.Argument(help="Name of the project to create")
    ] = None,
    directory: Annotated[
        str | None, typer.Argument(help="Directory to create project in")
    ] = None,
    template: Annotated[
        str | None, typer.Option(help="Name of the template to use")
    ] = None,
    library: Annotated[
        str | None, typer.Option(help="Name of the library containing the template")
    ] = None,
    set_var: Annotated[
        list[str] | None,
        typer.Option("--set-var", help="Set template variable in key=value format"),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run", help="Show what would be created without making changes"
        ),
    ] = False,
    skip_hooks: Annotated[
        bool, typer.Option("--skip-hooks", help="Skip post-creation hooks")
    ] = False,
) -> None:
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
    all_templates = find_all_templates(config, library)

    if not all_templates:
        where = f"library '{library}'" if library else "any configured libraries"
        get_console().print(f"No templates found in {where}.")
        get_console().print("Use 'kilm template make' to create a template first.")
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
        directory = str(Path.cwd())

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
                get_console().print(f"Template '{template}' not found.")
                get_console().print("Available templates:")
                for t_name, t_data in all_templates.items():
                    source = t_data.get("source_library", "unknown")
                    description = t_data.get("description", "")
                    get_console().print(f"  {t_name} ({source}): {description}")
                return
    else:
        # Interactive template selection using questionary
        template_choices = [
            questionary.Choice(
                title=f"{t_name} ({t_data.get('source_library', 'unknown')}) - {t_data.get('description', '')}",
                value=t_name,  # Use template name as the value
            )
            for t_name, t_data in all_templates.items()
        ]

        selected_template_name = questionary.select(
            "Select template:", choices=template_choices, use_shortcuts=True
        ).ask()

        if selected_template_name is None:  # Handle cancellation
            get_console().print("Template selection cancelled.")
            return

        selected_template = all_templates.get(selected_template_name)

    # Ensure selected_template is not None before proceeding
    if not selected_template:
        get_console().print("[red]Error: No template selected.[/red]")
        return

    # Get template directory
    template_path_str = selected_template.get("path")
    if not template_path_str:
        get_console(stderr=True).print(
            f"Error: Template metadata for '{selected_template.get('name')}' is missing the 'path'."
        )
        return
    template_dir = Path(template_path_str)

    # Load template metadata
    metadata_file = template_dir / TEMPLATE_METADATA
    try:
        with metadata_file.open() as f:
            metadata = yaml.safe_load(f)
        if not metadata:  # Handle empty metadata file
            get_console(stderr=True).print(
                f"Warning: Template metadata file is empty: {metadata_file}"
            )
            metadata = {}  # Use empty dict to avoid downstream errors
    except Exception as e:
        get_console(stderr=True).print(
            f"Error reading template metadata {metadata_file}: {e}"
        )
        return

    # Get template variables from metadata
    template_variables = metadata.get("variables", {})

    # --- Variable Processing ---
    variables = {}  # Final variables dictionary
    command_line_vars = {}  # Variables set via --set-var

    # Parse --set-var options first
    for var in set_var or []:
        if "=" in var:
            key, value = var.split("=", 1)
            command_line_vars[key.strip()] = value.strip()

    # Set project_name if provided as argument 'name'
    if name:
        # Only set project_name if it's defined in template or not already set via --set-var
        if (
            "project_name" in template_variables
            and "project_name" not in command_line_vars
        ):
            variables["project_name"] = name
        elif (
            "project_name" not in template_variables
            and "project_name" not in command_line_vars
        ):
            # If project_name is not an official template var, still use it if provided
            variables["project_name"] = name

    # Show template info
    get_console().print()
    get_console().print(f"Using Template: {metadata.get('name', 'Unknown')}")
    get_console().print(f"Description: {metadata.get('description', 'N/A')}")
    if metadata.get("use_case"):
        get_console().print(f"Use case: {metadata.get('use_case')}")

    get_console().print()
    get_console().print("Template Variables:")

    # Combine initial variables from args and --set-var
    variables.update(command_line_vars)

    # Sequentially prompt for variables not already provided
    for var_name, var_info in template_variables.items():
        if var_name in variables:
            # Variable already provided, echo its value
            description = var_info.get("description", f"Value for {var_name}")
            source = (
                "argument"
                if var_name == "project_name"
                and name
                and "project_name" not in command_line_vars
                else "--set-var"
            )
            if var_name in command_line_vars or (var_name == "project_name" and name):
                get_console().print(
                    f"  {var_name}: {variables[var_name]} (from {source}) - {description}"
                )
            continue  # Skip prompting

        # Variable not provided, prompt the user
        description = var_info.get("description", f"Value for {var_name}")
        default = var_info.get("default", "")

        # Render the default value using already known variables
        rendered_default = default
        if default and (
            ("{{" in default and "}}" in default)
            or FILENAME_VAR_PATTERN.search(default)
        ):
            try:
                # Use the 'variables' dict which now contains previously entered answers
                rendered_default = render_template_string(default, variables)
            except jinja2.exceptions.UndefinedError as e:
                # If a variable needed for the default hasn't been entered yet,
                # keep the original template string or empty if undefined errors occur early
                get_console(stderr=True).print(
                    f"Debug: Undefined variable for default of {var_name}: {e}. Default might be incomplete."
                )
                rendered_default = (
                    ""  # Or keep 'default'? Better to show empty than half-rendered?
                )
            except Exception as e:
                get_console(stderr=True).print(
                    f"Warning: Could not render default for {var_name}: {e}"
                )
                rendered_default = default  # Use original default on other errors

        # Ask the question using questionary.text
        answer = questionary.text(
            f"{var_name} ({description})",
            default=rendered_default,
            # Add validation if needed, e.g., lambda text: len(text) > 0 or "Value cannot be empty"
        ).ask()

        if answer is None:  # Handle Ctrl+C or cancellation
            get_console().print("Variable input cancelled.")
            return  # Exit the command gracefully

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
                shown_default = render_template_string(
                    original_default_template, variables
                )
            except Exception:
                shown_default = (
                    original_default_template  # Fallback if initial render failed
                )

            # Render the default correctly using *all* collected variables
            try:
                correct_default = render_template_string(
                    original_default_template, variables
                )
            except Exception as e:
                get_console(stderr=True).print(
                    f"Warning: Could not re-render default for {var_name}: {e}"
                )
                correct_default = variables[var_name]  # Keep existing value on error

            # If the user's final answer matches the *shown* default (meaning they didn't change it),
            # update it with the *correctly* rendered default.
            if (
                variables[var_name] == shown_default
                and variables[var_name] != correct_default
            ):
                get_console().print(
                    f"Updating default for '{var_name}': '{shown_default}' -> '{correct_default}'"
                )
                variables[var_name] = correct_default
    # --- End Post-processing ---

    get_console().print()
    get_console().print(
        f"Final variables: {json.dumps(variables, indent=2)}"
    )  # Changed message for clarity

    # --- Determine Final Project Directory ---
    final_project_dir = None
    directory_name_template = template_variables.get("directory_name", {}).get(
        "default", ""
    )
    directory_name_value = variables.get("directory_name", "")

    # Try using the 'directory_name' variable value if it exists and is not just the template string
    if directory_name_value and directory_name_value != directory_name_template:
        final_project_dir = project_dir / directory_name_value
    elif directory_name_template and "{{" in directory_name_template:
        # If value wasn't provided/prompted, try rendering the default template
        try:
            dir_name_rendered = render_template_string(
                directory_name_template, variables
            )
            final_project_dir = project_dir / dir_name_rendered
        except Exception as e:
            get_console(stderr=True).print(
                f"Warning: Could not render default directory_name '{directory_name_template}': {e}"
            )
            # Fallback below

    # Fallback to using project_name variable if directory_name failed or wasn't conclusive
    if not final_project_dir and "project_name" in variables:
        project_name_sanitized = variables["project_name"].lower().replace(" ", "-")
        final_project_dir = project_dir / project_name_sanitized
        get_console().print(
            f"Using project_name to determine directory: {final_project_dir}"
        )

    # Final check if we have a directory
    if not final_project_dir:
        get_console(stderr=True).print(
            "Error: Cannot determine project directory. Ensure 'project_name' or 'directory_name' variable is properly handled."
        )
        return
    # --- End Directory Determination ---

    get_console().print()
    get_console().print(f"Project will be created in: {final_project_dir}")

    # --- Execution ---
    if dry_run:
        get_console().print("Dry run enabled. No changes will be made.")
        # Optionally, list files that *would* be created here
    else:
        # Check if target directory exists and handle overwrite
        if final_project_dir.exists():
            if not typer.confirm(
                f"Directory '{final_project_dir}' already exists. Overwrite?"
            ):
                get_console().print("Aborted.")
                return
            get_console().print(f"Removing existing directory: {final_project_dir}")
            try:
                shutil.rmtree(final_project_dir)
            except Exception as e:
                get_console(stderr=True).print(
                    f"Error removing existing directory: {e}"
                )
                return

        # Create parent directories if they don't exist
        try:
            final_project_dir.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            get_console(stderr=True).print(
                f"Error creating parent directories for {final_project_dir}: {e}"
            )
            return

    # Create project from template using the utility function
    try:
        # Check if template uses old Jinja2 syntax in filenames and warn Windows users
        if os.name == "nt":  # Windows
            template_content_dir = template_dir / TEMPLATE_CONTENT_DIR
            if template_content_dir.exists():
                old_syntax_files = []
                for _root, _dirs, files in os.walk(template_content_dir):
                    for file in files:
                        if "{{" in file and "}}" in file:
                            old_syntax_files.append(file)

                if old_syntax_files:
                    get_console().print()
                    get_console(stderr=True).print(
                        "WARNING: Windows Compatibility Notice:"
                    )
                    get_console(stderr=True).print(
                        "This template uses the old {{variable}} syntax in filenames, which may not work on Windows."
                    )
                    get_console(stderr=True).print(
                        "Consider updating the template to use the new Windows-compatible %{variable} syntax."
                    )
                    get_console(stderr=True).print("Files with old syntax:")
                    for file in old_syntax_files[:3]:  # Show first 3 files
                        get_console(stderr=True).print(f"  - {file}")
                    if len(old_syntax_files) > 3:
                        get_console(stderr=True).print(
                            f"  ... and {len(old_syntax_files) - 3} more"
                        )
                    get_console().print()
                    get_console(stderr=True).print("New syntax examples:")
                    get_console(stderr=True).print("  - %{project_name}.kicad_pro")
                    get_console(stderr=True).print(
                        "  - %{project_name.lower}.kicad_sch"
                    )
                    get_console(stderr=True).print(
                        "  - %{project_name.replace(' ', '-')}.kicad_pcb"
                    )
                    get_console().print()

        success = create_project_from_template(
            template_dir=template_dir,
            project_dir=final_project_dir,
            variables=variables,
            dry_run=dry_run,
            skip_hooks=skip_hooks,
            metadata=metadata,  # Pass metadata for post-hook if needed
        )
    except Exception as e:
        get_console(stderr=True).print(f"Error during project creation: {e}")
        traceback.print_exc()  # Print traceback for debugging
        success = False

    if success:
        if not dry_run:
            get_console().print()
            get_console().print(
                f"Project '{variables.get('project_name', name)}' created successfully in '{final_project_dir}'"
            )
    else:
        get_console().print()
        get_console(stderr=True).print("Project creation failed.")


def make(
    name: Annotated[
        str | None, typer.Argument(help="Name of the template to create")
    ] = None,
    source_directory: Annotated[
        Path | None, typer.Argument(help="Source project directory")
    ] = None,
    description: Annotated[
        str | None, typer.Option(help="Template description")
    ] = None,
    use_case: Annotated[
        str | None, typer.Option("--use-case", help="Template use case description")
    ] = None,
    output_directory: Annotated[
        Path | None,
        typer.Option(
            "--output-directory", help="Directory where the template will be created"
        ),
    ] = None,
    exclude: Annotated[
        list[str] | None,
        typer.Option(help="Additional patterns to exclude (gitignore format)"),
    ] = None,
    variable: Annotated[
        list[str] | None,
        typer.Option(help="Define a template variable in name=value format"),
    ] = None,
    extends: Annotated[
        str | None, typer.Option(help="Parent template that this template extends")
    ] = None,
    non_interactive: Annotated[
        bool,
        typer.Option(
            "--non-interactive",
            help="Non-interactive mode (don't prompt for variables or configuration)",
        ),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run", help="Show what would be created without making changes"
        ),
    ] = False,
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite existing template if it exists")
    ] = False,
) -> None:
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
    all_libraries = config.get_libraries(
        library_type="github"
    )  # Only get GitHub libraries
    library_names = [lib["name"] for lib in all_libraries]
    library_paths = {lib["name"]: lib["path"] for lib in all_libraries}

    if not library_names:
        get_console().print(
            "No GitHub libraries configured. Use 'kilm init' to create one first."
        )
        sys.exit(1)

    # Set interactive mode - now the default is True, and --non-interactive makes it False
    interactive = not non_interactive

    # If interactive mode, prompt for missing values
    if interactive:
        # Ask for source directory if not specified
        if not source_directory:
            default_dir = str(Path.cwd())
            source_dir_input = typer.prompt(
                "Source project directory", default=default_dir
            )
            # Handle relative paths
            if not Path(source_dir_input).is_absolute():
                source_directory = Path.cwd() / source_dir_input
            else:
                source_directory = Path(source_dir_input)

        # Ask for template name if not specified
        if not name:
            default_name = source_directory.name if source_directory else "template"
            name = typer.prompt("Template name", default=default_name)

        # Ask for description and use case if not specified
        if not description:
            description = typer.prompt(
                "Template description", default=f"{name} template"
            )
        if not use_case:
            use_case = typer.prompt("Template use case", default="")

        # Ask for output directory if not specified
        if not output_directory:
            # Show numbered list of libraries
            get_console().print("\nChoose a library to store the template:")
            for i, lib_name in enumerate(library_names):
                get_console().print(f"{i + 1}. {lib_name} ({library_paths[lib_name]})")

            # Get selection
            while True:
                try:
                    lib_selection = typer.prompt(
                        "Select library (number)", type=int, default=1
                    )
                    if 1 <= lib_selection <= len(library_names):
                        selected_lib = library_names[lib_selection - 1]
                        library_path = library_paths[selected_lib]
                        break
                    get_console().print(
                        f"Please enter a number between 1 and {len(library_names)}"
                    )
                except ValueError:
                    get_console().print("Please enter a valid number")

            output_directory = Path(library_path) / TEMPLATES_DIR / name
            get_console().print(f"Template will be created in: {output_directory}")
    else:
        # Non-interactive mode - use current directory if not specified
        if not source_directory:
            source_directory = Path.cwd()

        # If name is not provided, use the directory name
        if not name:
            name = source_directory.name

        # Determine the output directory
        if not output_directory:
            # Find the library to add the template to
            library_path = config.get_symbol_library_path()
            if not library_path:
                get_console().print(
                    "No library configured. Use 'kilm init' to create one first."
                )
                return

            output_directory = Path(library_path) / TEMPLATES_DIR / name

    # Ensure source_directory is a Path object
    if source_directory is None:
        source_directory = Path.cwd()
    elif not isinstance(source_directory, Path):
        source_directory = Path(source_directory)

    # Check if template already exists
    if output_directory and output_directory.exists() and not force:
        get_console().print(f"Template '{name}' already exists at {output_directory}")
        get_console().print("Use --force to overwrite.")
        return

    # Get gitignore spec
    gitignore_spec = get_gitignore_spec(source_directory)

    # Show what we're going to do
    get_console().print(f"Creating template '{name}' from {source_directory}")
    get_console().print(f"Output directory: {output_directory}")

    if description:
        get_console().print(f"Description: {description}")
    if use_case:
        get_console().print(f"Use case: {use_case}")
    if exclude:
        get_console().print("Additional exclusions:")
        for pattern in exclude:
            get_console().print(f"  {pattern}")
    if extends:
        get_console().print(f"Extends: {extends}")

    # Parse variables from command line
    variable_dict: dict[str, TemplateVariable] = {}
    for var in variable or []:
        if "=" in var:
            key, value = var.split("=", 1)
            variable_dict[key.strip()] = {
                "description": f"Value for {key.strip()}",
                "default": value.strip(),
            }

    if variable_dict:
        get_console().print("\nTemplate variables:")
        for key, value in variable_dict.items():
            get_console().print(f"  {key}: {value['default']} - {value['description']}")

    # If interactive mode is enabled, scan for potential variables
    detected_variables: dict[str, TemplateVariable] = {}
    if interactive:
        potential_vars = find_potential_variables(source_directory)
        if potential_vars:
            get_console().print("\nFound potential template variables:")
            for var_name, values in potential_vars.items():
                value_str = ", ".join(values)
                get_console().print(f"  {var_name}: {value_str}")

                # Ask if the user wants to use this variable
                if typer.confirm(
                    f"  Use '{var_name}' as a template variable?", default=True
                ):
                    # Use the first value as default
                    default_value = values[0] if values else ""
                    var_description = typer.prompt(
                        "  Description", default=f"Value for {var_name}"
                    )

                    detected_variables[var_name] = {
                        "description": var_description,
                        "default": default_value,
                    }

        # Always ask if the user wants to define additional variables
        while typer.confirm(
            "Would you like to define additional template variables?", default=False
        ):
            var_name = typer.prompt("Variable name")
            var_default = typer.prompt("Default value", default="")
            var_description = typer.prompt(
                "Description", default=f"Value for {var_name}"
            )

            detected_variables[var_name] = {
                "description": var_description,
                "default": var_default,
            }

    # Merge manual and detected variables, with manual taking precedence
    variables = {**detected_variables, **variable_dict}

    # Create metadata
    metadata = create_template_metadata(
        name=name,
        description=description,
        use_case=use_case,
        variables=variables,
        extends=extends,
        dependencies=None,
    )

    # Preview what will be included
    if dry_run:
        # Get the list of files that would be included
        included_files = []
        excluded_files = []

        additional_spec = None
        if exclude:
            additional_spec = pathspec.PathSpec.from_lines("gitwildmatch", exclude)

        for root, dirs, files in os.walk(source_directory):
            rel_root = os.path.relpath(root, source_directory)
            if rel_root == ".":
                rel_root = ""

            # Skip directories that should be excluded
            dirs_to_remove = []
            for d in dirs:
                rel_path = str(Path(rel_root) / d) if rel_root else d
                # Ensure proper gitignore path format for directories
                git_path = rel_path.replace(os.sep, "/")
                if not git_path.endswith("/"):
                    git_path += "/"

                if (gitignore_spec and gitignore_spec.match_file(git_path)) or (
                    additional_spec and additional_spec.match_file(git_path)
                ):
                    dirs_to_remove.append(d)
                    excluded_files.append(f"{rel_path}/")

            for d in dirs_to_remove:
                dirs.remove(d)

            # Check files
            for file in files:
                rel_path = str(Path(rel_root) / file) if rel_root else file
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

        get_console().print("\nFiles that will be included in the template:")
        for file in included_files:
            get_console().print(f"  + {file}")

        # Show which Markdown files will be templated
        md_files = [f for f in included_files if f.lower().endswith(".md")]
        if md_files:
            get_console().print(
                "\nMarkdown files that will be converted to Jinja templates:"
            )
            for file in md_files:
                get_console().print(f"  * {file}")

        # Show which KiCad project files will be templated
        kicad_files = [
            f
            for f in included_files
            if f.lower().endswith((".kicad_pro", ".kicad_sch", ".kicad_pcb"))
        ]
        if kicad_files:
            get_console().print("\nKiCad project files that will be templated:")
            for file in kicad_files:
                # Show the templated filename that will be used
                if file.lower().endswith(".kicad_pro"):
                    templated_name = "%{project_filename}.kicad_pro"
                elif file.lower().endswith(".kicad_sch"):
                    templated_name = "%{project_filename}.kicad_sch"
                elif file.lower().endswith(".kicad_pcb"):
                    templated_name = "%{project_filename}.kicad_pcb"
                else:
                    templated_name = file

                get_console().print(f"  * {file} → {templated_name}")

        get_console().print("\nFiles that will be excluded from the template:")
        for file in excluded_files:
            get_console().print(f"  - {file}")

    # If this is a dry run, stop here
    if dry_run:
        get_console().print("\nDry run complete. No changes were made.")
        return

    # Create the template
    try:
        # Create the template directory structure
        if output_directory:
            output_directory.mkdir(parents=True, exist_ok=True)

        # Create template structure with special handling for Markdown files
        create_template_structure(
            source_directory=source_directory,
            template_directory=output_directory,
            metadata=metadata,
            gitignore_spec=gitignore_spec,
            additional_excludes=exclude or None,
        )

        get_console().print(
            f"\nTemplate '{name}' created successfully at {output_directory}"
        )

        # Add hints for next steps
        get_console().print("\nNext steps:")
        get_console().print(
            f"1. Edit {output_directory / TEMPLATE_METADATA if output_directory else 'N/A'} to customize template metadata"
        )
        get_console().print(
            f"2. Customize template files in {output_directory / TEMPLATE_CONTENT_DIR if output_directory else 'N/A'}"
        )
        get_console().print(
            f"3. Edit post-creation hook in {output_directory / HOOKS_DIR / POST_CREATE_HOOK if output_directory else 'N/A'} if needed"
        )
        get_console().print(
            f"4. Use your template with: kilm template create MyProject --template {name}"
        )

        # Add information about filename templating syntax
        get_console().print("\nFilename Templating:")
        get_console().print(
            "For Windows compatibility, use %{variable} syntax in filenames:"
        )
        get_console().print("  - %{project_name}.kicad_pro")
        get_console().print("  - %{project_name.lower}.kicad_sch")
        get_console().print("  - %{project_name.replace(' ', '-')}.kicad_pcb")
        get_console().print("  - %{project_name.upper.replace(' ', '_')}.md")
        get_console().print(
            "(Old {{variable}} syntax still works but may cause issues on Windows)"
        )

    except Exception as e:
        get_console(stderr=True).print(f"Error creating template: {e!s}")
        traceback.print_exc()
        sys.exit(1)


def list_templates(
    library: Annotated[
        str | None, typer.Option(help="Filter templates by library name")
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option(
            "-v", "--verbose", help="Show detailed information including variables"
        ),
    ] = False,
    json_output: Annotated[
        bool, typer.Option("--json", help="Output in JSON format")
    ] = False,
) -> None:
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
    all_templates = find_all_templates(config, library)

    if not all_templates and library:
        get_console().print()
        get_console().print(
            Panel(
                f"[yellow]No templates found in library '[cyan]{library}[/cyan]'.[/yellow]\n\n"
                "[cyan]💡 Try:[/cyan]\n"
                f"• List all libraries: [blue]kilm list-libraries[/blue]\n"
                f"• Create template in '{library}': [blue]kilm template make --library {library}[/blue]\n"
                "• List all templates: [blue]kilm template list[/blue]",
                title="[bold yellow]⚠️ No Templates Found[/bold yellow]",
                border_style="yellow",
            )
        )
        return

    if not all_templates:
        get_console().print()
        get_console().print(
            Panel(
                "[yellow]No templates found in any configured libraries.[/yellow]\n\n"
                "[cyan]💡 Get Started:[/cyan]\n"
                "• Create a template: [blue]kilm template make[/blue]\n"
                "• Check library configuration: [blue]kilm list-libraries[/blue]",
                title="[bold yellow]⚠️ No Templates[/bold yellow]",
                border_style="yellow",
            )
        )
        return

    # If JSON output is requested
    if json_output:
        # Plain echo: a Rich console would wrap long values and break the JSON.
        typer.echo(json.dumps(all_templates, indent=2))
        return

    # Group templates by library for display
    templates_by_library = {}
    for name, data in all_templates.items():
        lib_name = data.get("source_library", "Unknown")
        if lib_name not in templates_by_library:
            templates_by_library[lib_name] = []
        templates_by_library[lib_name].append((name, data))

    # Display templates in Rich tables organized by library
    get_console().print()

    for lib_name, templates in templates_by_library.items():
        # Create a table for each library
        table = Table(
            title=f"[bold cyan]{lib_name}[/bold cyan] Templates",
            show_header=True,
            header_style="bold magenta",
            border_style="cyan",
        )

        table.add_column("Template", style="cyan", no_wrap=True)
        table.add_column("Version", justify="center", style="blue", width=8)
        table.add_column("Description", style="green")

        if verbose:
            table.add_column("Variables", style="yellow", max_width=30)
            table.add_column("Extends", style="magenta", max_width=15)

        # Add rows for each template
        for name, data in sorted(templates):
            description = data.get("description", "No description")
            version = data.get("version", "1.0.0")
            extends = data.get("extends", "")

            row_data = [f"[bold]{name}[/bold]", version, description]

            if verbose:
                # Format variables for display
                variables = data.get("variables", {})
                var_display = ""
                if variables:
                    var_list = [f"{k}" for k in variables]
                    var_display = ", ".join(var_list[:3])  # Show first 3 variables
                    if len(var_list) > 3:
                        var_display += f", +{len(var_list) - 3} more"
                else:
                    var_display = "[dim]None[/dim]"

                row_data.append(var_display)
                row_data.append(extends or "[dim]None[/dim]")

            table.add_row(*row_data)

        get_console().print(table)
        get_console().print()

    # Add usage hint panel
    hint_content = (
        "[cyan]Usage:[/cyan] kilm template create <name> --template <template_name>\n"
    )
    hint_content += "[cyan]Verbose:[/cyan] kilm template list --verbose\n"
    hint_content += "[cyan]Filter:[/cyan] kilm template list --library <library_name>"

    get_console().print(
        Panel(
            hint_content,
            title="[bold blue]💡 Quick Tips[/bold blue]",
            border_style="blue",
        )
    )
    # Add summary panel
    library_count = len(templates_by_library)
    template_count = len(all_templates)

    summary_content = f"[green]Libraries:[/green] {library_count}\n"
    summary_content += f"[green]Templates:[/green] {template_count}"

    get_console().print(
        Panel(
            summary_content,
            title="[bold cyan]📊 Summary[/bold cyan]",
            border_style="cyan",
            width=30,
        )
    )


# Register the template command
if __name__ == "__main__":
    main_callback()
