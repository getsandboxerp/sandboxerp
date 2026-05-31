"""
Docker Compose manager for SandboxERP.

Thin orchestration layer between the Compose template renderer and the
``docker compose`` CLI. Writes compose files to disk and delegates
lifecycle commands (up, stop, down) to the system binary.

:author: Hector Colina / Team360 <https://team360.cl>
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from rich.console import Console

from sandboxerp.docker.templates import ComposeTemplate, build_odoo_template

console = Console()

DEFAULT_COMPOSE_DIR = Path.home() / ".sandboxerp" / "env"
COMPOSE_FILENAME = "docker-compose.yml"


def _compose_path(compose_dir: Path = DEFAULT_COMPOSE_DIR) -> Path:
    """Return the full path to the compose file.

    :param compose_dir: Directory containing the compose file.
    :return: Absolute path to ``docker-compose.yml``.
    """
    return compose_dir / COMPOSE_FILENAME


def write_compose_file(
    template: ComposeTemplate,
    compose_dir: Path = DEFAULT_COMPOSE_DIR,
) -> Path:
    """Render *template* and write it to disk.

    Creates *compose_dir* if it does not exist.

    :param template: Populated :class:`~sandboxerp.docker.templates.ComposeTemplate`.
    :param compose_dir: Target directory.
    :return: Path to the written file.
    """
    compose_dir.mkdir(parents=True, exist_ok=True)
    path = _compose_path(compose_dir)
    path.write_text(template.render(), encoding="utf-8")
    return path


def compose_up(compose_dir: Path = DEFAULT_COMPOSE_DIR) -> None:
    """Start all services defined in the compose file.

    Runs ``docker compose up -d`` against the compose file in *compose_dir*.

    :param compose_dir: Directory that contains ``docker-compose.yml``.
    :raises subprocess.CalledProcessError: If the command exits non-zero.
    """
    _run(["docker", "compose", "-f", str(_compose_path(compose_dir)), "up", "-d"])


def compose_stop(compose_dir: Path = DEFAULT_COMPOSE_DIR) -> None:
    """Stop all running services without removing containers.

    Runs ``docker compose stop``.

    :param compose_dir: Directory that contains ``docker-compose.yml``.
    :raises subprocess.CalledProcessError: If the command exits non-zero.
    """
    _run(["docker", "compose", "-f", str(_compose_path(compose_dir)), "stop"])


def compose_down(
    compose_dir: Path = DEFAULT_COMPOSE_DIR,
    *,
    volumes: bool = True,
) -> None:
    """Remove containers and optionally volumes.

    Runs ``docker compose down`` (with ``-v`` when *volumes* is ``True``).

    :param compose_dir: Directory that contains ``docker-compose.yml``.
    :param volumes: Remove named volumes declared in the compose file.
    :raises subprocess.CalledProcessError: If the command exits non-zero.
    """
    cmd = ["docker", "compose", "-f", str(_compose_path(compose_dir)), "down"]
    if volumes:
        cmd.append("-v")
    _run(cmd)


def prepare_environment(
    *,
    country: str,
    industry: str,
    profile: str,
    seed: int,
    bind: str = "127.0.0.1",
    port: int = 8069,
    odoo_version: str = "17",
    compose_dir: Path = DEFAULT_COMPOSE_DIR,
) -> Path:
    """Build, write, and launch a complete Odoo Compose environment.

    Convenience function that combines template construction, file writing,
    and ``docker compose up`` into a single call.

    :param country: ISO country code.
    :param industry: Industry pack name.
    :param profile: Scale profile.
    :param seed: Random seed for reproducibility.
    :param bind: Host interface for Odoo port.
    :param port: Host port for Odoo.
    :param odoo_version: Odoo major version tag.
    :param compose_dir: Target directory for the compose file.
    :return: Path to the written ``docker-compose.yml``.
    """
    template = build_odoo_template(
        country=country,
        industry=industry,
        profile=profile,
        seed=seed,
        bind=bind,
        port=port,
        odoo_version=odoo_version,
    )
    path = write_compose_file(template, compose_dir)
    console.print(f"[bold]→[/bold] Compose file: [dim]{path}[/dim]")
    compose_up(compose_dir)
    return path


def _run(cmd: list[str]) -> None:
    """Execute a shell command, streaming output to the console.

    :param cmd: Command + arguments list.
    :raises subprocess.CalledProcessError: On non-zero exit.
    """
    subprocess.run(cmd, check=True)
