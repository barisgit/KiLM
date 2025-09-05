"""
Update command implementation for KiCad Library Manager.
Updates KiLM itself to the latest version.
"""

import click

from ... import __version__
from ...auto_update import UpdateManager


@click.command()
@click.option(
    "--check",
    is_flag=True,
    default=False,
    help="Check for updates without installing",
    show_default=True,
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Force update even if already up to date",
    show_default=True,
)
def update(check, force):
    """Update KiLM to the latest version.

    This command updates KiLM itself by downloading and installing the latest
    version from PyPI. The update method depends on how KiLM was installed
    (pip, pipx, conda, etc.).

    ⚠️  DEPRECATION NOTICE:
    In KiLM 0.4.0, the 'update' command now updates KiLM itself.
    To update library content, use 'kilm sync' instead.
    This banner will be removed in a future version.

    Use --check to see if updates are available without installing.
    """
    # Display deprecation notice prominently
    click.echo("\n" + "=" * 70)
    click.echo("⚠️  BREAKING CHANGE NOTICE (KiLM 0.4.0)")
    click.echo("=" * 70)
    click.echo("The 'kilm update' command now updates KiLM itself.")
    click.echo("To update library content, use 'kilm sync' instead.")
    click.echo("This notice will be removed in a future version.")
    click.echo("=" * 70 + "\n")

    update_manager = UpdateManager(__version__)

    click.echo(f"Current KiLM version: {__version__}")
    click.echo(f"Installation method: {update_manager.installation_method}")
    click.echo("\nChecking for updates...")

    latest_version = update_manager.check_latest_version()

    if latest_version is None:
        click.echo("Could not check for updates. Please try again later.")
        return

    if not update_manager.is_newer_version_available(latest_version):
        if not force:
            click.echo(f"KiLM is up to date (v{__version__})")
            return
        else:
            click.echo(f"Forcing update to v{latest_version} (current: v{__version__})")
    else:
        click.echo(f"New version available: {latest_version}")

    if check:
        if update_manager.is_newer_version_available(latest_version):
            click.echo(f"\nUpdate available: {latest_version}")
            click.echo(f"To update, run: {update_manager.get_update_instruction()}")
        else:
            click.echo("No updates available.")
        return

    # Perform the update
    if update_manager.can_auto_update():
        click.echo(f"\nUpdating KiLM to version {latest_version}...")
        success, message = update_manager.perform_update()

        if success:
            click.echo(f"✅ {message}")
            click.echo(f"KiLM has been updated to version {latest_version}")
        else:
            click.echo(f"❌ {message}")
    else:
        instruction = update_manager.get_update_instruction()
        click.echo(
            f"\nManual update required for {update_manager.installation_method} installation."
        )
        click.echo(f"Please run: {instruction}")
