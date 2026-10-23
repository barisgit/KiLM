"""The post-creation hook that a template can run after ``template create``."""

import importlib.util
from pathlib import Path
from typing import Protocol, TypedDict, runtime_checkable

import typer

from kicad_lib_manager.utils.template.constants import POST_CREATE_HOOK
from kicad_lib_manager.utils.template.models import RenderVariables, TemplateMetadata

HOOK_MODULE_NAME = "hook"
HOOK_FUNCTION = "post_create"

# The starting point written into every new template's hooks directory. Raw, so
# the escapes in its commented examples reach the file as written.
HOOK_SCRIPT = r'''"""
Post-creation hook for template.
This script runs after the template has been used to create a new project.
"""


def post_create(context):
    """
    Hook that runs after project creation.

    Args:
        context: Dict containing:
            - project_dir: Path to the created project
            - variables: Dict of all template variables and their values
            - template: Template metadata

    Returns:
        None
    """
    # Uncomment and modify as needed
    # import subprocess
    # from pathlib import Path

    # Example: Initialize git repository
    # subprocess.run(["git", "init"], cwd=context["project_dir"], check=True)

    # Example: Create README.md if it doesn't exist
    # readme_path = Path(context["project_dir"]) / "README.md"
    # if not readme_path.exists():
    #     readme_path.write_text(
    #         f"# {context['variables']['project_name']}\n\n"
    #         "Created with KiCad Library Manager\n"
    #     )

    # Print message to user
    print(f"Project {context['variables']['project_name']} created successfully!")
    print(f"Location: {context['project_dir']}")
'''


class HookContext(TypedDict):
    """The argument passed to a template's ``post_create`` function.

    ``template`` keeps the keys of ``metadata.yaml`` that KiLM does not know,
    so a hook can read its own settings from there.
    """

    project_dir: str
    variables: RenderVariables
    template: TemplateMetadata


@runtime_checkable
class PostCreateHook(Protocol):
    """The ``post_create`` function of a hook script."""

    def __call__(self, context: HookContext, /) -> object:
        """Act on the newly created project."""
        ...


def create_hook_script(hooks_dir: Path) -> None:
    """Write the starting post-creation hook into a template's hooks directory."""
    (hooks_dir / POST_CREATE_HOOK).write_text(HOOK_SCRIPT, encoding="utf-8")


def run_post_create_hook(
    hook_script: Path,
    project_dir: Path,
    variables: RenderVariables,
    template_metadata: TemplateMetadata,
) -> None:
    """Import ``hook_script`` and call its ``post_create`` function.

    A missing script does nothing; a script that cannot be loaded or has no
    ``post_create`` function is reported on stderr. Whatever the hook raises
    propagates to the caller.
    """
    if not hook_script.exists():
        return
    spec = importlib.util.spec_from_file_location(HOOK_MODULE_NAME, hook_script)
    if spec is None or spec.loader is None:
        typer.echo(f"Error: Could not load hook script {hook_script}", err=True)
        return
    hook = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hook)
    post_create: object = getattr(hook, HOOK_FUNCTION, None)
    if not isinstance(post_create, PostCreateHook):
        typer.echo(
            f"Warning: Hook script {hook_script} does not have a post_create function",
            err=True,
        )
        return
    post_create(
        HookContext(
            project_dir=str(project_dir),
            variables=variables,
            template=template_metadata,
        )
    )
