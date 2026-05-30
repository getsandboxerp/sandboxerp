"""
sandboxerp.cli.destroy
~~~~~~~~~~~~~~~~~~~~~~

``sandbox destroy`` subcommand.

Removes the SandboxERP environment completely — containers, volumes, and
the generated ``docker-compose.yml``.

Examples::

    sandbox destroy            # prompts for confirmation
    sandbox destroy --force    # skips confirmation (CI / scripting)

"""

import typer
from rich.console import Console

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

    Removes all Docker containers, volumes, and generated configuration
    files created by ``sandbox generate``.  **This action cannot be undone.**

    Args:
        force: When *True*, the confirmation prompt is skipped.  Intended
            for use in CI pipelines and non-interactive scripts.

    Raises:
        typer.Abort: When the user declines the confirmation prompt.
        typer.Exit:  With code 1 when no managed environment is found.

    .. warning::
        All generated data will be lost.  If you need to preserve the
        environment, use ``sandbox stop`` instead, or create a snapshot
        with ``sandbox snapshot save`` (premium feature).

    .. todo::
        Implement via ``docker.py`` in Layer 2.
    """
    if not force:
        console.print(
            "\n[bold red]⚠  WARNING[/bold red]  "
            "This will permanently destroy the sandbox environment.\n"
            "All generated data will be [bold]lost[/bold].\n"
        )
        confirmed = typer.confirm("Are you sure you want to destroy the environment?", default=False)
        if not confirmed:
            raise typer.Abort()

    # TODO (Layer 2 — docker.py): run docker compose down --volumes --remove-orphans
    console.print("[bold yellow]⚙  Engine not yet implemented — stub only.[/bold yellow]")
