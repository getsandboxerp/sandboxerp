"""
sandboxerp.engine.health
~~~~~~~~~~~~~~~~~~~~~~~~~

Post-generate environment health check for SandboxERP.

Queries the live Odoo instance to verify data consistency and display
a summary of the generated environment. Called by
:func:`~sandboxerp.engine.generator.generate_environment` after
:func:`~sandboxerp.engine.installer.install` completes.

:author: Hector Colina / Team360 <https://team360.cl>
"""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from typing import Any

from rich.console import Console

from sandboxerp.engine.odoo import OdooClient, OdooError

console = Console()

# Modules we report on if installed — order matters for display.
_REPORTABLE_MODULES = [
    "l10n_cl", "l10n_cl_edi", "l10n_cl_reports",
    "l10n_mx", "l10n_mx_edi", "l10n_mx_reports",
    "l10n_ar", "l10n_co", "l10n_pe",
    "sale_management", "purchase", "stock", "account",
]


def run_health_check(
    client: OdooClient,
    metrics: dict[str, Any],
) -> None:
    """Query Odoo and display a post-generate environment health summary.

    Receives installer metrics (counts already known) and queries only
    what is not available from the installer: dates, seasonality, totals,
    top partner/product, data quality indicators, and dataset hash.

    :param client: Authenticated :class:`~sandboxerp.engine.odoo.OdooClient`.
    :param metrics: Dict returned by :func:`~sandboxerp.engine.installer.install`
        containing ``customers``, ``suppliers``, ``products``, ``so_created``,
        ``so_confirmed``, ``so_invoiced``, ``so_paid``, ``country_pack``,
        ``industry_pack``.
    """
    console.print("\n[bold]→[/bold] Health check...")

    try:
        _print_company(client, metrics)
        _print_modules(client)
        _print_master_data(metrics)
        _print_date_range_and_seasonality(client)
        _print_causal_chain(metrics)
        _print_total_invoiced(client)
        _print_top_partner(client)
        _print_top_product(client)
        _print_data_quality(client)
        _print_dataset_hash(client)
    except OdooError as exc:
        console.print(f"  [yellow]⚠[/yellow]  Health check incomplete: {exc}")


# ─────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────

def _label(key: str) -> str:
    """Format a left-aligned label for the health check output.

    :param key: Short label string.
    :return: Left-padded label string.
    """
    return f"  [dim]{key:<16}[/dim]"


def _print_company(client: OdooClient, metrics: dict) -> None:
    """Print company name, currency and locale.

    :param client: Authenticated Odoo client.
    :param metrics: Installer metrics dict.
    """
    company = client.search_read(
        "res.company", [["id", "=", 1]],
        ["name", "country_id", "currency_id"],
    )
    if not company:
        return
    c = company[0]
    locale = metrics.get("country_pack", {}).get("meta", {}).get("locale", "")
    console.print(
        f"{_label('company')}"
        f"{c['name']} | {c['currency_id'][1]} | {locale}"
    )


def _print_modules(client: OdooClient) -> None:
    """Print installed localization and business modules.

    :param client: Authenticated Odoo client.
    """
    installed = client.search_read(
        "ir.module.module",
        [["state", "=", "installed"], ["name", "in", _REPORTABLE_MODULES]],
        ["name"],
    )
    names = [m["name"] for m in installed]
    version = client.version().get("server_version", "?")
    console.print(
        f"{_label('odoo')}"
        f"{version} · {' · '.join(names)}"
    )


def _print_master_data(metrics: dict) -> None:
    """Print master data counts from installer metrics.

    :param metrics: Installer metrics dict.
    """
    console.print(
        f"{_label('master data')}"
        f"{metrics.get('customers', '?')} customers · "
        f"{metrics.get('suppliers', '?')} suppliers · "
        f"{metrics.get('products', '?')} products"
    )


def _print_date_range_and_seasonality(client: OdooClient) -> None:
    """Print SO date range and peak/low months.

    :param client: Authenticated Odoo client.
    """
    sos = client.search_read(
        "sale.order",
        [["state", "=", "sale"]],
        ["date_order"],
    )
    if not sos:
        return

    months: Counter = Counter(so["date_order"][:7] for so in sos)
    date_from = min(months)
    date_to = max(months)
    n_months = len(months)
    peak_month, peak_count = months.most_common(1)[0]
    low_month, low_count = months.most_common()[-1]

    console.print(
        f"{_label('date range')}"
        f"{date_from} → {date_to}  ({n_months} months)"
    )
    console.print(
        f"{_label('seasonality')}"
        f"peak: {peak_month} ({peak_count})  ·  low: {low_month} ({low_count})"
    )


def _print_causal_chain(metrics: dict) -> None:
    """Print causal chain completion rates from installer metrics.

    :param metrics: Installer metrics dict.
    """
    total = metrics.get("so_created", "?")
    confirmed = metrics.get("so_confirmed", "?")
    invoiced = metrics.get("so_invoiced", "?")
    paid = metrics.get("so_paid", "?")
    console.print(
        f"{_label('causal chain')}"
        f"{confirmed}/{total} confirmed · "
        f"{invoiced}/{total} invoiced · "
        f"{paid}/{total} paid"
    )


def _print_total_invoiced(client: OdooClient) -> None:
    """Print total invoiced amount from posted invoices.

    Uses the company currency rather than the invoice currency to avoid
    discrepancies when the payment journal uses a different currency.

    :param client: Authenticated Odoo client.
    """
    invs = client.search_read(
        "account.move",
        [["move_type", "=", "out_invoice"], ["state", "=", "posted"]],
        ["amount_total"],
    )
    if not invs:
        return
    total = sum(i["amount_total"] for i in invs)
    company = client.search_read("res.company", [["id", "=", 1]], ["currency_id"])
    currency = company[0]["currency_id"][1] if company else ""
    console.print(
        f"{_label('total invoiced')}"
        f"{total:,.0f} {currency}"
    )


def _print_top_partner(client: OdooClient) -> None:
    """Print the partner with the highest total SO amount.

    :param client: Authenticated Odoo client.
    """
    sos = client.search_read(
        "sale.order",
        [["state", "=", "sale"]],
        ["partner_id", "amount_total"],
    )
    if not sos:
        return

    totals: dict = defaultdict(lambda: {"total": 0.0, "count": 0, "name": ""})
    for so in sos:
        pid = so["partner_id"][0]
        totals[pid]["total"] += so["amount_total"]
        totals[pid]["count"] += 1
        totals[pid]["name"] = so["partner_id"][1]

    top = max(totals.values(), key=lambda x: x["total"])
    company = client.search_read("res.company", [["id", "=", 1]], ["currency_id"])
    currency = company[0]["currency_id"][1] if company else ""
    console.print(
        f"{_label('top partner')}"
        f"{top['name']}  ({top['total']:,.0f} {currency} · {top['count']} orders)"
    )


def _print_top_product(client: OdooClient) -> None:
    """Print the product with the highest total quantity sold.

    :param client: Authenticated Odoo client.
    """
    lines = client.search_read(
        "sale.order.line",
        [],
        ["product_id", "product_uom_qty"],
    )
    if not lines:
        return

    totals: dict = defaultdict(lambda: {"qty": 0.0, "name": ""})
    for line in lines:
        pid = line["product_id"][0]
        totals[pid]["qty"] += line["product_uom_qty"]
        totals[pid]["name"] = line["product_id"][1]

    top = max(totals.values(), key=lambda x: x["qty"])
    console.print(
        f"{_label('top product')}"
        f"{top['name']}  ({top['qty']:.0f} units sold)"
    )


def _print_data_quality(client: OdooClient) -> None:
    """Print data quality indicators: negative stock and partners without VAT.

    :param client: Authenticated Odoo client.
    """
    neg_stock = client.search(
        "stock.quant",
        [["quantity", "<", 0], ["location_id.usage", "=", "internal"]],
    )
    no_vat = client.search(
        "res.partner",
        [["customer_rank", ">", 0], ["vat", "=", False],
         ["type", "=", "contact"], ["name", "!=", "My Company"]],
    )

    stock_icon = "[green]✓[/green] no negative stock" if not neg_stock else f"[dim]ℹ {len(neg_stock)} negative stock locations (expected in sandbox)[/dim]"
    vat_icon = "[green]✓[/green] all partners have VAT" if not no_vat else f"[yellow]⚠[/yellow] {len(no_vat)} partners missing VAT"

    console.print(
        f"{_label('data quality')}"
        f"{stock_icon}  ·  {vat_icon}"
    )


def _print_dataset_hash(client: OdooClient) -> None:
    """Print a short reproducible hash of the generated dataset.

    The hash is computed from SO count, total invoiced amount, and date range.
    Same seed + same country + same profile = same hash.

    :param client: Authenticated Odoo client.
    """
    sos = client.search_read(
        "sale.order", [["state", "=", "sale"]], ["date_order"]
    )
    invs = client.search_read(
        "account.move",
        [["move_type", "=", "out_invoice"], ["state", "=", "posted"]],
        ["amount_total"],
    )
    so_count = len(sos)
    total = sum(i["amount_total"] for i in invs)
    dates = sorted(so["date_order"][:7] for so in sos)
    date_from = dates[0] if dates else ""
    date_to = dates[-1] if dates else ""

    raw = f"{so_count}{total:.2f}{date_from}{date_to}"
    dataset_hash = hashlib.md5(raw.encode()).hexdigest()[:8]
    console.print(f"{_label('dataset hash')}{dataset_hash}")
