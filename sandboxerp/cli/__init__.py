"""
sandboxerp.cli
~~~~~~~~~~~~~~

Command-line interface package for SandboxERP.

Exports the root Typer ``app`` so it can be referenced from
``pyproject.toml`` as the installed ``sandbox`` script.
:author: Hector Colina / Team360 <https://team360.cl>
"""

from sandboxerp.cli.main import app

__all__ = ["app"]
