"""
tests.test_persona_engine
~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for sandboxerp.engine.persona_engine.

:author: Hector Colina / Team360 <https://team360.cl>
"""

from __future__ import annotations

import random

import pytest

from sandboxerp.engine.persona_engine import (
    PERSONA_CATALOGUE,
    PartnerPersona,
    Persona,
    PersonaEngine,
    assign_personas,
)


# ─────────────────────────────────────────
# Persona dataclass
# ─────────────────────────────────────────

class TestPersona:
    def test_valid_persona(self):
        p = Persona(
            name="test",
            payment_delay_min=0,
            payment_delay_max=10,
            amount_multiplier=1.0,
            frequency_multiplier=1.0,
        )
        assert p.name == "test"

    def test_rejects_inverted_delays(self):
        with pytest.raises(ValueError, match="payment_delay_min"):
            Persona(
                name="bad",
                payment_delay_min=20,
                payment_delay_max=5,
                amount_multiplier=1.0,
                frequency_multiplier=1.0,
            )

    def test_rejects_zero_amount_multiplier(self):
        with pytest.raises(ValueError, match="amount_multiplier"):
            Persona(
                name="bad",
                payment_delay_min=0,
                payment_delay_max=5,
                amount_multiplier=0.0,
                frequency_multiplier=1.0,
            )

    def test_rejects_zero_frequency_multiplier(self):
        with pytest.raises(ValueError, match="frequency_multiplier"):
            Persona(
                name="bad",
                payment_delay_min=0,
                payment_delay_max=5,
                amount_multiplier=1.0,
                frequency_multiplier=0.0,
            )

    def test_extra_payment_delay_within_bounds(self):
        p = Persona(
            name="test",
            payment_delay_min=5,
            payment_delay_max=15,
            amount_multiplier=1.0,
            frequency_multiplier=1.0,
        )
        rng = random.Random(42)
        for _ in range(50):
            delay = p.extra_payment_delay(rng)
            assert 5 <= delay <= 15

    def test_equal_min_max_always_same(self):
        p = Persona(
            name="fixed",
            payment_delay_min=7,
            payment_delay_max=7,
            amount_multiplier=1.0,
            frequency_multiplier=1.0,
        )
        rng = random.Random(0)
        assert p.extra_payment_delay(rng) == 7


# ─────────────────────────────────────────
# PERSONA_CATALOGUE
# ─────────────────────────────────────────

class TestPersonaCatalogue:
    def test_all_expected_personas_present(self):
        for name in ("punctual", "slow_payer", "high_value", "frequent", "churned", "risky"):
            assert name in PERSONA_CATALOGUE

    def test_all_personas_valid(self):
        for name, persona in PERSONA_CATALOGUE.items():
            assert isinstance(persona, Persona)
            assert persona.name == name
            assert persona.amount_multiplier > 0
            assert persona.frequency_multiplier > 0

    def test_slow_payer_has_higher_delay_than_punctual(self):
        assert (
            PERSONA_CATALOGUE["slow_payer"].payment_delay_min
            > PERSONA_CATALOGUE["punctual"].payment_delay_max
        )

    def test_high_value_has_higher_amount_than_frequent(self):
        assert (
            PERSONA_CATALOGUE["high_value"].amount_multiplier
            > PERSONA_CATALOGUE["frequent"].amount_multiplier
        )

    def test_frequent_has_higher_frequency_than_churned(self):
        assert (
            PERSONA_CATALOGUE["frequent"].frequency_multiplier
            > PERSONA_CATALOGUE["churned"].frequency_multiplier
        )


# ─────────────────────────────────────────
# PartnerPersona
# ─────────────────────────────────────────

class TestPartnerPersona:
    def test_to_metadata_keys(self):
        pp = PartnerPersona(
            partner_id=1,
            persona=PERSONA_CATALOGUE["punctual"],
        )
        meta = pp.to_metadata()
        assert "persona_name" in meta
        assert "amount_multiplier" in meta
        assert "frequency_multiplier" in meta

    def test_to_metadata_values(self):
        pp = PartnerPersona(
            partner_id=5,
            persona=PERSONA_CATALOGUE["high_value"],
        )
        meta = pp.to_metadata()
        assert meta["persona_name"] == "high_value"
        assert meta["amount_multiplier"] == PERSONA_CATALOGUE["high_value"].amount_multiplier


# ─────────────────────────────────────────
# PersonaEngine — assign
# ─────────────────────────────────────────

class TestPersonaEngineAssign:
    def test_assigns_all_partners(self):
        engine = PersonaEngine(seed=42)
        ids = [1, 2, 3, 4, 5]
        result = engine.assign(ids)
        assert set(result.keys()) == set(ids)

    def test_all_assigned_are_partner_persona(self):
        engine = PersonaEngine(seed=0)
        result = engine.assign([10, 20, 30])
        assert all(isinstance(v, PartnerPersona) for v in result.values())

    def test_assignment_is_stable(self):
        engine = PersonaEngine(seed=7)
        ids = list(range(1, 11))
        first = engine.assign(ids)
        second = engine.assign(ids)
        for pid in ids:
            assert first[pid].persona.name == second[pid].persona.name

    def test_reproducible_across_engines(self):
        ids = list(range(1, 21))
        e1 = PersonaEngine(seed=99)
        e2 = PersonaEngine(seed=99)
        r1 = e1.assign(ids)
        r2 = e2.assign(ids)
        for pid in ids:
            assert r1[pid].persona.name == r2[pid].persona.name

    def test_different_seeds_differ(self):
        ids = list(range(1, 51))
        e1 = PersonaEngine(seed=1)
        e2 = PersonaEngine(seed=2)
        r1 = e1.assign(ids)
        r2 = e2.assign(ids)
        # With 50 partners, at least some assignment should differ
        assert any(r1[pid].persona.name != r2[pid].persona.name for pid in ids)

    def test_get_returns_none_for_unassigned(self):
        engine = PersonaEngine(seed=0)
        assert engine.get(9999) is None

    def test_get_returns_assigned(self):
        engine = PersonaEngine(seed=0)
        engine.assign([42])
        assert engine.get(42) is not None
        assert engine.get(42).partner_id == 42


# ─────────────────────────────────────────
# PersonaEngine — enrich_chain
# ─────────────────────────────────────────

class _FakeTx:
    """Minimal transaction stub for enrichment tests."""
    def __init__(self, tx_type: str):
        self.type = tx_type
        self.metadata: dict = {}


class TestPersonaEngineEnrichChain:
    def test_enriches_metadata(self):
        engine = PersonaEngine(seed=42)
        engine.assign([1])
        chain = [_FakeTx("sale_order"), _FakeTx("customer_invoice")]
        engine.enrich_chain(chain, partner_id=1)
        for tx in chain:
            assert "persona_name" in tx.metadata
            assert "amount_multiplier" in tx.metadata

    def test_payment_delay_only_on_invoice(self):
        engine = PersonaEngine(seed=42)
        engine.assign([1])
        so = _FakeTx("sale_order")
        inv = _FakeTx("customer_invoice")
        engine.enrich_chain([so, inv], partner_id=1)
        assert "payment_delay_extra" not in so.metadata
        assert "payment_delay_extra" in inv.metadata

    def test_unassigned_partner_returns_chain_unchanged(self):
        engine = PersonaEngine(seed=0)
        chain = [_FakeTx("sale_order")]
        result = engine.enrich_chain(chain, partner_id=9999)
        assert result[0].metadata == {}

    def test_modifies_in_place(self):
        engine = PersonaEngine(seed=1)
        engine.assign([5])
        tx = _FakeTx("sale_order")
        chain = [tx]
        engine.enrich_chain(chain, partner_id=5)
        assert tx.metadata.get("persona_name") is not None


# ─────────────────────────────────────────
# PersonaEngine — chains_for_partner
# ─────────────────────────────────────────

class TestChainsForPartner:
    def test_frequent_more_than_base(self):
        engine = PersonaEngine(seed=0)
        # Force frequent persona
        from sandboxerp.engine.persona_engine import PartnerPersona, PERSONA_CATALOGUE
        engine._assignments[1] = PartnerPersona(1, PERSONA_CATALOGUE["frequent"])
        assert engine.chains_for_partner(1, base_count=10) > 10

    def test_churned_less_than_base(self):
        engine = PersonaEngine(seed=0)
        from sandboxerp.engine.persona_engine import PartnerPersona, PERSONA_CATALOGUE
        engine._assignments[2] = PartnerPersona(2, PERSONA_CATALOGUE["churned"])
        assert engine.chains_for_partner(2, base_count=10) < 10

    def test_minimum_one(self):
        engine = PersonaEngine(seed=0)
        from sandboxerp.engine.persona_engine import PartnerPersona, PERSONA_CATALOGUE
        engine._assignments[3] = PartnerPersona(3, PERSONA_CATALOGUE["churned"])
        assert engine.chains_for_partner(3, base_count=1) >= 1

    def test_unassigned_returns_base(self):
        engine = PersonaEngine(seed=0)
        assert engine.chains_for_partner(9999, base_count=5) == 5


# ─────────────────────────────────────────
# PersonaEngine — distribution / summary
# ─────────────────────────────────────────

class TestDistributionAndSummary:
    def test_distribution_sums_to_total(self):
        engine = PersonaEngine(seed=42)
        ids = list(range(1, 101))
        engine.assign(ids)
        assert sum(engine.distribution().values()) == 100

    def test_distribution_all_keys_present(self):
        engine = PersonaEngine(seed=0)
        engine.assign([1, 2, 3])
        dist = engine.distribution()
        for name in PERSONA_CATALOGUE:
            assert name in dist

    def test_summary_no_assignments(self):
        engine = PersonaEngine(seed=0)
        assert "No partners" in engine.summary()

    def test_summary_contains_persona_names(self):
        engine = PersonaEngine(seed=0)
        engine.assign(list(range(1, 21)))
        summary = engine.summary()
        assert "punctual" in summary
        assert "%" in summary


# ─────────────────────────────────────────
# assign_personas convenience function
# ─────────────────────────────────────────

class TestAssignPersonas:
    def test_returns_mapping(self):
        result = assign_personas([1, 2, 3], seed=42)
        assert len(result) == 3

    def test_reproducible(self):
        r1 = assign_personas([1, 2, 3, 4, 5], seed=7)
        r2 = assign_personas([1, 2, 3, 4, 5], seed=7)
        for pid in [1, 2, 3, 4, 5]:
            assert r1[pid].persona.name == r2[pid].persona.name

    def test_custom_weights_accepted(self):
        weights = {
            "punctual": 1.0,
            "slow_payer": 0.0,
            "high_value": 0.0,
            "frequent": 0.0,
            "churned": 0.0,
            "risky": 0.0,
        }
        result = assign_personas(list(range(1, 20)), seed=0, weights=weights)
        assert all(pp.persona.name == "punctual" for pp in result.values())
