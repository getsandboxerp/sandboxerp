"""
sandboxerp.cli.stop
~~~~~~~~~~~~~~~~~~~

``sandbox stop`` subcommand.

Stops the running SandboxERP environment, persisting all data so the
environment can be resumed with ``sandbox start``.

Example::

    sandbox stop

:author: Hector Colina / Team360 <https://team360.cl>
"""

import typer
from rich.console import Console

from sandboxerp.engine.docker import (
    environment_exists,
    environment_is_running,
    get_client,
    stop_environment,
)

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
    """
    try:
        client = get_client()
    except RuntimeError as exc:
        console.print(f"[bold red]✗ Docker error:[/bold red] {exc}")
        raise typer.Exit(code=1)

    if not environment_exists(client):
        console.print(
            "[bold red]✗[/bold red]  No SandboxERP environment found. "
            "Run [bold]sandbox generate[/bold] first."
        )
        raise typer.Exit(code=1)

    if not environment_is_running(client):
        console.print("[yellow]⚠[/yellow]  Environment is already stopped.")
        raise typer.Exit(code=0)

    try:
        stop_environment(client)
        console.print("[bold green]✓[/bold green]  Environment stopped. Data preserved.")
    except RuntimeError as exc:
        console.print(f"[bold red]✗ Error:[/bold red] {exc}")
        raise typer.Exit(code=1)
