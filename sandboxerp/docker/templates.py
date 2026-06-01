"""
Docker Compose template helpers for SandboxERP.

Provides typed dataclasses that represent a Compose file structure and
a renderer that serialises them to YAML. This keeps template logic
separate from the Docker engine so each piece can be tested in isolation.

:author: Hector Colina / Team360 <https://team360.cl>
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import yaml


@dataclass
class ServiceTemplate:
    """Configuration for a single Compose service.

    :param name: Service name (e.g. ``"odoo"`` or ``"db"``).
    :param image: Docker image reference.
    :param ports: Port mappings as ``"host:container"`` strings.
    :param environment: Environment variable key-value pairs.
    :param volumes: Volume mount strings (named or bind-mount).
    :param depends_on: Names of services this service depends on.
    :param labels: Docker labels to attach to the container.
    :param command: Optional command to override the image default entrypoint.
    """

    name: str
    image: str
    ports: list[str] = field(default_factory=list)
    environment: dict[str, str] = field(default_factory=dict)
    volumes: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    labels: dict[str, str] = field(default_factory=dict)
    command: Optional[str] = None

    def to_dict(self) -> dict:
        """Serialise this service to a Compose-compatible dict.

        :return: Dict ready to nest under the ``services:`` key.
        """
        svc: dict = {"image": self.image}
        if self.depends_on:
            svc["depends_on"] = self.depends_on
        if self.ports:
            svc["ports"] = self.ports
        if self.environment:
            svc["environment"] = self.environment
        if self.volumes:
            svc["volumes"] = self.volumes
        if self.labels:
            svc["labels"] = self.labels
        if self.command is not None:
            svc["command"] = self.command
        return svc


@dataclass
class ComposeTemplate:
    """Top-level Compose file template.

    :param services: List of :class:`ServiceTemplate` instances.
    :param named_volumes: Names of top-level named volumes to declare.
    :param header_comment: Optional comment written at the top of the file.
    """

    services: list[ServiceTemplate]
    named_volumes: list[str] = field(default_factory=list)
    header_comment: Optional[str] = None

    def render(self) -> str:
        """Render the template to a YAML string.

        :return: Multi-line YAML string suitable for ``docker-compose.yml``.
        """
        doc: dict = {
            "services": {s.name: s.to_dict() for s in self.services},
        }

        if self.named_volumes:
            doc["volumes"] = {v: None for v in self.named_volumes}

        rendered = yaml.dump(doc, default_flow_style=False, sort_keys=False)

        if self.header_comment:
            rendered = f"# {self.header_comment}\n{rendered}"

        return rendered


def build_odoo_template(
    *,
    country: str,
    industry: str,
    profile: str,
    seed: int,
    bind: str = "127.0.0.1",
    port: int = 8069,
    odoo_version: str = "17",
    postgres_image: str = "postgres:15",
) -> ComposeTemplate:
    """Build the standard Odoo + PostgreSQL Compose template.

    Database initialisation is handled by
    :func:`sandboxerp.engine.docker.create_database` after the containers
    are up. The Odoo service starts without ``--init base`` to avoid a
    known Odoo 17 issue where that flag is silently ignored when passed
    via the Docker ``command`` directive.

    :param country: ISO country code label (stored as a container label).
    :param industry: Industry pack label.
    :param profile: Scale profile label.
    :param seed: Seed label for traceability.
    :param bind: Host interface for the Odoo port.
    :param port: Host port for Odoo.
    :param odoo_version: Odoo major version tag.
    :param postgres_image: Full Postgres image reference.
    :return: Populated :class:`ComposeTemplate` ready to render.
    """
    sandbox_labels = {
        "sandboxerp": "true",
        "sandboxerp.country": country,
        "sandboxerp.industry": industry,
        "sandboxerp.profile": profile,
        "sandboxerp.seed": str(seed),
    }

    db_service = ServiceTemplate(
        name="db",
        image=postgres_image,
        environment={
            "POSTGRES_USER": "odoo",
            "POSTGRES_PASSWORD": "odoo",
            "POSTGRES_DB": "sandbox",
        },
        volumes=["db_data:/var/lib/postgresql/data"],
        labels=sandbox_labels,
    )

    odoo_service = ServiceTemplate(
        name="odoo",
        image=f"odoo:{odoo_version}",
        depends_on=["db"],
        ports=[f"{bind}:{port}:8069"],
        environment={
            "HOST": "db",
            "USER": "odoo",
            "PASSWORD": "odoo",
        },
        volumes=["odoo_data:/var/lib/odoo"],
        labels=sandbox_labels,
    )

    return ComposeTemplate(
        services=[db_service, odoo_service],
        named_volumes=["db_data", "odoo_data"],
        header_comment=(
            f"Generated by SandboxERP — "
            f"country={country} industry={industry} profile={profile} seed={seed}"
        ),
    )
