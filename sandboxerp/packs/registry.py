"""
Pack registry for SandboxERP.

Maintains an in-memory catalogue of available packs (country, industry,
chaos) and exposes helpers to list and resolve them by name.

:author: Hector Colina / Team360 <https://team360.cl>
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class PackType(str, Enum):
    """Category of a SandboxERP pack.

    :cvar COUNTRY: Country-level pack (RUT, IVA, currency, regions).
    :cvar INDUSTRY: Industry-specific transaction patterns.
    :cvar CHAOS: Premium pack for broken/degraded environment testing.
    """

    COUNTRY = "country"
    INDUSTRY = "industry"
    CHAOS = "chaos"


@dataclass(frozen=True)
class PackMeta:
    """Metadata descriptor for a single pack.

    :param name: Unique pack identifier (e.g. ``"country_cl"``).
    :param type: :class:`PackType` category.
    :param label: Human-readable display name.
    :param countries: Country codes this pack applies to. Empty = all.
    :param premium: Whether the pack requires a premium license.
    """

    name: str
    type: PackType
    label: str
    countries: tuple[str, ...] = ()
    premium: bool = False


# ─────────────────────────────────────────
# Built-in pack catalogue
# ─────────────────────────────────────────

_REGISTRY: list[PackMeta] = [
    # Country packs
    PackMeta("country_cl", PackType.COUNTRY, "Chile (RUT, IVA, CLP)", countries=("cl",)),
    PackMeta("country_mx", PackType.COUNTRY, "Mexico (RFC, IVA, MXN)", countries=("mx",)),
    PackMeta("country_nl", PackType.COUNTRY, "Netherlands (BTW, EUR, nl_NL)", countries=("nl",)),
    PackMeta("country_pt", PackType.COUNTRY, "Portugal (NIF, IVA, EUR, pt_PT)", countries=("pt",)),
    PackMeta("country_ar", PackType.COUNTRY, "Argentina (CUIT, IVA, ARS)", countries=("ar",)),
    PackMeta("country_co", PackType.COUNTRY, "Colombia (NIT, IVA, COP)", countries=("co",)),
    PackMeta("country_pe", PackType.COUNTRY, "Peru (RUC, IGV, PEN)", countries=("pe",)),
    # Industry packs
    PackMeta("retail", PackType.INDUSTRY, "Retail (POS, inventory, pricing)"),
    PackMeta("accounting", PackType.INDUSTRY, "Accounting firm (invoices, reconciliation)"),
    PackMeta("manufacturing", PackType.INDUSTRY, "Manufacturing (BOM, MO, WC)"),
    PackMeta("services", PackType.INDUSTRY, "Professional services (timesheets, projects)"),
    # Chaos packs (premium)
    PackMeta("chaos_duplicates", PackType.CHAOS, "Duplicate records & partners", premium=True),
    PackMeta("chaos_acl", PackType.CHAOS, "Broken ACL / security rules", premium=True),
    PackMeta("chaos_crons", PackType.CHAOS, "Dead scheduled actions", premium=True),
]

_INDEX: dict[str, PackMeta] = {p.name: p for p in _REGISTRY}


# ─────────────────────────────────────────
# Public API
# ─────────────────────────────────────────


def list_packs(
    pack_type: Optional[PackType] = None,
    *,
    include_premium: bool = True,
) -> list[PackMeta]:
    """Return all registered packs, optionally filtered.

    :param pack_type: When provided, only packs of this type are returned.
    :param include_premium: When ``False``, premium packs are excluded.
    :return: List of matching :class:`PackMeta` entries.
    """
    result = _REGISTRY
    if pack_type is not None:
        result = [p for p in result if p.type == pack_type]
    if not include_premium:
        result = [p for p in result if not p.premium]
    return result


def get_pack(name: str) -> PackMeta:
    """Look up a pack by its unique name.

    :param name: Pack identifier (e.g. ``"country_cl"``).
    :return: Matching :class:`PackMeta`.
    :raises KeyError: If no pack with *name* is registered.
    """
    if name not in _INDEX:
        raise KeyError(
            f"Pack '{name}' is not registered. "
            f"Available: {', '.join(sorted(_INDEX))}"
        )
    return _INDEX[name]


def resolve_packs(country: str, industry: str) -> list[PackMeta]:
    """Return the ordered list of packs for a generation run.

    Resolves: country pack → industry pack (country-specific or generic).

    :param country: ISO country code.
    :param industry: Industry pack name.
    :return: Ordered list of :class:`PackMeta` to apply.
    """
    packs: list[PackMeta] = []

    # Layer 1: country pack
    country_key = f"country_{country}"
    if country_key in _INDEX:
        packs.append(_INDEX[country_key])

    # Layer 3: industry pack (country-specific variant first)
    industry_country_key = f"{industry}_{country}"
    if industry_country_key in _INDEX:
        packs.append(_INDEX[industry_country_key])
    elif industry in _INDEX:
        packs.append(_INDEX[industry])

    return packs
