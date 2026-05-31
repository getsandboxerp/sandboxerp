"""
sandboxerp.cli.generate
~~~~~~~~~~~~~~~~~~~~~~~

``sandbox generate`` subcommand.

Orchestrates the full environment creation pipeline:

1. Validate flags and resolve pack combinations.
2. Pull Odoo + Postgres Docker images (if not cached).
3. Bring up containers via a dynamically generated ``docker-compose.yml``.
4. Install Odoo modules (sale, stock, account, …).
5. Apply country localisation.
6. Generate synthetic data with ERP causality (Lead → SO → Delivery →
   Invoice → Payment).
7. Print the access URL and credentials.

Examples::

    # Minimal — Chile retail, small company
    sandbox generate --country cl --industry retail --profile small --seed 42

    # Expose on all interfaces (requires explicit confirmation)
    sandbox generate --country cl --industry retail --profile small \\
        --seed 42 --bind 0.0.0.0 --port 8069

:author: Hector Colina / Team360 <https://team360.cl>
"""

import typer
from rich.console import Console

from sandboxerp.engine.generator import (
    SUPPORTED_COUNTRIES,
    SUPPORTED_INDUSTRIES,
    SUPPORTED_PROFILES,
    generate_environment,
)

app = typer.Typer(help="Generate a complete Odoo sandbox environment.", no_args_is_help=True)
console = Console()

# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

@app.callback(invoke_without_command=True)
def generate(
    country: str = typer.Option(
        ...,
        "--country",
        "-c",
        help=(
            "ISO-3166-1 alpha-2 country code. "
            f"Available: {', '.join(sorted(SUPPORTED_COUNTRIES))}."
        ),
    ),
    industry: str = typer.Option(
        ...,
        "--industry",
        "-i",
        help=(
            "Industry vertical for the generated company. "
            f"Choices: {', '.join(sorted(SUPPORTED_INDUSTRIES))}."
        ),
    ),
    profile: str = typer.Option(
        "small",
        "--profile",
        "-p",
        help=(
            "Company size / data-volume profile. "
            f"Choices: {', '.join(sorted(SUPPORTED_PROFILES))}."
        ),
    ),
    seed: int = typer.Option(
        42,
        "--seed",
        "-s",
        help=(
            "Random seed for reproducible data generation. "
            "The same seed + flags always produce the same environment."
        ),
    ),
    bind: str = typer.Option(
        "127.0.0.1",
        "--bind",
        help=(
            "Interface to bind Odoo to. "
            "Defaults to 127.0.0.1 (localhost only). "
            "Use 0.0.0.0 to expose on all interfaces — "
            "you will be prompted for confirmation."
        ),
    ),
    port: int = typer.Option(
        8069,
        "--port",
        help="Host port to forward to Odoo's internal 8069.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Destroy any existing environment before generating.",
    ),
) -> None:
    """
    Generate a complete, reproducible Odoo sandbox environment.

    The environment is 100 %% synthetic.  All data (companies, partners,
    products, invoices, payments …) is fabricated — never real.

    Args:
        country:  ISO-3166-1 alpha-2 country code.
        industry: Industry vertical.
        profile:  Company size / data-volume profile.
        seed:     Random seed for reproducibility.
        bind:     Network interface for the Odoo container.
        port:     Host port mapped to Odoo.
        force:    Destroy existing environment before generating.

    Raises:
        typer.Abort: When the user declines the ``--bind 0.0.0.0`` warning.
        typer.BadParameter: When an unsupported country, industry, or profile
            is supplied.
        typer.Exit: On Docker errors or if an environment already exists
            and ``--force`` was not passed.
    """
    # ------------------------------------------------------------------
    # Input validation
    # ------------------------------------------------------------------
    if country not in SUPPORTED_COUNTRIES:
        raise typer.BadParameter(
            f"Country '{country}' is not supported. "
            f"Available: {', '.join(sorted(SUPPORTED_COUNTRIES))}.",
            param_hint="'--country'",
        )
    if industry not in SUPPORTED_INDUSTRIES:
        raise typer.BadParameter(
            f"Industry '{industry}' is not supported. "
            f"Available: {', '.join(sorted(SUPPORTED_INDUSTRIES))}.",
            param_hint="'--industry'",
        )
    if profile not in SUPPORTED_PROFILES:
        raise typer.BadParameter(
            f"Profile '{profile}' is not supported. "
            f"Available: {', '.join(sorted(SUPPORTED_PROFILES))}.",
            param_hint="'--profile'",
        )

    # ------------------------------------------------------------------
    # Security warning for network exposure
    # ------------------------------------------------------------------
    if bind != "127.0.0.1":
        console.print(
            f"\n[bold yellow]⚠  WARNING[/bold yellow]  "
            f"You are binding Odoo to [bold]{bind}[/bold]. "
            "This makes the environment reachable from outside localhost.\n"
            "[red]Never expose a sandbox to the public internet.[/red]\n"
        )
        confirmed = typer.confirm("Continue anyway?", default=False)
        if not confirmed:
            raise typer.Abort()

    # ------------------------------------------------------------------
    # Summarise what will be built
    # ------------------------------------------------------------------
    console.print(
        f"\n[bold cyan]SandboxERP[/bold cyan] — generating environment\n"
        f"  country   : [green]{country.upper()}[/green]\n"
        f"  industry  : [green]{industry}[/green]\n"
        f"  profile   : [green]{profile}[/green]\n"
        f"  seed      : [green]{seed}[/green]\n"
        f"  bind      : [green]{bind}:{port}[/green]\n"
    )

    # ------------------------------------------------------------------
    # Engine
    # ------------------------------------------------------------------
    try:
        generate_environment(
            country=country,
            industry=industry,
            profile=profile,
            seed=seed,
            bind=bind,
            port=port,
            force=force,
        )
    except (RuntimeError, PermissionError) as exc:
        console.print(f"[bold red]✗ Error:[/bold red] {exc}")
        raise typer.Exit(code=1)
