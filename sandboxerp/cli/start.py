"""
sandboxerp.cli.start
~~~~~~~~~~~~~~~~~~~~

``sandbox start`` subcommand.

Starts a previously stopped SandboxERP environment without regenerating
data.  Equivalent to ``docker compose start`` on the managed stack.

Example::

    sandbox start

"""

import typer
from rich.console import Console

app = typer.Typer(help="Start a stopped sandbox environment.", no_args_is_help=False)
console = Console()


@app.callback(invoke_without_command=True)
def start() -> None:
    """
    Start a previously stopped Odoo sandbox.

    Does **not** regenerate data — restores the environment to the exact
    state it was in when ``sandbox stop`` was called.

    Raises:
        typer.Exit: With code 1 when no managed environment is found.

    .. todo::
        Implement via ``docker.py`` in Layer 2.
    """
    # TODO (Layer 2 — docker.py): detect managed stack, run docker compose start
    console.print("[bold yellow]⚙  Engine not yet implemented — stub only.[/bold yellow]")
