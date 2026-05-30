"""
sandboxerp.cli.main
~~~~~~~~~~~~~~~~~~~

Entry point for the SandboxERP CLI.

Registers all subcommands under a single Typer application and provides
top-level version and help output.

Usage::

    sandbox --help
    sandbox --version
    sandbox generate --country cl --industry retail --profile small --seed 42
    sandbox start
    sandbox stop
    sandbox destroy

The ``sandbox`` command is installed via the ``[project.scripts]`` entry in
``pyproject.toml``::

    [project.scripts]
    sandbox = "sandboxerp.cli.main:app"

Attributes:
    app (typer.Typer): Root Typer application shared across all subcommands.

:author: Hector Colina / Team360 <https://team360.cl>
"""

from importlib.metadata import version, PackageNotFoundError

import typer
from rich.console import Console

from sandboxerp.cli.generate import app as generate_app
from sandboxerp.cli.start import app as start_app
from sandboxerp.cli.stop import app as stop_app
from sandboxerp.cli.destroy import app as destroy_app

# ---------------------------------------------------------------------------
# Root application
# ---------------------------------------------------------------------------

app = typer.Typer(
    name="sandbox",
    help=(
        "SandboxERP — Generate complete, coherent Odoo environments "
        "from a YAML spec or CLI flags.\n\n"
        "All environments are 100 %% synthetic and intended for development "
        "only — never for production."
    ),
    add_completion=False,   # disable shell-completion install prompt
    rich_markup_mode="rich",
    no_args_is_help=True,   # print help when called with no args
)

console = Console()

# ---------------------------------------------------------------------------
# Subcommand registration
# ---------------------------------------------------------------------------

app.add_typer(generate_app, name="generate")
app.add_typer(start_app,    name="start")
app.add_typer(stop_app,     name="stop")
app.add_typer(destroy_app,  name="destroy")

# ---------------------------------------------------------------------------
# Top-level callbacks
# ---------------------------------------------------------------------------

@app.callback(invoke_without_command=True)
def root(
    ctx: typer.Context,
    version_flag: bool = typer.Option(
        False,
        "--version",
        "-V",
        is_eager=True,
        help="Show the installed SandboxERP version and exit.",
    ),
) -> None:
    """
    Root callback executed before every subcommand.

    When ``--version`` / ``-V`` is passed the package version is printed and
    the process exits with code 0.  When no subcommand is supplied Typer
    already shows the help text because ``no_args_is_help=True``.

    Args:
        ctx: Typer/Click context (used to check whether a subcommand was
            invoked so we avoid double-printing help).
        version_flag: Print version and exit when *True*.
    """
    if version_flag:
        try:
            pkg_version = version("sandboxerp")
        except PackageNotFoundError:
            pkg_version = "dev"
        console.print(f"[bold cyan]SandboxERP[/bold cyan] version [green]{pkg_version}[/green]")
        raise typer.Exit()


# ---------------------------------------------------------------------------
# Entrypoint (allows `python -m sandboxerp.cli.main` during development)
# ---------------------------------------------------------------------------

if __name__ == "__main__":  # pragma: no cover
    app()
