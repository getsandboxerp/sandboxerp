"""
sandboxerp.cli.destroy
~~~~~~~~~~~~~~~~~~~~~~

``sandbox destroy`` subcommand.

Removes the SandboxERP environment completely — containers, volumes, and
the generated ``docker-compose.yml``.

Examples::

    sandbox destroy            # prompts for confirmation
    sandbox destroy --force    # skips confirmation (CI / scripting)

:author: Hector Colina / Team360 <https://team360.cl>
"""

import typer
from rich.console import Console

from sandboxerp.engine.docker import (
    DEFAULT_COMPOSE_DIR,
    destroy_environment,
    environment_exists,
    get_client,
)

app = typer.Typer(help="Destroy the sandbox environment (irreversible).", no_args_is_help=False)
console = Console()


@app.callback(invoke_without_command=True)
def destroy(
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip the confirmation prompt. Use in CI / non-interactive scripts.",
    ),
) -> None:
    """
    Destroy the Odoo sandbox environment permanently.

    Removes all Docker containers and volumes created by ``sandbox generate``.
    **This action cannot be undone.**

    Args:
        force: When *True*, the confirmation prompt is skipped.

    Raises:
        typer.Abort: When the user declines the confirmation prompt.
        typer.Exit:  With code 1 when no managed environment is found.
    """
    if not force:
        console.print(
            "\n[bold red]⚠  WARNING[/bold red]  "
            "This will permanently destroy the sandbox environment.\n"
            "All generated data will be [bold]lost[/bold].\n"
        )
        confirmed = typer.confirm(
            "Are you sure you want to destroy the environment?", default=False
        )
        if not confirmed:
            raise typer.Abort()

    try:
        client = get_client()
    except RuntimeError as exc:
        console.print(f"[bold red]✗ Docker error:[/bold red] {exc}")
        raise typer.Exit(code=1)

    if not environment_exists(client):
        console.print(
            "[bold red]✗[/bold red]  No SandboxERP environment found. "
            "Nothing to destroy."
        )
        raise typer.Exit(code=1)

    try:
        destroy_environment(client, force=force)

        # Remove compose file if present
        compose_file = DEFAULT_COMPOSE_DIR / "docker-compose.yml"
        if compose_file.exists():
            compose_file.unlink()
            console.print(f"  [dim]Removed {compose_file}[/dim]")

        console.print("[bold green]✓[/bold green]  Environment destroyed.")
    except RuntimeError as exc:
        console.print(f"[bold red]✗ Error:[/bold red] {exc}")
        raise typer.Exit(code=1)
