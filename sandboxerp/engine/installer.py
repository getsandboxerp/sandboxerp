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
7. Generate causal transaction chains via the Behaviour Engine,
   distributed across months using the Seasonality Engine.

This module is called by :mod:`sandboxerp.engine.generator` once the
Docker environment is up and Odoo is responding on its HTTP port.

:author: Hector Colina / Team360 <https://team360.cl>
"""

from __future__ import annotations

import random
import time
from datetime import date
from typing import Any

from faker import Faker
from rich.console import Console
from rich.progress import BarColumn, Progress, TaskProgressColumn, TextColumn

from sandboxerp.engine.behaviour import generate_chain
from sandboxerp.engine.odoo import OdooClient, OdooError
from sandboxerp.engine.persona_engine import PersonaEngine
from sandboxerp.engine.seasonality import distribute_volume
from sandboxerp.engine.time_engine import ObservationWindow, assign_dates
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
    observation_months: int = 12,
) -> None:
    """Run the full post-Docker installation pipeline.

    :param country: ISO country code (e.g. ``"cl"``).
    :param industry: Industry pack name (e.g. ``"retail"``).
    :param profile: Scale profile name (e.g. ``"small"``).
    :param seed: Random seed for reproducible data generation.
    :param host: Odoo host (default ``"127.0.0.1"``).
    :param port: Odoo HTTP port (default ``8069``).
    :param observation_months: How many months back the observation window
        spans (default ``12``).
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

    console.print("[bold]→[/bold] Configuring language...")
    _configure_language(client, country_pack)

    console.print("[bold]→[/bold] Configuring company...")
    _configure_company(client, country_pack)

    console.print("[bold]→[/bold] Configuring admin user...")
    _configure_admin_user(client)

    console.print("[bold]→[/bold] Generating master data...")
    fake = Faker(country_pack["meta"]["locale"])
    fake.seed_instance(seed)

    partner_ids = _generate_partners(client, country_pack, industry_pack, profile, fake)
    product_ids = _generate_products(client, industry_pack, profile, fake)

    window = ObservationWindow.last_n_months(observation_months)

    console.print("[bold]→[/bold] Generating transactions...")
    _generate_transactions(
        client,
        country_pack=country_pack,
        industry_pack=industry_pack,
        profile=profile,
        seed=seed,
        partner_ids=partner_ids,
        product_ids=product_ids,
        window=window,
    )

    console.print("\n[bold green]✓ Installation complete.[/bold green]")


# ─────────────────────────────────────────
# XML-RPC wait
# ─────────────────────────────────────────


def _wait_for_xmlrpc(
    host: str,
    port: int,
    timeout: int = 300,
    interval: int = 5,
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
# Language configuration
# ─────────────────────────────────────────


def _configure_language(client: OdooClient, country_pack: dict) -> None:
    """Load and activate the locale defined by the country pack.

    Attempts to load ``es_CL`` (or the locale declared in the pack).
    Falls back to ``es_ES`` if the primary locale is not available in
    Odoo. Assigns the active locale to the admin user so the interface
    renders in the correct language.

    :param client: Authenticated Odoo client.
    :param country_pack: Loaded country pack dict.
    """
    locale = country_pack.get("meta", {}).get("locale", "es_CL")

    # Ask Odoo to load the language (no-op if already loaded).
    try:
        client.execute("res.lang", "load_lang", locale)
    except Exception:
        pass

    # Verify the language is active; fall back to es_ES if needed.
    lang_ids = client.search("res.lang", [["code", "=", locale]])
    if not lang_ids:
        locale = "es_ES"
        lang_ids = client.search("res.lang", [["code", "=", locale]])

    if lang_ids:
        client.write("res.users", [2], {"lang": locale})
        console.print(f"  [dim]language={locale}[/dim]")
    else:
        console.print("  [dim]language=en_US (locale not found)[/dim]")


# ─────────────────────────────────────────
# Company configuration
# ─────────────────────────────────────────


def _configure_company(client: OdooClient, country_pack: dict) -> None:
    """Apply country pack settings to the main Odoo company.

    Sets currency and country. Currency change is attempted separately
    and silently ignored if Odoo rejects it (e.g. when journal entries
    already exist after localisation module installation).

    :param client: Authenticated Odoo client.
    :param country_pack: Loaded country pack dict.
    """
    loc = country_pack.get("localization", {})
    currency_name = loc.get("currency", "USD")
    country_code = loc.get("country_code", "")

    country_ids = client.search("res.country", [("code", "=", country_code)])
    country_id = country_ids[0] if country_ids else False

    currency_ids = client.search("res.currency", [("name", "=", currency_name)])
    currency_id = currency_ids[0] if currency_ids else False

    values: dict[str, Any] = {}
    if country_id:
        values["country_id"] = country_id
    if currency_id:
        values["currency_id"] = currency_id

    if values:
        # Set country first — always safe.
        country_vals = {k: v for k, v in values.items() if k != "currency_id"}
        currency_vals = {k: v for k, v in values.items() if k == "currency_id"}

        if country_vals:
            client.write("res.company", [1], country_vals)

        if currency_vals:
            try:
                client.write("res.company", [1], currency_vals)
            except Exception:
                pass  # Currency already set by localisation module

        console.print(
            f"  [dim]country={country_code} currency={currency_name}[/dim]"
        )


# ─────────────────────────────────────────
# Admin user configuration
# ─────────────────────────────────────────


def _configure_admin_user(client: OdooClient) -> None:
    """Assign administrator groups to the Odoo admin user.

    In a fresh Odoo install with only ``base`` initialised, the admin
    user lacks the Inventory, Sales and Purchase administrator groups.
    These groups are created when the corresponding modules are installed
    but are not automatically assigned to existing users. This function
    assigns them explicitly so the admin user can operate across all
    installed apps without manual intervention.

    Uses the ``(4, id)`` many2many command to add without replacing
    existing group memberships.

    :param client: Authenticated Odoo client.
    """
    target_groups = [
        "Inventory/Administrator",
        "Sales/Administrator",
        "Purchase/Administrator",
    ]

    groups = client.search_read(
        "res.groups",
        [["full_name", "in", target_groups]],
        ["id", "full_name"],
    )

    assigned = []
    for group in groups:
        try:
            client.execute(
                "res.groups", "write", [group["id"]], {"users": [[4, 2]]}
            )
            assigned.append(group["full_name"])
        except Exception:
            pass  # Group may not exist if module is not installed

    if assigned:
        console.print(f"  [dim]groups assigned: {', '.join(assigned)}[/dim]")
    else:
        console.print("  [dim]no groups to assign[/dim]")


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

    VAT is formatted as required by Odoo with l10n_cl installed:
    ``CL`` prefix + RUT digits without dots + hyphen (e.g. ``CL76086428-5``).
    If Odoo rejects the VAT (e.g. too few digits), the partner is created
    without it.

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
        task = progress.add_task("Customers", total=customer_count)
        for _ in range(customer_count):
            raw_vat = getattr(fake, person_rut_method, fake.ssn)()
            vat = "CL" + raw_vat.replace(".", "")
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
            try:
                pid = client.create("res.partner", record)
            except Exception:
                record.pop("vat", None)
                pid = client.create("res.partner", record)
            partner_ids.append(pid)
            progress.advance(task)

        task = progress.add_task("Suppliers", total=supplier_count)
        for _ in range(supplier_count):
            raw_vat = getattr(fake, company_rut_method, fake.ssn)()
            vat = "CL" + raw_vat.replace(".", "")
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
            try:
                pid = client.create("res.partner", record)
            except Exception:
                record.pop("vat", None)
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
            sku_prefix = (
                industry_pack.get("products", {})
                .get("sku_prefix_by_category", {})
                .get(cat.get("code", "XX"), "PR")
            )
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


def _months_in_window(window: ObservationWindow) -> list[int]:
    """Return the distinct calendar months covered by *window*.

    :param window: :class:`~sandboxerp.engine.time_engine.ObservationWindow`.
    :return: Sorted list of month numbers (1–12), possibly with repeats
        across years collapsed to unique values.
    """
    months: list[int] = []
    current = date(window.start.year, window.start.month, 1)
    end_month = date(window.end.year, window.end.month, 1)
    while current <= end_month:
        if current.month not in months:
            months.append(current.month)
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)
    return sorted(months)


def _generate_transactions(
    client: OdooClient,
    *,
    country_pack: dict,
    industry_pack: dict,
    profile: str,
    seed: int,
    partner_ids: list[int],
    product_ids: list[int],
    window: ObservationWindow,
) -> None:
    """Generate causal ERP transaction chains distributed by seasonality
    and enriched with persona-consistent behaviour.

    Pipeline per chain:

    1. Distribute ``n_chains`` across active months via
       :func:`~sandboxerp.engine.seasonality.distribute_volume`.
    2. Assign a :class:`~sandboxerp.engine.persona_engine.Persona` to
       every partner via :class:`~sandboxerp.engine.persona_engine.PersonaEngine`.
    3. For each chain: enrich transactions with persona metadata
       (including ``payment_delay_extra`` on ``customer_invoice`` steps).
    4. Assign temporally coherent dates via
       :func:`~sandboxerp.engine.time_engine.assign_dates`, which reads
       ``payment_delay_extra`` from metadata automatically.
    5. Create the ``sale.order`` record in Odoo with ``date_order`` and
       a price scaled by the partner's ``amount_multiplier``.

    :param client: Authenticated Odoo client.
    :param country_pack: Loaded country pack dict.
    :param industry_pack: Loaded industry pack dict.
    :param profile: Scale profile name.
    :param seed: Random seed for reproducibility.
    :param partner_ids: List of available partner IDs.
    :param product_ids: List of available product template IDs.
    :param window: Observation window constraining document dates.
    """
    from datetime import timedelta

    rng = random.Random(seed)
    country = country_pack["meta"]["code"]
    industry = industry_pack["meta"]["code"]

    n_chains = (
        industry_pack.get("transactions", {})
        .get("so_chains_by_profile", {})
        .get(profile, 10)
    )

    # ── Persona Engine: assign personas to all partners ──────────────
    persona_engine = PersonaEngine(seed=seed)
    if partner_ids:
        persona_engine.assign(partner_ids)

    # ── Distribute total chains across months by seasonality ─────────
    active_months = _months_in_window(window)
    monthly_counts = distribute_volume(
        industry,
        annual_total=n_chains,
        months=active_months,
    )

    # Resolve pricelist for SO
    pricelist_ids = client.search("product.pricelist", [], limit=1)
    pricelist_id = pricelist_ids[0] if pricelist_ids else False

    created_so = 0
    total_chains = sum(monthly_counts.values())

    with Progress(
        TextColumn("  {task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Sale Orders", total=total_chains)

        for month, count in sorted(monthly_counts.items()):
            # Derive the correct year for this month within the window.
            # The window may span two calendar years (e.g. Jun 2023–Jun 2024);
            # prefer the year where the month falls inside the window.
            year = window.end.year if month <= window.end.month else window.start.year

            month_start = date(year, month, 1)
            if month == 12:
                month_end = date(year, 12, 31)
            else:
                month_end = date(year, month + 1, 1) - timedelta(days=1)

            month_window = ObservationWindow(
                start=max(month_start, window.start),
                end=min(month_end, window.end),
            )

            chains = generate_chain(
                seed=rng.randint(0, 2**31),
                country=country,
                industry=industry,
                profile=profile,
                n_chains=count,
            )

            for chain in chains:
                if not partner_ids or not product_ids:
                    break

                partner_id = rng.choice(partner_ids)
                product_id = rng.choice(product_ids)

                # ── Persona: enrich chain with partner behaviour ──────
                persona_engine.enrich_chain(chain, partner_id=partner_id)

                # ── Time Engine: assign coherent dates ────────────────
                dated_chain = assign_dates(chain, window=month_window, rng=rng)

                so_tx = next(
                    (t for t in dated_chain if t.type == "sale_order"), None
                )
                if not so_tx:
                    progress.advance(task)
                    continue

                # ── Amount: scale by persona multiplier ───────────────
                amount_multiplier = so_tx.metadata.get("amount_multiplier", 1.0)
                scaled_price = round(
                    so_tx.amount * amount_multiplier / rng.randint(1, 10), 2
                )

                try:
                    so_vals: dict[str, Any] = {
                        "partner_id": partner_id,
                        "date_order": so_tx.as_odoo_date(),
                        "order_line": [
                            (
                                0,
                                0,
                                {
                                    "product_id": product_id,
                                    "product_uom_qty": rng.randint(1, 10),
                                    "price_unit": scaled_price,
                                },
                            )
                        ],
                    }
                    if pricelist_id:
                        so_vals["pricelist_id"] = pricelist_id

                    client.create("sale.order", so_vals)
                    created_so += 1
                except OdooError:
                    pass

                progress.advance(task)

    if partner_ids:
        console.print(f"  [dim]{persona_engine.summary()}[/dim]")

    console.print(
        f"  [green]✓[/green] {created_so} sale orders "
        f"({len(active_months)} months, seasonality: {industry})"
    )
