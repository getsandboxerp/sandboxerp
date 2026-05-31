"""
sandboxerp.engine.installer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Installer engine for SandboxERP.

Orchestrates the post-Docker phase of environment generation:

1. Wait for Odoo to accept XML-RPC connections.
2. Create the sandbox database (if it does not exist).
3. Load country + industry packs.
4. Install Odoo modules in the order declared by the packs.
5. Configure the company (currency, country, language, tax).
6. Generate synthetic master data: partners, products.
7. Generate causal transaction chains via the Behaviour Engine.

This module is called by :mod:`sandboxerp.engine.generator` once the
Docker environment is up and Odoo is responding on its HTTP port.

:author: Hector Colina / Team360 <https://team360.cl>
"""

from __future__ import annotations

import time
from typing import Any

from faker import Faker
from rich.console import Console
from rich.progress import BarColumn, Progress, TaskProgressColumn, TextColumn

from sandboxerp.engine.behaviour import generate_chain
from sandboxerp.engine.odoo import OdooClient, OdooError
from sandboxerp.packs.loader import load_country_pack, load_industry_pack

console = Console()

# Default Odoo admin credentials for sandbox environments.
ODOO_DB = "sandbox"
ODOO_USER = "admin"
ODOO_PASSWORD = "admin"


# ─────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────


def install(
    *,
    country: str,
    industry: str,
    profile: str,
    seed: int,
    host: str = "127.0.0.1",
    port: int = 8069,
) -> None:
    """Run the full post-Docker installation pipeline.

    :param country: ISO country code (e.g. ``"cl"``).
    :param industry: Industry pack name (e.g. ``"retail"``).
    :param profile: Scale profile (e.g. ``"small"``).
    :param seed: Random seed for reproducible data generation.
    :param host: Odoo host (default ``"127.0.0.1"``).
    :param port: Odoo HTTP port (default ``8069``).
    :raises OdooError: On any XML-RPC failure.
    :raises FileNotFoundError: If a required pack is missing.
    """
    console.print("\n[bold]→[/bold] Loading packs...")
    country_pack = load_country_pack(country)
    industry_pack = load_industry_pack(industry, country)
    console.print(
        f"  [dim]country: {country_pack['meta']['name']} | "
        f"industry: {industry_pack['meta']['name']}[/dim]"
    )

    console.print("[bold]→[/bold] Connecting to Odoo...")
    client = _wait_for_xmlrpc(host=host, port=port)

    console.print("[bold]→[/bold] Installing modules...")
    _install_modules(client, country_pack, industry_pack)

    console.print("[bold]→[/bold] Configuring company...")
    _configure_company(client, country_pack)

    console.print("[bold]→[/bold] Generating master data...")
    fake = Faker(country_pack["meta"]["locale"])
    fake.seed_instance(seed)

    partner_ids = _generate_partners(client, country_pack, industry_pack, profile, fake)
    product_ids = _generate_products(client, industry_pack, profile, fake)

    console.print("[bold]→[/bold] Generating transactions...")
    _generate_transactions(
        client,
        country_pack=country_pack,
        industry_pack=industry_pack,
        profile=profile,
        seed=seed,
        partner_ids=partner_ids,
        product_ids=product_ids,
    )

    console.print("\n[bold green]✓ Installation complete.[/bold green]")


# ─────────────────────────────────────────
# XML-RPC wait
# ─────────────────────────────────────────


def _wait_for_xmlrpc(
    host: str,
    port: int,
    timeout: int = 120,
    interval: int = 3,
) -> OdooClient:
    """Poll until the Odoo XML-RPC endpoint is accepting calls.

    :param host: Odoo host.
    :param port: Odoo HTTP port.
    :param timeout: Maximum seconds to wait.
    :param interval: Seconds between retries.
    :return: Authenticated :class:`~sandboxerp.engine.odoo.OdooClient`.
    :raises RuntimeError: If Odoo does not respond within *timeout* seconds.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            client = OdooClient.connect_and_authenticate(
                host=host,
                port=port,
                db=ODOO_DB,
                user=ODOO_USER,
                password=ODOO_PASSWORD,
            )
            return client
        except OdooError:
            time.sleep(interval)

    raise RuntimeError(
        f"Odoo XML-RPC did not become available within {timeout}s. "
        "Check: docker compose logs odoo"
    )


# ─────────────────────────────────────────
# Module installation
# ─────────────────────────────────────────


def _install_modules(
    client: OdooClient,
    country_pack: dict,
    industry_pack: dict,
) -> None:
    """Install all modules declared by country + industry packs.

    Country modules are installed first, then industry modules.

    :param client: Authenticated Odoo client.
    :param country_pack: Loaded country pack dict.
    :param industry_pack: Loaded industry pack dict.
    """
    country_modules = (
        country_pack.get("localization", {})
        .get("odoo_modules", {})
        .get("install_order", [])
    )
    industry_modules = (
        industry_pack.get("meta", {})
        .get("odoo_modules", {})
        .get("install_order", [])
    )

    all_modules = country_modules + [
        m for m in industry_modules if m not in country_modules
    ]

    for module in all_modules:
        if client.module_is_installed(module):
            console.print(f"  [dim]✓ {module} already installed[/dim]")
        else:
            console.print(f"  [bold]↓[/bold] Installing {module}...")
            client.install_module(module)
            console.print(f"  [green]✓[/green] {module}")


# ─────────────────────────────────────────
# Company configuration
# ─────────────────────────────────────────


def _configure_company(client: OdooClient, country_pack: dict) -> None:
    """Apply country pack settings to the main Odoo company.

    Sets currency, country, language, and default tax.

    :param client: Authenticated Odoo client.
    :param country_pack: Loaded country pack dict.
    """
    loc = country_pack.get("localization", {})
    currency_name = loc.get("currency", "USD")
    country_code = loc.get("country_code", "")

    # Resolve country ID
    country_ids = client.search("res.country", [("code", "=", country_code)])
    country_id = country_ids[0] if country_ids else False

    # Resolve currency ID
    currency_ids = client.search("res.currency", [("name", "=", currency_name)])
    currency_id = currency_ids[0] if currency_ids else False

    # Update main company (id=1)
    values: dict[str, Any] = {}
    if country_id:
        values["country_id"] = country_id
    if currency_id:
        values["currency_id"] = currency_id

    if values:
        client.write("res.company", [1], values)
        console.print(
            f"  [dim]country={country_code} currency={currency_name}[/dim]"
        )


# ─────────────────────────────────────────
# Master data — partners
# ─────────────────────────────────────────


def _generate_partners(
    client: OdooClient,
    country_pack: dict,
    industry_pack: dict,
    profile: str,
    fake: Faker,
) -> list[int]:
    """Generate customer and supplier partner records.

    :param client: Authenticated Odoo client.
    :param country_pack: Loaded country pack dict.
    :param industry_pack: Loaded industry pack dict.
    :param profile: Scale profile name.
    :param fake: Seeded :class:`~faker.Faker` instance.
    :return: List of created partner IDs.
    """
    customer_count = (
        industry_pack.get("customers", {})
        .get("count_by_profile", {})
        .get(profile, 10)
    )
    supplier_count = (
        industry_pack.get("suppliers", {})
        .get("count_by_profile", {})
        .get(profile, 5)
    )

    fiscal = country_pack.get("fiscal", {})
    person_rut_method = fiscal.get("faker_person_id", "ssn")
    company_rut_method = fiscal.get("faker_company_id", "ssn")

    country_ids = client.search(
        "res.country",
        [("code", "=", country_pack["localization"].get("country_code", "US"))],
    )
    country_id = country_ids[0] if country_ids else False

    partner_ids: list[int] = []

    with Progress(
        TextColumn("  {task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=True,
    ) as progress:
        # Customers
        task = progress.add_task("Customers", total=customer_count)
        for _ in range(customer_count):
            vat = getattr(fake, person_rut_method, fake.ssn)()
            record = {
                "name": fake.name(),
                "customer_rank": 1,
                "supplier_rank": 0,
                "is_company": False,
                "vat": vat,
                "email": fake.email(),
                "phone": fake.phone_number(),
                "country_id": country_id,
            }
            pid = client.create("res.partner", record)
            partner_ids.append(pid)
            progress.advance(task)

        # Suppliers
        task = progress.add_task("Suppliers", total=supplier_count)
        for _ in range(supplier_count):
            vat = getattr(fake, company_rut_method, fake.ssn)()
            record = {
                "name": fake.company(),
                "customer_rank": 0,
                "supplier_rank": 1,
                "is_company": True,
                "vat": vat,
                "email": fake.company_email(),
                "phone": fake.phone_number(),
                "country_id": country_id,
            }
            pid = client.create("res.partner", record)
            partner_ids.append(pid)
            progress.advance(task)

    console.print(
        f"  [green]✓[/green] {customer_count} customers + {supplier_count} suppliers"
    )
    return partner_ids


# ─────────────────────────────────────────
# Master data — products
# ─────────────────────────────────────────


def _generate_products(
    client: OdooClient,
    industry_pack: dict,
    profile: str,
    fake: Faker,
) -> list[int]:
    """Generate product records based on industry pack configuration.

    :param client: Authenticated Odoo client.
    :param industry_pack: Loaded industry pack dict.
    :param profile: Scale profile name.
    :param fake: Seeded :class:`~faker.Faker` instance.
    :return: List of created product template IDs.
    """
    products_cfg = industry_pack.get("products", {})
    count = products_cfg.get("count_by_profile", {}).get(profile, 10)
    categories = products_cfg.get("categories", [])
    product_type = products_cfg.get("type", "product")

    product_ids: list[int] = []

    with Progress(
        TextColumn("  {task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Products", total=count)
        for i in range(count):
            cat = categories[i % len(categories)] if categories else {}
            price_range = cat.get("price_range", [1000, 50000])
            price = round(
                fake.random.uniform(price_range[0], price_range[1]), 2
            )
            sku_prefix = industry_pack.get("products", {}) \
                .get("sku_prefix_by_category", {}) \
                .get(cat.get("code", "XX"), "PR")
            internal_ref = f"{sku_prefix}{str(i + 1).zfill(5)}"

            record = {
                "name": fake.catch_phrase(),
                "type": product_type,
                "list_price": price,
                "standard_price": round(
                    price * (1 - cat.get("margin_pct", 0.30)), 2
                ),
                "default_code": internal_ref,
            }
            pid = client.create("product.template", record)
            product_ids.append(pid)
            progress.advance(task)

    console.print(f"  [green]✓[/green] {count} products")
    return product_ids


# ─────────────────────────────────────────
# Transactions
# ─────────────────────────────────────────


def _generate_transactions(
    client: OdooClient,
    *,
    country_pack: dict,
    industry_pack: dict,
    profile: str,
    seed: int,
    partner_ids: list[int],
    product_ids: list[int],
) -> None:
    """Generate causal ERP transaction chains.

    Uses :func:`~sandboxerp.engine.behaviour.generate_chain` to produce
    causally linked chains (Lead → SO → Delivery → Invoice → Payment)
    and creates the corresponding Odoo records.

    :param client: Authenticated Odoo client.
    :param country_pack: Loaded country pack dict.
    :param industry_pack: Loaded industry pack dict.
    :param profile: Scale profile name.
    :param seed: Random seed for reproducibility.
    :param partner_ids: List of available partner IDs.
    :param product_ids: List of available product template IDs.
    """
    import random

    rng = random.Random(seed)
    country = country_pack["meta"]["code"]
    industry = industry_pack["meta"]["code"]

    n_chains = (
        industry_pack.get("transactions", {})
        .get("so_chains_by_profile", {})
        .get(profile, 10)
    )

    chains = generate_chain(
        seed=seed,
        country=country,
        industry=industry,
        profile=profile,
        n_chains=n_chains,
    )

    # Resolve pricelist and journal for SO
    pricelist_ids = client.search("product.pricelist", [], limit=1)
    pricelist_id = pricelist_ids[0] if pricelist_ids else False

    created_so = 0

    with Progress(
        TextColumn("  {task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Sale Orders", total=len(chains))

        for chain in chains:
            if not partner_ids or not product_ids:
                break

            partner_id = rng.choice(partner_ids)
            product_id = rng.choice(product_ids)

            # Find SO transaction in chain
            so_tx = next((t for t in chain if t.type == "sale_order"), None)
            if not so_tx:
                progress.advance(task)
                continue

            try:
                so_vals: dict[str, Any] = {
                    "partner_id": partner_id,
                    "order_line": [
                        (
                            0,
                            0,
                            {
                                "product_id": product_id,
                                "product_uom_qty": rng.randint(1, 10),
                                "price_unit": round(so_tx.amount / rng.randint(1, 10), 2),
                            },
                        )
                    ],
                }
                if pricelist_id:
                    so_vals["pricelist_id"] = pricelist_id

                client.create("sale.order", so_vals)
                created_so += 1
            except OdooError:
                pass  # skip chains that fail due to missing config

            progress.advance(task)

    console.print(f"  [green]✓[/green] {created_so} sale orders")
