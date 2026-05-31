"""
sandboxerp.cli.start
~~~~~~~~~~~~~~~~~~~~

``sandbox start`` subcommand.

Starts a previously stopped SandboxERP environment without regenerating
data.  Equivalent to ``docker compose start`` on the managed stack.

Example::

    sandbox start

:author: Hector Colina / Team360 <https://team360.cl>
"""

import typer
from rich.console import Console

from sandboxerp.engine.docker import (
    environment_exists,
    environment_is_running,
    get_client,
    start_environment,
)

app = typer.Typer(help="Start a stopped sandbox environment.", no_args_is_help=False)
console = Console()


@app.callback(invoke_without_command=True)
def start() -> None:
    """
    Start a previously stopped Odoo sandbox.

    Does **not** regenerate data — restores the environment to the exact
    state it was in when ``sandbox stop`` was called.

    Raises:
        typer.Exit: With code 1 when no managed environment is found or
            the environment is already running.
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

    if environment_is_running(client):
        console.print("[yellow]⚠[/yellow]  Environment is already running.")
        raise typer.Exit(code=0)

    try:
        start_environment(client)
        console.print("[bold green]✓[/bold green]  Environment started.")
    except RuntimeError as exc:
        console.print(f"[bold red]✗ Error:[/bold red] {exc}")
        raise typer.Exit(code=1)
