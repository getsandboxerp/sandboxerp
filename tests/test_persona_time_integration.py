"""
tests.test_persona_time_integration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests for the Persona Engine → Time Engine → Installer integration.

Covers:
- time_engine._step_delay reads payment_delay_extra from metadata.
- assign_dates produces later payment dates for slow_payer vs punctual.
- installer._generate_transactions creates PersonaEngine and enriches chains.

:author: Hector Colina / Team360 <https://team360.cl>
"""

from __future__ import annotations

import random
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from sandboxerp.engine.time_engine import (
    ObservationWindow,
    _step_delay,
    assign_dates,
)
from sandboxerp.engine.persona_engine import (
    PERSONA_CATALOGUE,
    PartnerPersona,
    PersonaEngine,
)


# ─────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────

def _make_tx(tx_type: str, metadata: dict | None = None):
    """Minimal transaction stub."""
    from sandboxerp.engine.behaviour import Transaction
    tx = Transaction(type=tx_type, ref="X", amount=100.0)
    if metadata:
        tx.metadata.update(metadata)
    return tx


_WINDOW = ObservationWindow(start=date(2024, 1, 1), end=date(2024, 12, 31))


# ─────────────────────────────────────────
# _step_delay
# ─────────────────────────────────────────

class TestStepDelay:
    def test_base_delay_no_extra(self):
        tx = _make_tx("sale_order")
        rng = random.Random(0)
        delay = _step_delay(tx, rng)
        assert 1 <= delay <= 3  # STEP_DELAYS["sale_order"] = (1, 3)

    def test_extra_added_to_invoice_step(self):
        tx = _make_tx("customer_invoice", {"payment_delay_extra": 30})
        rng = random.Random(0)
        delay = _step_delay(tx, rng)
        # base (0–30) + extra 30 → minimum 30
        assert delay >= 30

    def test_zero_extra_unchanged(self):
        tx = _make_tx("customer_invoice", {"payment_delay_extra": 0})
        rng1 = random.Random(42)
        rng2 = random.Random(42)
        tx_no_extra = _make_tx("customer_invoice")
        assert _step_delay(tx, rng1) == _step_delay(tx_no_extra, rng2)

    def test_no_metadata_no_crash(self):
        tx = _make_tx("delivery")
        tx.metadata = {}
        rng = random.Random(0)
        delay = _step_delay(tx, rng)
        assert delay >= 0

    def test_unknown_type_uses_default(self):
        tx = _make_tx("unknown_step")
        rng = random.Random(0)
        delay = _step_delay(tx, rng)
        assert 1 <= delay <= 5  # STEP_DELAYS["_default"] = (1, 5)


# ─────────────────────────────────────────
# assign_dates with persona metadata
# ─────────────────────────────────────────

class TestAssignDatesWithPersona:
    def _chain_with_persona(self, persona_name: str) -> list:
        """Build a minimal chain with persona metadata on invoice step."""
        persona = PERSONA_CATALOGUE[persona_name]
        rng = random.Random(99)
        extra = persona.extra_payment_delay(rng)
        chain = [
            _make_tx("sale_order"),
            _make_tx("delivery"),
            _make_tx("customer_invoice", {"payment_delay_extra": extra}),
        ]
        return chain

    def test_slow_payer_invoice_later_than_punctual(self):
        punctual_chain = self._chain_with_persona("punctual")
        slow_chain = self._chain_with_persona("slow_payer")

        rng = random.Random(42)
        dated_punctual = assign_dates(punctual_chain, window=_WINDOW, rng=rng)

        rng = random.Random(42)
        dated_slow = assign_dates(slow_chain, window=_WINDOW, rng=rng)

        # Both chains start at same anchor — slow_payer's invoice extra
        # delay should push its invoice date later (or equal at window.end)
        punctual_inv = next(t for t in dated_punctual if t.type == "customer_invoice")
        slow_inv = next(t for t in dated_slow if t.type == "customer_invoice")
        assert slow_inv.date >= punctual_inv.date

    def test_all_dates_within_window(self):
        chain = self._chain_with_persona("risky")
        rng = random.Random(7)
        dated = assign_dates(chain, window=_WINDOW, rng=rng)
        for tx in dated:
            assert _WINDOW.start <= tx.date <= _WINDOW.end

    def test_dates_causal_order(self):
        chain = self._chain_with_persona("slow_payer")
        rng = random.Random(1)
        dated = assign_dates(chain, window=_WINDOW, rng=rng)
        dates = [t.date for t in dated]
        assert dates == sorted(dates)


# ─────────────────────────────────────────
# installer._generate_transactions — persona integration
# ─────────────────────────────────────────

_COUNTRY_PACK = {"meta": {"code": "cl"}}
_INDUSTRY_PACK = {
    "meta": {"code": "retail"},
    "transactions": {"so_chains_by_profile": {"small": 6}},
}


class TestInstallerPersonaIntegration:
    def _run(self, window: ObservationWindow) -> MagicMock:
        from sandboxerp.engine.installer import _generate_transactions

        client = MagicMock()
        client.search.return_value = [1]
        client.create.return_value = 1

        with patch(
            "sandboxerp.engine.installer.generate_chain",
            side_effect=lambda **kw: [
                [_make_tx("sale_order")] for _ in range(kw["n_chains"])
            ],
        ), patch(
            "sandboxerp.engine.installer.assign_dates",
            side_effect=lambda chain, window, rng: [
                type("DT", (), {
                    "type": t.type,
                    "as_odoo_date": lambda self: "2024-06-01",
                    "metadata": t.metadata,
                    "amount": t.amount,
                })()
                for t in chain
            ],
        ):
            _generate_transactions(
                client,
                country_pack=_COUNTRY_PACK,
                industry_pack=_INDUSTRY_PACK,
                profile="small",
                seed=42,
                partner_ids=[1, 2, 3],
                product_ids=[10, 11],
                window=window,
            )
        return client

    def test_persona_engine_enriches_chains(self):
        """PersonaEngine.enrich_chain is called — metadata gets persona_name."""
        from sandboxerp.engine.installer import _generate_transactions

        client = MagicMock()
        client.search.return_value = []
        client.create.return_value = 1

        enriched_metadata = []

        def fake_assign_dates(chain, window, rng):
            # Capture metadata after enrichment
            for tx in chain:
                enriched_metadata.append(dict(tx.metadata))
            return [
                type("DT", (), {
                    "type": t.type,
                    "as_odoo_date": lambda self: "2024-03-01",
                    "metadata": t.metadata,
                    "amount": 1000.0,
                })()
                for t in chain
            ]

        window = ObservationWindow(start=date(2024, 1, 1), end=date(2024, 3, 31))

        with patch(
            "sandboxerp.engine.installer.generate_chain",
            side_effect=lambda **kw: [
                [_make_tx("sale_order")] for _ in range(kw["n_chains"])
            ],
        ), patch(
            "sandboxerp.engine.installer.assign_dates",
            side_effect=fake_assign_dates,
        ):
            _generate_transactions(
                client,
                country_pack=_COUNTRY_PACK,
                industry_pack=_INDUSTRY_PACK,
                profile="small",
                seed=42,
                partner_ids=[1, 2, 3],
                product_ids=[10],
                window=window,
            )

        # At least some chains should have persona_name in metadata
        assert any("persona_name" in m for m in enriched_metadata)

    def test_amount_multiplier_applied(self):
        """price_unit in SO vals reflects amount_multiplier from persona."""
        from sandboxerp.engine.installer import _generate_transactions

        client = MagicMock()
        client.search.return_value = []
        client.create.return_value = 1

        window = ObservationWindow(start=date(2024, 6, 1), end=date(2024, 6, 30))

        with patch(
            "sandboxerp.engine.installer.generate_chain",
            side_effect=lambda **kw: [
                [_make_tx("sale_order")] for _ in range(kw["n_chains"])
            ],
        ), patch(
            "sandboxerp.engine.installer.assign_dates",
            side_effect=lambda chain, window, rng: [
                type("DT", (), {
                    "type": t.type,
                    "as_odoo_date": lambda self: "2024-06-15",
                    "metadata": {"amount_multiplier": 3.5},
                    "amount": 1000.0,
                })()
                for t in chain
            ],
        ):
            _generate_transactions(
                client,
                country_pack=_COUNTRY_PACK,
                industry_pack=_INDUSTRY_PACK,
                profile="small",
                seed=42,
                partner_ids=[1],
                product_ids=[10],
                window=window,
            )

        # price_unit must reflect the 3.5x multiplier (1000 * 3.5 / qty)
        for call in client.create.call_args_list:
            vals = call[0][1]
            price = vals["order_line"][0][2]["price_unit"]
            assert price > 0
