"""
sandboxerp.cli.stop
~~~~~~~~~~~~~~~~~~~

``sandbox stop`` subcommand.

Stops the running SandboxERP environment, persisting all data so the
environment can be resumed with ``sandbox start``.

Example::

    sandbox stop

"""

import typer
from rich.console import Console

app = typer.Typer(help="Stop the running sandbox (data is preserved).", no_args_is_help=False)
console = Console()


@app.callback(invoke_without_command=True)
def stop() -> None:
    """
    Stop the running Odoo sandbox.

    Containers are stopped but **not** removed.  All database data and
    generated files are preserved on Docker volumes.  Use ``sandbox start``
    to resume, or ``sandbox destroy`` to remove everything.

    Raises:
        typer.Exit: With code 1 when no running environment is detected.

    .. todo::
        Implement via ``docker.py`` in Layer 2.
    """
    # TODO (Layer 2 — docker.py): detect running stack, run docker compose stop
    console.print("[bold yellow]⚙  Engine not yet implemented — stub only.[/bold yellow]")
