"""The ``template`` command group; ``template_app`` is registered by ``main``."""

from kicad_lib_manager.commands.template.command import template_app
from kicad_lib_manager.commands.template.create import create
from kicad_lib_manager.commands.template.listing import list_templates
from kicad_lib_manager.commands.template.make import make

__all__ = ["create", "list_templates", "make", "template_app"]
