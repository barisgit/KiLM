"""Errors of the import command."""


class ImportZipError(Exception):
    """A ZIP that cannot be imported.

    The command reports the message, skips the ZIP, imports the remaining
    ones, and exits with status 1.
    """
