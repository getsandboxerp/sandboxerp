"""
sandboxerp.engine.docker
~~~~~~~~~~~~~~~~~~~~~~~~~

Docker engine for SandboxERP.

Handles all Docker interactions: verification, image pulling,
container lifecycle (create, start, stop, destroy), and
docker-compose generation for Odoo + PostgreSQL environments.

:author: Hector Colina / Team360 <https://team360.cl>
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

import docker
import docker.errors
import httpx
from docker import DockerClient
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

# ─────────────────────────────────────────
# Constants
# ─────────────────────────────────────────

ODOO_IMAGE = "odoo:{version}"
ODOO_DEFAULT_VERSION = "17.0-20250218"  # pinned — update deliberately, see #36
POSTGRES_IMAGE = "postgres:15"
LABEL_KEY = "sandboxerp"
LABEL_VALUE = "true"
DEFAULT_ODOO_PORT = 8069
DEFAULT_BIND = "127.0.0.1"
DEFAULT_COMPOSE_DIR = Path.home() / ".sandboxerp" / "env"

# Odoo master password for database manager (default in fresh installs).
ODOO_MASTER_PASSWORD = "admin"


# ─────────────────────────────────────────
# Client helpers
# ─────────────────────────────────────────


def get_client() -> DockerClient:
    """Return a connected Docker client.

    :raises RuntimeError: If Docker is not running or not installed.
    :return: Connected :class:`docker.DockerClient` instance.
    """
    try:
        client = docker.from_env()
        client.ping()
        return client
    except docker.errors.DockerException as exc:
        raise RuntimeError(
            "Docker is not running or not installed. "
            "Start Docker and try again."
        ) from exc


def is_docker_running() -> bool:
    """Check whether Docker daemon is reachable.

    :return: ``True`` if Docker responds to a ping, ``False`` otherwise.
    """
    try:
        get_client()
        return True
    except RuntimeError:
        return False


# ─────────────────────────────────────────
# Image helpers
# ─────────────────────────────────────────


def image_exists(client: DockerClient, image: str) -> bool:
    """Check whether an image is already available locally.

    :param client: Connected Docker client.
    :param image: Full image name including tag (e.g. ``odoo:17``).
    :return: ``True`` if the image is cached locally.
    """
    try:
        client.images.get(image)
        return True
    except docker.errors.ImageNotFound:
        return False


def pull_image(client: DockerClient, image: str) -> None:
    """Pull a Docker image if not already present locally.

    Displays a Rich spinner while pulling.

    :param client: Connected Docker client.
    :param image: Full image name including tag.
    """
    if image_exists(client, image):
        console.print(f"  [dim]✓ {image} already cached[/dim]")
        return

    with Progress(
        SpinnerColumn(),
        TextColumn(f"  Pulling [bold]{image}[/bold]..."),
        transient=True,
        console=console,
    ) as progress:
        progress.add_task("pull", total=None)
        client.images.pull(image)

    console.print(f"  [green]✓[/green] {image} ready")


def ensure_images(client: DockerClient, odoo_version: str = ODOO_DEFAULT_VERSION) -> None:
    """Ensure Odoo and PostgreSQL images are available locally.

    Pulls any missing image before environment generation.

    :param client: Connected Docker client.
    :param odoo_version: Odoo major version tag (default ``"17"``).
    """
    odoo_image = ODOO_IMAGE.format(version=odoo_version)
    pull_image(client, odoo_image)
    pull_image(client, POSTGRES_IMAGE)


# ─────────────────────────────────────────
# Environment state
# ─────────────────────────────────────────


def find_environment(client: DockerClient) -> list[docker.models.containers.Container]:
    """Return all containers that belong to a SandboxERP environment.

    SandboxERP containers are identified by the label
    ``sandboxerp=true``.

    :param client: Connected Docker client.
    :return: List of matching containers (may be empty).
    """
    return client.containers.list(
        all=True,
        filters={"label": f"{LABEL_KEY}={LABEL_VALUE}"},
    )


def environment_exists(client: DockerClient) -> bool:
    """Check whether any SandboxERP containers already exist.

    :param client: Connected Docker client.
    :return: ``True`` if at least one SandboxERP container is found.
    """
    return len(find_environment(client)) > 0


def environment_is_running(client: DockerClient) -> bool:
    """Check whether any SandboxERP containers are currently running.

    :param client: Connected Docker client.
    :return: ``True`` if at least one container is in ``running`` state.
    """
    running = client.containers.list(
        filters={"label": f"{LABEL_KEY}={LABEL_VALUE}", "status": "running"}
    )
    return len(running) > 0


# ─────────────────────────────────────────
# docker-compose generation
# ─────────────────────────────────────────


def generate_compose(
    *,
    project_name: str,
    country: str,
    industry: str,
    profile: str,
    seed: int,
    bind: str = DEFAULT_BIND,
    port: int = DEFAULT_ODOO_PORT,
    odoo_version: str = ODOO_DEFAULT_VERSION,
) -> str:
    """Generate a docker-compose YAML string for an Odoo environment.

    The compose file is fully self-contained: it defines a PostgreSQL
    service and an Odoo service wired together, labelled with
    ``sandboxerp=true`` for lifecycle management.

    Database initialisation is handled by :func:`create_database` after
    the containers are up, not via the Odoo entrypoint flag. This avoids
    a known Odoo 17 issue where ``--init base`` passed through ``command``
    in compose is silently ignored.

    :param project_name: Docker Compose project name (used as prefix).
    :param country: ISO country code (e.g. ``cl``, ``mx``).
    :param industry: Industry pack name (e.g. ``retail``).
    :param profile: Scale profile (``small`` | ``medium`` | ``enterprise``).
    :param seed: Random seed for reproducible data generation.
    :param bind: Host interface to bind Odoo port (default ``127.0.0.1``).
    :param port: Host port for Odoo web interface (default ``8069``).
    :param odoo_version: Odoo major version tag (default ``"17"``).
    :return: Multi-line YAML string ready to write to ``docker-compose.yml``.
    """
    odoo_image = ODOO_IMAGE.format(version=odoo_version)

    return f"""# Generated by SandboxERP — do not edit manually
# country={country}  industry={industry}  profile={profile}  seed={seed}
services:
  db:
    image: {POSTGRES_IMAGE}
    environment:
      POSTGRES_USER: odoo
      POSTGRES_PASSWORD: odoo
      POSTGRES_DB: sandbox
    volumes:
      - db_data:/var/lib/postgresql/data
    labels:
      {LABEL_KEY}: "{LABEL_VALUE}"
      sandboxerp.country: "{country}"
      sandboxerp.industry: "{industry}"
      sandboxerp.profile: "{profile}"
      sandboxerp.seed: "{seed}"

  odoo:
    image: {odoo_image}
    depends_on:
      - db
    ports:
      - "{bind}:{port}:8069"
    environment:
      HOST: db
      USER: odoo
      PASSWORD: odoo
    command: -- -i base --database sandbox --without-demo all
    volumes:
      - odoo_data:/var/lib/odoo
    labels:
      {LABEL_KEY}: "{LABEL_VALUE}"
      sandboxerp.country: "{country}"
      sandboxerp.industry: "{industry}"
      sandboxerp.profile: "{profile}"
      sandboxerp.seed: "{seed}"

volumes:
  db_data:
  odoo_data:
"""


def write_compose(
    compose_yaml: str,
    output_dir: Path,
) -> Path:
    """Write a docker-compose YAML string to disk.

    Creates ``output_dir`` if it does not exist.

    :param compose_yaml: YAML content as returned by :func:`generate_compose`.
    :param output_dir: Directory where ``docker-compose.yml`` will be written.
    :return: Absolute path to the written file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    compose_path = output_dir / "docker-compose.yml"
    compose_path.write_text(compose_yaml, encoding="utf-8")
    return compose_path


# ─────────────────────────────────────────
# Database initialisation
# ─────────────────────────────────────────


def create_database(
    host: str = "127.0.0.1",
    port: int = DEFAULT_ODOO_PORT,
    db_name: str = "sandbox",
    admin_password: str = "admin",
    master_password: str = ODOO_MASTER_PASSWORD,
    lang: str = "en_US",
    timeout: int = 300,
    interval: int = 5,
) -> None:
    """Create the Odoo sandbox database via the HTTP Database Manager API.

    Polls ``/web/database/create`` until the database is successfully
    created or *timeout* seconds have elapsed. This is the recommended
    approach for Odoo 17, where passing ``--init base`` via the Docker
    ``command`` directive is silently ignored.

    The call is idempotent: if the database already exists Odoo returns
    an error which this function silently ignores.

    :param host: Odoo host (default ``"127.0.0.1"``).
    :param port: Odoo HTTP port (default ``8069``).
    :param db_name: Name of the database to create (default ``"sandbox"``).
    :param admin_password: Admin user password for the new database.
    :param master_password: Odoo master password for the database manager.
    :param lang: Language code for the new database (default ``"en_US"``).
    :param timeout: Maximum seconds to wait (default ``300``).
    :param interval: Seconds between retries (default ``5``).
    :raises RuntimeError: If the database could not be created within
        *timeout* seconds.
    """
    url = f"http://{host}:{port}/web/database/create"
    # Odoo 17 /web/database/create is a plain form POST, not JSON-RPC.
    # A successful response is an HTML redirect (200 with HTML body),
    # not a JSON payload.
    form_data = {
        "master_pwd": master_password,
        "name": db_name,
        "lang": lang,
        "password": admin_password,
        "login": "admin",
        "demo": "false",
    }

    deadline = time.time() + timeout
    last_error: str = ""

    while time.time() < deadline:
        try:
            response = httpx.post(url, data=form_data, timeout=30)

            # Success: Odoo returns 200 with HTML (redirect to /web).
            # We treat any non-500 response as success since the DB was created.
            if response.status_code < 500:
                return

            last_error = f"HTTP {response.status_code}"

        except Exception as exc:
            last_error = str(exc)

        time.sleep(interval)

    raise RuntimeError(
        f"Could not create Odoo database '{db_name}' within {timeout}s. "
        f"Last error: {last_error}. "
        "Check: docker compose logs odoo"
    )


# ─────────────────────────────────────────
# Container lifecycle
# ─────────────────────────────────────────


def start_environment(client: DockerClient) -> None:
    """Start all stopped SandboxERP containers.

    :param client: Connected Docker client.
    :raises RuntimeError: If no SandboxERP environment is found.
    """
    containers = find_environment(client)
    if not containers:
        raise RuntimeError(
            "No SandboxERP environment found. Run `sandbox generate` first."
        )
    for container in containers:
        if container.status != "running":
            container.start()


def stop_environment(client: DockerClient) -> None:
    """Stop all running SandboxERP containers.

    :param client: Connected Docker client.
    :raises RuntimeError: If no SandboxERP environment is found.
    """
    containers = find_environment(client)
    if not containers:
        raise RuntimeError(
            "No SandboxERP environment found. Run `sandbox generate` first."
        )
    for container in containers:
        if container.status == "running":
            container.stop()


def destroy_environment(client: DockerClient, *, force: bool = False) -> None:
    """Remove all SandboxERP containers and their associated volumes.

    :param client: Connected Docker client.
    :param force: When ``True``, running containers are killed before removal.
    :raises RuntimeError: If no SandboxERP environment is found.
    """
    containers = find_environment(client)
    if not containers:
        raise RuntimeError(
            "No SandboxERP environment found. Nothing to destroy."
        )
    for container in containers:
        container.remove(v=True, force=force)

    # Remove named volumes — docker-compose prefixes them with the directory
    # name ("env_"), so they are not removed by container.remove(v=True).
    # Fixes: https://github.com/getsandboxerp/sandboxerp/issues/31
    volume_names = ["env_db_data", "env_odoo_data"]
    for vol_name in volume_names:
        try:
            vol = client.volumes.get(vol_name)
            vol.remove(force=True)
        except Exception:
            pass  # volume already gone or never created


def wait_for_odoo(
    bind: str = DEFAULT_BIND,
    port: int = DEFAULT_ODOO_PORT,
    timeout: int = 60,
) -> bool:
    """Poll until Odoo's HTTP port is accepting connections.

    :param bind: Host interface where Odoo is bound.
    :param port: Host port for Odoo.
    :param timeout: Maximum seconds to wait (default ``60``).
    :return: ``True`` if Odoo became available within *timeout* seconds,
             ``False`` otherwise.
    """
    import socket

    host = bind if bind != "0.0.0.0" else "127.0.0.1"
    deadline = time.time() + timeout

    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=2):
                return True
        except OSError:
            time.sleep(2)

    return False


def wait_for_db_init(
    bind: str = DEFAULT_BIND,
    port: int = DEFAULT_ODOO_PORT,
    timeout: int = 300,
    interval: int = 5,
) -> bool:
    """Poll until Odoo has fully initialized the sandbox database.

    Odoo initializes the database via -i base passed as a command
    argument in the compose file. This function polls
    /web/database/manager until it returns HTTP 200, indicating
    the database schema is ready for XML-RPC calls.

    Fixes: https://github.com/getsandboxerp/sandboxerp/issues/34

    :param bind: Host interface where Odoo is bound.
    :param port: Host port for Odoo.
    :param timeout: Maximum seconds to wait (default 300).
    :param interval: Seconds between retries (default 5).
    :return: True if the database became ready within timeout seconds.
    """
    host = bind if bind != "0.0.0.0" else "127.0.0.1"
    url = f"http://{host}:{port}/web/database/manager"
    deadline = time.time() + timeout

    while time.time() < deadline:
        try:
            response = httpx.get(url, timeout=10)
            if response.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(interval)

    return False


def wait_for_db_init(
    bind: str = DEFAULT_BIND,
    port: int = DEFAULT_ODOO_PORT,
    timeout: int = 300,
    interval: int = 5,
) -> bool:
    host = bind if bind != "0.0.0.0" else "127.0.0.1"
    url = f"http://{host}:{port}/web/database/manager"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            response = httpx.get(url, timeout=10)
            if response.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(interval)
    return False
