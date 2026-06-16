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

# Length to truncate ISO date strings to for year-month comparisons
# (e.g. "2025-03-15" -> "2025-03"). Used consistently for both SO
# date_order and invoice invoice_date so date-range comparisons are
# apples-to-apples.
_YEAR_MONTH_LEN = 7

# Heuristics for detecting the invoice_date-defaults-to-today() bug
# (see _print_invoice_date_range). Tunable without touching logic.
_INVOICE_DATE_MIN_SAMPLE = 5  # below this, a single shared date is not unusual
_INVOICE_DATE_COLLAPSE_RATIO = 0.5  # share of invoices on one date to flag as collapsed


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
        _print_invoice_date_range(client)
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

    months: Counter = Counter(so["date_order"][:_YEAR_MONTH_LEN] for so in sos)
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


def _print_invoice_date_range(client: OdooClient) -> None:
    """Print invoice date range and flag mismatches against SO dates.

    This is the validation that would have caught the v0.2.7 invoice_date
    bug: Odoo 17 defaults ``invoice_date`` to ``today()`` on ``action_post``
    when it isn't set explicitly, so a broken environment shows invoices
    clustered on the generation date instead of spread across the Time
    Engine's intended range.

    Flags two conditions:

    - Unique invoice dates collapsing to very few values relative to
      invoice count (suggests defaulted dates).
    - Invoice date range not overlapping the SO date range at all.

    :param client: Authenticated Odoo client.
    """
    invs = client.search_read(
        "account.move",
        [["move_type", "=", "out_invoice"], ["state", "=", "posted"]],
        ["invoice_date"],
    )
    if not invs:
        console.print(
            f"{_label('invoice dates')}"
            f"[dim]ℹ no posted invoices yet[/dim]"
        )
        return

    inv_dates = [i["invoice_date"] for i in invs if i.get("invoice_date")]
    if not inv_dates:
        console.print(
            f"{_label('invoice dates')}"
            f"[yellow]⚠[/yellow] posted invoices found but invoice_date is unset on all of them"
        )
        return

    unique_dates = sorted(set(inv_dates))
    date_from = unique_dates[0]
    date_to = unique_dates[-1]
    n_unique = len(unique_dates)
    n_invoices = len(inv_dates)

    # Heuristic: if most invoices share the same date and there are more
    # than a handful of invoices, that's the today()-default signature.
    most_common_date, most_common_count = Counter(inv_dates).most_common(1)[0]
    collapsed = (
        n_invoices >= _INVOICE_DATE_MIN_SAMPLE
        and most_common_count / n_invoices > _INVOICE_DATE_COLLAPSE_RATIO
    )

    sos = client.search_read(
        "sale.order", [["state", "=", "sale"]], ["date_order"]
    )
    so_dates = (
        sorted(so["date_order"][:_YEAR_MONTH_LEN] for so in sos) if sos else []
    )
    so_from = so_dates[0] if so_dates else None
    so_to = so_dates[-1] if so_dates else None

    inv_from_ym = date_from[:_YEAR_MONTH_LEN]
    inv_to_ym = date_to[:_YEAR_MONTH_LEN]
    range_mismatch = bool(
        so_from and so_to and (inv_to_ym < so_from or inv_from_ym > so_to)
    )

    if collapsed or range_mismatch:
        reason = (
            f"{most_common_count}/{n_invoices} invoices share date {most_common_date}"
            if collapsed
            else f"invoice range [{date_from} → {date_to}] doesn't overlap SO range [{so_from} → {so_to}]"
        )
        console.print(
            f"{_label('invoice dates')}"
            f"[yellow]⚠[/yellow] {date_from} → {date_to}  ({n_unique} unique / {n_invoices} invoices) "
            f"— possible invoice_date default bug: {reason}"
        )
    else:
        console.print(
            f"{_label('invoice dates')}"
            f"[green]✓[/green] {date_from} → {date_to}  ({n_unique} unique / {n_invoices} invoices)"
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
    dates = sorted(so["date_order"][:_YEAR_MONTH_LEN] for so in sos)
    date_from = dates[0] if dates else ""
    date_to = dates[-1] if dates else ""

    raw = f"{so_count}{total:.2f}{date_from}{date_to}"
    dataset_hash = hashlib.md5(raw.encode()).hexdigest()[:8]
    console.print(f"{_label('dataset hash')}{dataset_hash}")
