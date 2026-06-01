"""
sandboxerp.engine.persona_engine
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Persona Engine for SandboxERP — Layer 7.

Assigns consistent behavioural profiles to ERP partners (customers and
suppliers) so the synthetic dataset reflects realistic variance across
the customer base:

- A **punctual** customer always pays within terms.
- A **slow_payer** customer pays late, sometimes very late.
- A **high_value** customer places large orders infrequently.
- A **frequent** customer places small orders often.
- A **churned** customer has no recent activity.

These personas influence:

1. **Payment delay** — added to the ``customer_invoice`` step in
   :data:`~sandboxerp.engine.time_engine.STEP_DELAYS` via metadata.
2. **Amount multiplier** — scales the base transaction amount in
   :func:`~sandboxerp.engine.behaviour.generate_chain`.
3. **Chain frequency** — how many chains are generated for this partner
   relative to the average.

Usage::

    from sandboxerp.engine.persona_engine import assign_personas, PersonaEngine

    engine = PersonaEngine(seed=42)
    personas = engine.assign(partner_ids=[1, 2, 3, 4, 5])

    # Enrich a chain with persona metadata
    chain = engine.enrich_chain(chain, partner_id=1)

:author: Hector Colina / Team360 <https://team360.cl>
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional


# ─────────────────────────────────────────
# Persona definitions
# ─────────────────────────────────────────

@dataclass(frozen=True)
class Persona:
    """Immutable behavioural profile for a single partner.

    :param name: Persona type identifier (e.g. ``"punctual"``).
    :param payment_delay_min: Minimum extra payment delay in days
        (added on top of the base ``customer_invoice`` step delay).
    :param payment_delay_max: Maximum extra payment delay in days.
    :param amount_multiplier: Scales the base transaction amount.
        ``1.0`` = average; ``3.0`` = high-value; ``0.5`` = small buyer.
    :param frequency_multiplier: Scales how many chains are generated
        for this partner. ``2.0`` = twice as many orders as average.
    :param description: Human-readable description for documentation.
    """

    name: str
    payment_delay_min: int
    payment_delay_max: int
    amount_multiplier: float
    frequency_multiplier: float
    description: str = ""

    def __post_init__(self) -> None:
        if self.payment_delay_min > self.payment_delay_max:
            raise ValueError(
                f"payment_delay_min ({self.payment_delay_min}) must be "
                f"<= payment_delay_max ({self.payment_delay_max})."
            )
        if self.amount_multiplier <= 0:
            raise ValueError("amount_multiplier must be > 0.")
        if self.frequency_multiplier <= 0:
            raise ValueError("frequency_multiplier must be > 0.")

    def extra_payment_delay(self, rng: random.Random) -> int:
        """Sample an extra payment delay in days for this persona.

        :param rng: Seeded :class:`random.Random` instance.
        :return: Integer days to add to the base payment step delay.
        """
        return rng.randint(self.payment_delay_min, self.payment_delay_max)


# ─────────────────────────────────────────
# Built-in persona catalogue
# ─────────────────────────────────────────

#: Built-in persona catalogue.
#: Keys are persona names; values are :class:`Persona` instances.
PERSONA_CATALOGUE: dict[str, Persona] = {
    "punctual": Persona(
        name="punctual",
        payment_delay_min=0,
        payment_delay_max=5,
        amount_multiplier=1.0,
        frequency_multiplier=1.2,
        description="Pays on time or slightly early. Reliable, average order size.",
    ),
    "slow_payer": Persona(
        name="slow_payer",
        payment_delay_min=15,
        payment_delay_max=60,
        amount_multiplier=1.0,
        frequency_multiplier=0.9,
        description="Consistently pays late. High DSO risk.",
    ),
    "high_value": Persona(
        name="high_value",
        payment_delay_min=0,
        payment_delay_max=10,
        amount_multiplier=3.5,
        frequency_multiplier=0.6,
        description="Places large, infrequent orders. Pays on time.",
    ),
    "frequent": Persona(
        name="frequent",
        payment_delay_min=0,
        payment_delay_max=15,
        amount_multiplier=0.5,
        frequency_multiplier=2.5,
        description="Many small orders. Good payment behaviour.",
    ),
    "churned": Persona(
        name="churned",
        payment_delay_min=0,
        payment_delay_max=0,
        amount_multiplier=0.8,
        frequency_multiplier=0.1,
        description="Inactive customer. Very few recent transactions.",
    ),
    "risky": Persona(
        name="risky",
        payment_delay_min=30,
        payment_delay_max=120,
        amount_multiplier=1.5,
        frequency_multiplier=0.7,
        description="Large orders but very late payment. Credit risk profile.",
    ),
}

#: Probability weights for persona assignment (must align with
#: ``PERSONA_CATALOGUE`` key order).  Reflects a realistic customer mix:
#: most customers are average/punctual; a minority are risky or churned.
_DEFAULT_WEIGHTS: dict[str, float] = {
    "punctual":   0.35,
    "slow_payer": 0.20,
    "high_value": 0.10,
    "frequent":   0.20,
    "churned":    0.05,
    "risky":      0.10,
}


# ─────────────────────────────────────────
# Partner persona assignment
# ─────────────────────────────────────────

@dataclass
class PartnerPersona:
    """A partner ID bound to a :class:`Persona`.

    :param partner_id: Odoo partner record ID.
    :param persona: Assigned :class:`Persona`.
    """

    partner_id: int
    persona: Persona

    def to_metadata(self) -> dict:
        """Return a metadata dict suitable for injecting into a
        :class:`~sandboxerp.engine.behaviour.Transaction`.

        :return: Dict with ``persona_name``, ``payment_delay_extra``,
            ``amount_multiplier``, and ``frequency_multiplier`` keys.
        """
        return {
            "persona_name": self.persona.name,
            "amount_multiplier": self.persona.amount_multiplier,
            "frequency_multiplier": self.persona.frequency_multiplier,
        }


class PersonaEngine:
    """Assigns and tracks personas for a set of partner IDs.

    :param seed: Random seed for reproducible assignments.
    :param weights: Custom persona probability weights.  Must cover all
        keys in :data:`PERSONA_CATALOGUE`.  Defaults to
        :data:`_DEFAULT_WEIGHTS`.
    :param catalogue: Custom persona catalogue.  Defaults to
        :data:`PERSONA_CATALOGUE`.
    """

    def __init__(
        self,
        seed: int,
        weights: Optional[dict[str, float]] = None,
        catalogue: Optional[dict[str, Persona]] = None,
    ) -> None:
        self._rng = random.Random(seed)
        self._catalogue = catalogue or PERSONA_CATALOGUE
        self._weights = weights or _DEFAULT_WEIGHTS
        self._assignments: dict[int, PartnerPersona] = {}

        # Precompute ordered lists for random.choices
        self._persona_names = list(self._catalogue.keys())
        self._persona_weights = [
            self._weights.get(name, 1.0) for name in self._persona_names
        ]

    # ── Assignment ──────────────────────────────────────────────────

    def assign(self, partner_ids: list[int]) -> dict[int, PartnerPersona]:
        """Assign a persona to each partner ID.

        Assignments are **stable**: calling ``assign`` with the same
        partner IDs and seed always produces the same result.  IDs
        already assigned retain their persona.

        :param partner_ids: List of Odoo partner record IDs.
        :return: Dict mapping partner ID → :class:`PartnerPersona`.
        """
        for pid in partner_ids:
            if pid not in self._assignments:
                name = self._rng.choices(
                    self._persona_names,
                    weights=self._persona_weights,
                    k=1,
                )[0]
                persona = self._catalogue[name]
                self._assignments[pid] = PartnerPersona(
                    partner_id=pid, persona=persona
                )
        return dict(self._assignments)

    def get(self, partner_id: int) -> Optional[PartnerPersona]:
        """Return the :class:`PartnerPersona` for *partner_id*, or
        ``None`` if not yet assigned.

        :param partner_id: Odoo partner record ID.
        :return: :class:`PartnerPersona` or ``None``.
        """
        return self._assignments.get(partner_id)

    # ── Chain enrichment ────────────────────────────────────────────

    def enrich_chain(
        self,
        chain: list,
        *,
        partner_id: int,
    ) -> list:
        """Inject persona metadata into every transaction in *chain*.

        Modifies each transaction's ``metadata`` dict in-place with:

        - ``persona_name`` — the persona type.
        - ``amount_multiplier`` — scale factor for monetary amounts.
        - ``frequency_multiplier`` — scale factor for chain volume.
        - ``payment_delay_extra`` — extra days on the payment step
          (only added to transactions of type ``customer_invoice``).

        If *partner_id* has no assigned persona, the chain is returned
        unchanged.

        :param chain: List of transaction objects with a ``metadata``
            dict attribute (e.g. :class:`~sandboxerp.engine.behaviour.Transaction`).
        :param partner_id: Partner whose persona governs this chain.
        :return: The same list with metadata enriched in-place.
        """
        pp = self._assignments.get(partner_id)
        if pp is None:
            return chain

        base_meta = pp.to_metadata()
        extra_delay = pp.persona.extra_payment_delay(self._rng)

        for tx in chain:
            tx.metadata.update(base_meta)
            if tx.type == "customer_invoice":
                tx.metadata["payment_delay_extra"] = extra_delay

        return chain

    def chains_for_partner(self, partner_id: int, base_count: int) -> int:
        """Return the number of chains to generate for *partner_id*.

        Scales *base_count* by the partner's ``frequency_multiplier``,
        with a minimum of 1.

        :param partner_id: Partner ID (must have been assigned first).
        :param base_count: Average chains per partner.
        :return: Adjusted chain count, minimum 1.
        """
        pp = self._assignments.get(partner_id)
        if pp is None:
            return base_count
        return max(1, round(base_count * pp.persona.frequency_multiplier))

    # ── Introspection ───────────────────────────────────────────────

    def distribution(self) -> dict[str, int]:
        """Return a count of assigned personas.

        :return: Dict mapping persona name → number of partners assigned.
        """
        counts: dict[str, int] = {name: 0 for name in self._catalogue}
        for pp in self._assignments.values():
            counts[pp.persona.name] = counts.get(pp.persona.name, 0) + 1
        return counts

    def summary(self) -> str:
        """Return a human-readable summary of persona distribution.

        :return: Multi-line string with counts and percentages.
        """
        total = len(self._assignments)
        if total == 0:
            return "No partners assigned."
        lines = [f"Persona distribution ({total} partners):"]
        for name, count in sorted(self.distribution().items()):
            pct = 100 * count / total
            lines.append(f"  {name:<14} {count:>4}  ({pct:.1f}%)")
        return "\n".join(lines)


# ─────────────────────────────────────────
# Convenience function
# ─────────────────────────────────────────

def assign_personas(
    partner_ids: list[int],
    *,
    seed: int,
    weights: Optional[dict[str, float]] = None,
) -> dict[int, PartnerPersona]:
    """Assign personas to *partner_ids* and return the mapping.

    Convenience wrapper around :class:`PersonaEngine` for one-shot use.

    :param partner_ids: List of Odoo partner record IDs.
    :param seed: Random seed for reproducibility.
    :param weights: Optional custom probability weights.
    :return: Dict mapping partner ID → :class:`PartnerPersona`.
    """
    engine = PersonaEngine(seed=seed, weights=weights)
    return engine.assign(partner_ids)
