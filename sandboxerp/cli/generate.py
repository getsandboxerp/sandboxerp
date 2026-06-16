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

    # Premium — generate a tax report for Spain, 3rd quarter 2025
    # (requires SANDBOXERP_LICENSE_KEY and a country pack that defines
    # a `compliance` block — see PREMIUM SCAFFOLD NOTE below)
    sandbox generate --country es --industry retail --profile small \\
        --compliance "tax_report,period=3T,year=2025"

:author: Hector Colina / Team360 <https://team360.cl>
"""

import os
from datetime import date
from typing import Any, Optional

import typer
from rich.console import Console

from sandboxerp.engine.generator import (
    SUPPORTED_COUNTRIES,
    SUPPORTED_INDUSTRIES,
    SUPPORTED_PROFILES,
    generate_environment,
)
from sandboxerp.engine.license import require_premium
from sandboxerp.packs.loader import load_country_pack

app = typer.Typer(help="Generate a complete Odoo sandbox environment.", no_args_is_help=True)
console = Console()

# ---------------------------------------------------------------------------
# --compliance flag: constants
# ---------------------------------------------------------------------------

# Env var read for the premium license key. See PREMIUM SCAFFOLD NOTE below
# for why this is the only source supported today.
_LICENSE_KEY_ENV_VAR = "SANDBOXERP_LICENSE_KEY"

# Key in a country pack's YAML that, if present, marks compliance as
# available for that country (real content lives in the private
# Compliance Pack repo — see DEVELOPMENT.md).
_COMPLIANCE_PACK_KEY = "compliance"


# ---------------------------------------------------------------------------
# --compliance flag: parsing
# ---------------------------------------------------------------------------

def _previous_quarter(today: Optional[date] = None) -> tuple[str, int]:
    """Compute the previous calendar quarter relative to *today*.

    :param today: Reference date. Defaults to :func:`date.today` when omitted
        (kept as a parameter so tests can pin the result deterministically).
    :return: Tuple of ``(period, year)``, e.g. ``("2T", 2025)``.
    """
    today = today or date.today()
    current_quarter = (today.month - 1) // 3 + 1
    if current_quarter == 1:
        return f"4T", today.year - 1
    return f"{current_quarter - 1}T", today.year


def parse_compliance_flag(value: str) -> dict[str, Any]:
    """Parse the ``--compliance`` flag value into a structured dict.

    Expected format: ``"<report_name>[,key=value,...]"``, e.g.::

        "tax_report,period=3T,year=2025"
        "tax_report"  # period/year default to the previous quarter

    :param value: Raw flag string as typed by the user.
    :return: Dict with at least a ``"report"`` key, plus any ``key=value``
        pairs supplied (``period`` and ``year`` default to the previous
        quarter when not provided).
    :raises typer.BadParameter: If *value* is empty or malformed (e.g. a
        ``key=value`` segment missing the ``=``).
    """
    parts = [p.strip() for p in value.split(",") if p.strip()]
    if not parts:
        raise typer.BadParameter(
            "Empty --compliance value. Expected format: "
            "'<report_name>[,key=value,...]', e.g. "
            "'tax_report,period=3T,year=2025'.",
            param_hint="'--compliance'",
        )

    report_name, *kv_parts = parts
    parsed: dict[str, Any] = {"report": report_name}

    for kv in kv_parts:
        if "=" not in kv:
            raise typer.BadParameter(
                f"Malformed --compliance segment '{kv}'. "
                "Expected 'key=value', e.g. 'period=3T'.",
                param_hint="'--compliance'",
            )
        key, _, val = kv.partition("=")
        key = key.strip()
        val = val.strip()
        if not key or not val:
            raise typer.BadParameter(
                f"Malformed --compliance segment '{kv}'. "
                "Expected 'key=value', e.g. 'period=3T'.",
                param_hint="'--compliance'",
            )
        parsed[key] = val

    if "period" not in parsed or "year" not in parsed:
        default_period, default_year = _previous_quarter()
        parsed.setdefault("period", default_period)
        parsed.setdefault("year", str(default_year))

    return parsed


# ---------------------------------------------------------------------------
# --compliance flag: validation against the country pack + license
# ---------------------------------------------------------------------------

def _resolve_compliance(country: str, compliance_value: str) -> dict[str, Any]:
    """Validate and resolve a ``--compliance`` request end to end.

    Three checks happen in order, each with its own explicit error so the
    user knows exactly which one failed:

    1. Parse the flag string itself (malformed input).
    2. Does the *country pack* declare a ``compliance`` block at all? A
       country pack without one means SandboxERP doesn't support
       compliance reporting for that country yet — independent of any
       license.
    3. Does the caller have a premium license? Delegates to
       :func:`sandboxerp.engine.license.require_premium`, which already
       raises :class:`PermissionError` with an upgrade message.

    :param country: ISO country code, already validated by the caller.
    :param compliance_value: Raw ``--compliance`` flag string.
    :return: Parsed compliance request dict (see :func:`parse_compliance_flag`).
    :raises typer.BadParameter: If the flag string itself is malformed.
    :raises typer.Exit: If the country pack has no ``compliance`` block.
    :raises PermissionError: If no valid premium license is found
        (raised by :func:`~sandboxerp.engine.license.require_premium`).
    """
    parsed = parse_compliance_flag(compliance_value)

    country_pack = load_country_pack(country)
    if _COMPLIANCE_PACK_KEY not in country_pack:
        console.print(
            f"\n[bold red]✗ Error:[/bold red] Compliance reporting is not "
            f"available yet for country '[bold]{country}[/bold]'.\n"
            "Only countries with a Compliance Pack define this. "
            "Check https://sandboxerp.team360.cl for current availability.\n"
        )
        raise typer.Exit(code=1)

    # PREMIUM SCAFFOLD NOTE
    # ---------------------
    # The key is read from an environment variable only, for now:
    #
    #   export SANDBOXERP_LICENSE_KEY="your-key-here"
    #
    # This is intentional and not a placeholder for its own sake — env
    # vars are the standard way CLIs handle secrets (cf. ANTHROPIC_API_KEY,
    # AWS_ACCESS_KEY_ID, STRIPE_API_KEY): they don't leak into shell
    # history or `ps aux` the way a --license-key flag would.
    #
    # TODO before public premium launch: also support a persisted config
    # file (e.g. ~/.sandboxerp/credentials) so the key survives across
    # terminal sessions without the user editing their shell rc file by
    # hand. Add as a second lookup source, env var still takes priority.
    # This does NOT require touching require_premium()'s call signature —
    # only how `key` is sourced here.
    key = os.environ.get(_LICENSE_KEY_ENV_VAR)
    require_premium(key, feature=f"--compliance ({parsed['report']})")

    # PREMIUM SCAFFOLD NOTE — Docker image selection
    # ------------------------------------------------
    # Once licensed, compliance reports need OCA fiscal modules
    # preinstalled (e.g. l10n-spain + account_tax_balance + date_range
    # for ES) that are NOT part of the free SandboxERP image. That
    # custom image lives in the private Compliance Pack repo and is not
    # wired up here yet. generate_environment() does not currently
    # accept any parameter to select it — that's the next piece of
    # scaffolding, in engine/generator.py + engine/docker.py, not here.
    return parsed


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
    compliance: Optional[str] = typer.Option(
        None,
        "--compliance",
        help=(
            "Generate a compliance/tax report after the environment is "
            "ready. Format: '<report_name>[,period=<period>,year=<year>]', "
            "e.g. 'tax_report,period=3T,year=2025'. period/year default to "
            "the previous quarter. Requires a country pack with compliance "
            "support and a SandboxERP Premium license "
            f"(set {_LICENSE_KEY_ENV_VAR})."
        ),
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
        compliance: Optional compliance report request. See
            :func:`parse_compliance_flag` for the expected format.

    Raises:
        typer.Abort: When the user declines the ``--bind 0.0.0.0`` warning.
        typer.BadParameter: When an unsupported country, industry, profile,
            or a malformed ``--compliance`` value is supplied.
        typer.Exit: On Docker errors, if an environment already exists and
            ``--force`` was not passed, or if ``--compliance`` was requested
            for a country with no Compliance Pack support.
        PermissionError: If ``--compliance`` was requested without a valid
            premium license.
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
    # --compliance: parse + validate pack support + validate license
    # ------------------------------------------------------------------
    compliance_request: Optional[dict[str, Any]] = None
    if compliance is not None:
        try:
            compliance_request = _resolve_compliance(country, compliance)
        except PermissionError as exc:
            console.print(f"\n[bold red]✗ Error:[/bold red] {exc}\n")
            raise typer.Exit(code=1)

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
    summary = (
        f"\n[bold cyan]SandboxERP[/bold cyan] — generating environment\n"
        f"  country   : [green]{country.upper()}[/green]\n"
        f"  industry  : [green]{industry}[/green]\n"
        f"  profile   : [green]{profile}[/green]\n"
        f"  seed      : [green]{seed}[/green]\n"
        f"  bind      : [green]{bind}:{port}[/green]\n"
    )
    if compliance_request is not None:
        summary += (
            f"  compliance: [green]{compliance_request['report']}[/green] "
            f"(period={compliance_request['period']}, "
            f"year={compliance_request['year']})\n"
        )
    console.print(summary)

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
            # NOTE: generate_environment() does not accept a compliance
            # parameter yet. Wiring compliance_request through to the
            # installer/docker layers (premium image selection, report
            # generation after the causal chain completes) is the next
            # piece of scaffolding — tracked separately, not done here.
        )
    except (RuntimeError, PermissionError) as exc:
        console.print(f"[bold red]✗ Error:[/bold red] {exc}")
        raise typer.Exit(code=1)
