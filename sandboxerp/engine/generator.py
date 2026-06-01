"""
sandboxerp.engine.generator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Environment generator for SandboxERP.

Orchestrates the full generation pipeline:

1. Validate flags and resolve pack combinations.
2. Connect to Docker daemon.
3. Optionally destroy an existing environment.
4. Pull Odoo + Postgres Docker images (if not cached).
5. Write ``docker-compose.yml`` and bring up containers.
6. Wait for Odoo HTTP port to respond.
7. Create the sandbox database via the Odoo HTTP Database Manager API.
8. Hand off to :mod:`sandboxerp.engine.installer` for module installation
   and synthetic data generation.

:author: Hector Colina / Team360 <https://team360.cl>
"""

from __future__ import annotations

from pathlib import Path

from rich.console import Console

from sandboxerp.engine.docker import (
    DEFAULT_COMPOSE_DIR,
    create_database,
    destroy_environment,
    ensure_images,
    environment_exists,
    generate_compose,
    get_client,
    wait_for_odoo,
    write_compose,
)
from sandboxerp.engine.installer import install

console = Console()

# Supported values for validation.
SUPPORTED_COUNTRIES = {"cl", "mx", "ar", "co", "pe"}
SUPPORTED_INDUSTRIES = {"retail", "accounting", "manufacturing", "services"}
SUPPORTED_PROFILES = {"small", "medium", "enterprise", "benchmark"}


def validate_options(
    *,
    country: str,
    industry: str,
    profile: str,
) -> None:
    """Validate generation options against supported values.

    :param country: ISO country code.
    :param industry: Industry pack name.
    :param profile: Scale profile name.
    :raises ValueError: If any option is not supported.
    """
    if country not in SUPPORTED_COUNTRIES:
        raise ValueError(
            f"Country '{country}' is not supported. "
            f"Supported: {', '.join(sorted(SUPPORTED_COUNTRIES))}"
        )
    if industry not in SUPPORTED_INDUSTRIES:
        raise ValueError(
            f"Industry '{industry}' is not supported. "
            f"Supported: {', '.join(sorted(SUPPORTED_INDUSTRIES))}"
        )
    if profile not in SUPPORTED_PROFILES:
        raise ValueError(
            f"Profile '{profile}' is not supported. "
            f"Supported: {', '.join(sorted(SUPPORTED_PROFILES))}"
        )


def generate_environment(
    *,
    country: str,
    industry: str,
    profile: str,
    seed: int,
    bind: str = "127.0.0.1",
    port: int = 8069,
    odoo_version: str = "17",
    compose_dir: Path = DEFAULT_COMPOSE_DIR,
    force: bool = False,
) -> None:
    """Generate and launch a complete Odoo sandbox environment.

    Steps:

    1. Validate options.
    2. Connect to Docker.
    3. Optionally destroy an existing environment (if *force* is set).
    4. Pull required images.
    5. Write ``docker-compose.yml``.
    6. Start containers via docker-compose.
    7. Wait for Odoo to accept HTTP connections.
    8. Create the sandbox database via the Odoo HTTP Database Manager API.
    9. Install modules and generate synthetic data via the installer.

    :param country: ISO country code (e.g. ``cl``).
    :param industry: Industry pack (e.g. ``retail``).
    :param profile: Scale profile (e.g. ``small``).
    :param seed: Random seed for reproducible data.
    :param bind: Host interface to bind Odoo (default ``127.0.0.1``).
    :param port: Host port for Odoo (default ``8069``).
    :param odoo_version: Odoo major version tag (default ``"17"``).
    :param compose_dir: Directory to write the compose file into.
    :param force: Destroy any existing environment before generating.
    :raises ValueError: On invalid options.
    :raises RuntimeError: On Docker errors or if environment already exists
        and *force* is ``False``.
    """
    validate_options(country=country, industry=industry, profile=profile)

    client = get_client()

    if environment_exists(client):
        if force:
            console.print("[yellow]⚠[/yellow]  Destroying existing environment...")
            destroy_environment(client, force=True)
        else:
            raise RuntimeError(
                "A SandboxERP environment already exists. "
                "Run `sandbox destroy` first, or use --force."
            )

    console.print("[bold]→[/bold] Pulling Docker images...")
    ensure_images(client, odoo_version=odoo_version)

    project_name = f"sandboxerp_{country}_{industry}_{profile}"
    compose_yaml = generate_compose(
        project_name=project_name,
        country=country,
        industry=industry,
        profile=profile,
        seed=seed,
        bind=bind,
        port=port,
        odoo_version=odoo_version,
    )

    compose_path = write_compose(compose_yaml, compose_dir)
    console.print(f"[bold]→[/bold] Compose file written to [dim]{compose_path}[/dim]")

    console.print("[bold]→[/bold] Starting containers...")
    import subprocess
    subprocess.run(
        ["docker", "compose", "-f", str(compose_path), "up", "-d"],
        check=True,
    )

    console.print("[bold]→[/bold] Waiting for Odoo to be ready...")
    ready = wait_for_odoo(bind=bind, port=port)
    if not ready:
        console.print(
            "[yellow]⚠[/yellow]  Odoo HTTP port not yet responding — "
            "proceeding to database creation anyway."
        )

    # ── Database initialisation ──────────────────────────────────────
    # Must happen before XML-RPC calls. Odoo 17 does not auto-create the
    # database via the entrypoint flag in compose; we use the HTTP
    # Database Manager API instead.
    odoo_host = "127.0.0.1" if bind == "0.0.0.0" else bind
    console.print("[bold]→[/bold] Creating sandbox database...")
    create_database(host=odoo_host, port=port)
    console.print("  [green]✓[/green] Database ready")

    # ── Installer phase ──────────────────────────────────────────────
    install(
        country=country,
        industry=industry,
        profile=profile,
        seed=seed,
        host=odoo_host,
        port=port,
    )

    host_display = "localhost" if bind in ("127.0.0.1", "0.0.0.0") else bind
    console.print(
        f"\n[bold green]✓ Environment ready![/bold green]  "
        f"http://{host_display}:{port}\n"
        f"  user: admin  |  password: admin  |  db: sandbox"
    )
