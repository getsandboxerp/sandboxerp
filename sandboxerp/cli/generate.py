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

"""

import typer
from rich.console import Console

app = typer.Typer(help="Generate a complete Odoo sandbox environment.", no_args_is_help=True)
console = Console()

# ---------------------------------------------------------------------------
# Country / industry / profile enumerations
# (will be replaced by dynamic pack registry in a future layer)
# ---------------------------------------------------------------------------

SUPPORTED_COUNTRIES = ["cl", "mx"]
SUPPORTED_INDUSTRIES = ["retail", "accounting", "manufacturing"]
SUPPORTED_PROFILES = ["small", "medium", "enterprise", "benchmark"]

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
            f"Available in free tier: {', '.join(SUPPORTED_COUNTRIES)}."
        ),
    ),
    industry: str = typer.Option(
        ...,
        "--industry",
        "-i",
        help=(
            "Industry vertical for the generated company. "
            f"Choices: {', '.join(SUPPORTED_INDUSTRIES)}."
        ),
    ),
    profile: str = typer.Option(
        "small",
        "--profile",
        "-p",
        help=(
            "Company size / data-volume profile. "
            f"Choices: {', '.join(SUPPORTED_PROFILES)}."
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
) -> None:
    """
    Generate a complete, reproducible Odoo sandbox environment.

    The environment is 100 %% synthetic.  All data (companies, partners,
    products, invoices, payments …) is fabricated — never real.

    Args:
        country:  ISO-3166-1 alpha-2 country code (``cl``, ``mx``).
        industry: Industry vertical (``retail``, ``accounting``, …).
        profile:  Company size / data-volume profile.
        seed:     Random seed for reproducibility.
        bind:     Network interface for the Odoo container.
        port:     Host port mapped to Odoo.

    Raises:
        typer.Abort: When the user declines the ``--bind 0.0.0.0`` warning.
        typer.BadParameter: When an unsupported country, industry, or profile
            is supplied.
    """
    # ------------------------------------------------------------------
    # Input validation
    # ------------------------------------------------------------------
    _validate_country(country)
    _validate_industry(industry)
    _validate_profile(profile)

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
    # TODO (Layer 2 — docker.py):  pull images, build docker-compose
    # TODO (Layer 3 — generator.py): install modules, load country pack
    # TODO (Layer 5 — behaviour.py): generate causal ERP data
    # ------------------------------------------------------------------

    console.print("[bold yellow]⚙  Engine not yet implemented — stub only.[/bold yellow]")


# ---------------------------------------------------------------------------
# Private validators
# ---------------------------------------------------------------------------

def _validate_country(country: str) -> None:
    """Raise ``typer.BadParameter`` when *country* is not in the free tier.

    Args:
        country: Value supplied via ``--country``.

    Raises:
        typer.BadParameter: When *country* is not supported.
    """
    if country not in SUPPORTED_COUNTRIES:
        raise typer.BadParameter(
            f"Country '{country}' is not supported. "
            f"Available: {', '.join(SUPPORTED_COUNTRIES)}.",
            param_hint="'--country'",
        )


def _validate_industry(industry: str) -> None:
    """Raise ``typer.BadParameter`` when *industry* is not recognised.

    Args:
        industry: Value supplied via ``--industry``.

    Raises:
        typer.BadParameter: When *industry* is not supported.
    """
    if industry not in SUPPORTED_INDUSTRIES:
        raise typer.BadParameter(
            f"Industry '{industry}' is not supported. "
            f"Available: {', '.join(SUPPORTED_INDUSTRIES)}.",
            param_hint="'--industry'",
        )


def _validate_profile(profile: str) -> None:
    """Raise ``typer.BadParameter`` when *profile* is not recognised.

    Args:
        profile: Value supplied via ``--profile``.

    Raises:
        typer.BadParameter: When *profile* is not supported.
    """
    if profile not in SUPPORTED_PROFILES:
        raise typer.BadParameter(
            f"Profile '{profile}' is not supported. "
            f"Available: {', '.join(SUPPORTED_PROFILES)}.",
            param_hint="'--profile'",
        )
