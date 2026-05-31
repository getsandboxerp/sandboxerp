"""
tests.test_time_engine
~~~~~~~~~~~~~~~~~~~~~~

Unit tests for the SandboxERP Time Engine (Layer 6).

Covers:
- ObservationWindow: construction, validation, random_date, clamp.
- DatedTransaction: construction, as_odoo_date.
- assign_dates: date ordering, window bounds, empty chain, single step.
- assign_dates_to_chains: bulk processing.

:author: Hector Colina / Team360 <https://team360.cl>
"""

from __future__ import annotations

import random
from datetime import date, timedelta

import pytest

from sandboxerp.engine.time_engine import (
    DatedTransaction,
    ObservationWindow,
    assign_dates,
    assign_dates_to_chains,
)
from sandboxerp.engine.behaviour import generate_chain


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rng(seed: int = 42) -> random.Random:
    return random.Random(seed)


def _window(months: int = 12) -> ObservationWindow:
    return ObservationWindow.last_n_months(months)


# ---------------------------------------------------------------------------
# ObservationWindow
# ---------------------------------------------------------------------------

class TestObservationWindow:
    def test_last_n_months_returns_window(self):
        w = ObservationWindow.last_n_months(12)
        assert isinstance(w, ObservationWindow)
        assert w.start < w.end

    def test_end_never_in_future(self):
        future = date.today() + timedelta(days=30)
        w = ObservationWindow(start=date.today() - timedelta(days=10), end=future)
        assert w.end <= date.today()

    def test_start_gt_end_raises(self):
        with pytest.raises(ValueError):
            ObservationWindow(
                start=date.today(),
                end=date.today() - timedelta(days=1),
            )

    def test_n_less_than_1_raises(self):
        with pytest.raises(ValueError):
            ObservationWindow.last_n_months(0)

    def test_span_days_positive(self):
        w = _window(6)
        assert w.span_days > 0

    def test_random_date_within_bounds(self):
        w = _window(12)
        rng = _rng()
        for _ in range(50):
            d = w.random_date(rng)
            assert w.start <= d <= w.end

    def test_random_date_reproducible(self):
        w = _window(12)
        d1 = w.random_date(_rng(42))
        d2 = w.random_date(_rng(42))
        assert d1 == d2

    def test_clamp_below_start(self):
        w = _window(6)
        early = w.start - timedelta(days=10)
        assert w.clamp(early) == w.start

    def test_clamp_above_end(self):
        w = _window(6)
        late = w.end + timedelta(days=10)
        assert w.clamp(late) == w.end

    def test_clamp_within_returns_same(self):
        w = _window(6)
        mid = w.start + timedelta(days=w.span_days // 2)
        assert w.clamp(mid) == mid


# ---------------------------------------------------------------------------
# DatedTransaction
# ---------------------------------------------------------------------------

class TestDatedTransaction:
    def test_as_odoo_date_format(self):
        tx = DatedTransaction(
            type="sale_order",
            ref="SO/0001",
            amount=1000.0,
            date=date(2024, 6, 15),
        )
        assert tx.as_odoo_date() == "2024-06-15"

    def test_as_odoo_date_none(self):
        tx = DatedTransaction(type="sale_order", ref="SO/0001", amount=0.0)
        assert tx.as_odoo_date() == ""

    def test_metadata_defaults_to_empty_dict(self):
        tx = DatedTransaction(type="lead", ref="CRM/0001", amount=0.0)
        assert tx.metadata == {}


# ---------------------------------------------------------------------------
# assign_dates
# ---------------------------------------------------------------------------

class TestAssignDates:
    def test_returns_same_length_as_input(self):
        chains = generate_chain(seed=42, country="cl", industry="retail", profile="small", n_chains=1)
        chain = chains[0]
        dated = assign_dates(chain, window=_window(), rng=_rng())
        assert len(dated) == len(chain)

    def test_all_dates_within_window(self):
        chains = generate_chain(seed=42, country="cl", industry="retail", profile="small", n_chains=5)
        w = _window(12)
        for chain in chains:
            dated = assign_dates(chain, window=w, rng=_rng())
            for tx in dated:
                assert tx.date is not None
                assert w.start <= tx.date <= w.end, (
                    f"{tx.type} date {tx.date} outside window [{w.start}, {w.end}]"
                )

    def test_dates_are_non_decreasing(self):
        """Each step must be on or after the previous step."""
        chains = generate_chain(seed=42, country="cl", industry="retail", profile="small", n_chains=10)
        w = _window(12)
        for chain in chains:
            dated = assign_dates(chain, window=w, rng=_rng())
            for i in range(1, len(dated)):
                assert dated[i].date >= dated[i - 1].date, (
                    f"{dated[i].type} ({dated[i].date}) before "
                    f"{dated[i-1].type} ({dated[i-1].date})"
                )

    def test_empty_chain_returns_empty(self):
        result = assign_dates([], window=_window(), rng=_rng())
        assert result == []

    def test_single_step_chain(self):
        chains = generate_chain(seed=0, country="cl", industry="retail", profile="small", n_chains=1)
        single = chains[0][:1]
        dated = assign_dates(single, window=_window(), rng=_rng())
        assert len(dated) == 1
        assert dated[0].date is not None

    def test_reproducible_with_same_seed(self):
        chains = generate_chain(seed=42, country="cl", industry="retail", profile="small", n_chains=3)
        w = _window(12)
        dated1 = [assign_dates(c, window=w, rng=_rng(42)) for c in chains]
        dated2 = [assign_dates(c, window=w, rng=_rng(42)) for c in chains]
        for c1, c2 in zip(dated1, dated2):
            for t1, t2 in zip(c1, c2):
                assert t1.date == t2.date

    def test_different_seeds_produce_different_dates(self):
        chains = generate_chain(seed=42, country="cl", industry="retail", profile="small", n_chains=1)
        w = _window(12)
        dated1 = assign_dates(chains[0], window=w, rng=_rng(1))
        dated2 = assign_dates(chains[0], window=w, rng=_rng(99))
        # At least the anchor date should differ
        dates1 = [t.date for t in dated1]
        dates2 = [t.date for t in dated2]
        assert dates1 != dates2

    def test_preserves_transaction_fields(self):
        chains = generate_chain(seed=42, country="cl", industry="retail", profile="small", n_chains=1)
        chain = chains[0]
        dated = assign_dates(chain, window=_window(), rng=_rng())
        for original, dt in zip(chain, dated):
            assert dt.type == original.type
            assert dt.ref == original.ref
            assert dt.amount == original.amount

    def test_no_date_in_future(self):
        chains = generate_chain(seed=42, country="cl", industry="retail", profile="small", n_chains=20)
        w = _window(12)
        today = date.today()
        for chain in chains:
            dated = assign_dates(chain, window=w, rng=_rng())
            for tx in dated:
                assert tx.date <= today, f"{tx.type} has future date {tx.date}"


# ---------------------------------------------------------------------------
# assign_dates_to_chains
# ---------------------------------------------------------------------------

class TestAssignDatesToChains:
    def test_returns_same_number_of_chains(self):
        chains = generate_chain(seed=42, country="cl", industry="retail", profile="small", n_chains=5)
        w = _window(12)
        dated = assign_dates_to_chains(chains, window=w, rng=_rng())
        assert len(dated) == len(chains)

    def test_each_chain_has_correct_length(self):
        chains = generate_chain(seed=42, country="cl", industry="retail", profile="small", n_chains=5)
        w = _window(12)
        dated = assign_dates_to_chains(chains, window=w, rng=_rng())
        for original, d in zip(chains, dated):
            assert len(d) == len(original)

    def test_all_dates_within_window(self):
        chains = generate_chain(seed=42, country="cl", industry="retail", profile="small", n_chains=10)
        w = _window(12)
        dated = assign_dates_to_chains(chains, window=w, rng=_rng())
        for chain in dated:
            for tx in chain:
                assert w.start <= tx.date <= w.end

    def test_empty_input_returns_empty(self):
        result = assign_dates_to_chains([], window=_window(), rng=_rng())
        assert result == []
