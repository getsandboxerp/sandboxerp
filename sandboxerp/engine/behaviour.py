"""
Behaviour engine for SandboxERP — Layer 5.

Generates causally coherent ERP transaction chains:
Lead → Sales Order → Delivery → Invoice → Payment.

This module is the MVP implementation of the Behaviour Engine layer.
Time coherence (Layer 6) and Persona Engine (Layer 7) extend this base.

:author: Hector Colina / Team360 <https://team360.cl>
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Transaction:
    """Represents a single ERP transaction in a causal chain.

    :param type: Transaction type identifier (e.g. ``"lead"``, ``"sale_order"``).
    :param ref: Human-readable reference (e.g. ``"SO001"``).
    :param amount: Monetary amount associated with this transaction.
    :param parent_ref: Reference of the preceding transaction, if any.
    :param metadata: Arbitrary extra data for pack-specific extensions.
    """

    type: str
    ref: str
    amount: float
    parent_ref: Optional[str] = None
    metadata: dict = field(default_factory=dict)


def generate_chain(
    *,
    seed: int,
    country: str,
    industry: str,
    profile: str,
    n_chains: int = 10,
) -> list[list[Transaction]]:
    """Generate causal ERP transaction chains.

    Each chain follows the canonical flow:
    Lead → Sales Order → Delivery → Invoice → Payment.

    The number of chains and amounts are scaled by *profile*.

    :param seed: Random seed for reproducibility.
    :param country: ISO country code (used by localization packs).
    :param industry: Industry pack name (influences chain shape).
    :param profile: Scale profile (``small`` | ``medium`` | ``enterprise``).
    :param n_chains: Number of independent chains to generate.
    :return: List of chains; each chain is a list of :class:`Transaction`.
    """
    rng = random.Random(seed)
    scale = _profile_scale(profile)
    chains: list[list[Transaction]] = []

    for i in range(n_chains):
        chain_id = str(i + 1).zfill(4)
        base_amount = round(rng.uniform(500, 50_000) * scale, 2)

        lead = Transaction(
            type="lead",
            ref=f"CRM/{chain_id}",
            amount=0.0,
        )
        so = Transaction(
            type="sale_order",
            ref=f"SO/{chain_id}",
            amount=base_amount,
            parent_ref=lead.ref,
        )
        delivery = Transaction(
            type="delivery",
            ref=f"WH/OUT/{chain_id}",
            amount=0.0,
            parent_ref=so.ref,
        )
        invoice = Transaction(
            type="invoice",
            ref=f"INV/{chain_id}",
            amount=base_amount,
            parent_ref=so.ref,
        )
        payment = Transaction(
            type="payment",
            ref=f"PAY/{chain_id}",
            amount=base_amount,
            parent_ref=invoice.ref,
        )

        chains.append([lead, so, delivery, invoice, payment])

    return chains


def _profile_scale(profile: str) -> float:
    """Return a monetary scale multiplier for a given profile.

    :param profile: Scale profile name.
    :return: Float multiplier applied to generated amounts.
    """
    return {
        "small": 1.0,
        "medium": 5.0,
        "enterprise": 20.0,
        "benchmark": 50.0,
    }.get(profile, 1.0)
