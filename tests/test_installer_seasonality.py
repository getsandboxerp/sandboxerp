"""
tests.test_installer_seasonality
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests for the seasonality + time engine integration added to
:mod:`sandboxerp.engine.installer`.

Covers:
- ``_months_in_window`` correctness across different window spans.
- ``_generate_transactions`` distributes chains proportionally by month
  (via mocked dependencies — no Docker / Odoo required).

:author: Hector Colina / Team360 <https://team360.cl>
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from sandboxerp.engine.installer import _months_in_window
from sandboxerp.engine.time_engine import ObservationWindow


# ─────────────────────────────────────────
# _months_in_window
# ─────────────────────────────────────────


class TestMonthsInWindow:
    def test_single_month(self):
        window = ObservationWindow(
            start=date(2024, 3, 1),
            end=date(2024, 3, 31),
        )
        assert _months_in_window(window) == [3]

    def test_three_consecutive_months(self):
        window = ObservationWindow(
            start=date(2024, 1, 15),
            end=date(2024, 3, 20),
        )
        assert _months_in_window(window) == [1, 2, 3]

    def test_full_year(self):
        window = ObservationWindow(
            start=date(2023, 1, 1),
            end=date(2023, 12, 31),
        )
        assert _months_in_window(window) == list(range(1, 13))

    def test_year_boundary(self):
        window = ObservationWindow(
            start=date(2023, 11, 1),
            end=date(2024, 2, 28),
        )
        # Nov, Dec, Jan, Feb — but unique months only
        result = _months_in_window(window)
        assert set(result) == {11, 12, 1, 2}

    def test_returns_sorted(self):
        window = ObservationWindow(
            start=date(2024, 6, 1),
            end=date(2024, 9, 30),
        )
        result = _months_in_window(window)
        assert result == sorted(result)

    def test_no_duplicate_months(self):
        window = ObservationWindow(
            start=date(2023, 1, 1),
            end=date(2024, 12, 31),
        )
        result = _months_in_window(window)
        assert len(result) == len(set(result))


# ─────────────────────────────────────────
# _generate_transactions (mocked)
# ─────────────────────────────────────────


def _make_mock_chain(n: int = 1):
    """Return *n* minimal mock transaction chains with a sale_order step."""
    chains = []
    for i in range(n):
        tx = MagicMock()
        tx.type = "sale_order"
        tx.amount = 1000.0
        tx.ref = f"SO/{i:04d}"
        tx.parent_ref = None
        tx.metadata = {}
        chains.append([tx])
    return chains


class TestGenerateTransactionsSeasonality:
    """Verify that _generate_transactions uses seasonality distribution."""

    def _run(self, window: ObservationWindow, n_chains: int = 12) -> int:
        """Run _generate_transactions with fully mocked dependencies.

        Returns the number of ``client.create`` calls made (≈ sale orders).
        """
        from sandboxerp.engine.installer import _generate_transactions

        client = MagicMock()
        client.search.return_value = [1]
        client.create.return_value = 1

        country_pack = {"meta": {"code": "cl"}}
        industry_pack = {
            "meta": {"code": "retail"},
            "transactions": {
                "so_chains_by_profile": {"small": n_chains}
            },
        }

        with patch(
            "sandboxerp.engine.installer.generate_chain",
            side_effect=lambda **kw: _make_mock_chain(kw["n_chains"]),
        ), patch(
            "sandboxerp.engine.installer.assign_dates",
            side_effect=lambda chain, window, rng: chain,
        ):
            _generate_transactions(
                client,
                country_pack=country_pack,
                industry_pack=industry_pack,
                profile="small",
                seed=42,
                partner_ids=[1, 2, 3],
                product_ids=[10, 11, 12],
                window=window,
            )

        return client.create.call_count

    def test_total_sale_orders_matches_n_chains(self):
        window = ObservationWindow(
            start=date(2024, 1, 1),
            end=date(2024, 12, 31),
        )
        count = self._run(window, n_chains=60)
        # Allow ±12 rounding slack
        assert abs(count - 60) <= 12

    def test_single_month_window(self):
        window = ObservationWindow(
            start=date(2024, 6, 1),
            end=date(2024, 6, 30),
        )
        count = self._run(window, n_chains=20)
        assert abs(count - 20) <= 2

    def test_date_order_field_set(self):
        """sale.order create calls must include date_order."""
        from sandboxerp.engine.installer import _generate_transactions

        client = MagicMock()
        client.search.return_value = []
        client.create.return_value = 1

        country_pack = {"meta": {"code": "cl"}}
        industry_pack = {
            "meta": {"code": "retail"},
            "transactions": {"so_chains_by_profile": {"small": 3}},
        }

        window = ObservationWindow(
            start=date(2024, 3, 1),
            end=date(2024, 3, 31),
        )

        dated_tx = MagicMock()
        dated_tx.type = "sale_order"
        dated_tx.amount = 500.0
        dated_tx.as_odoo_date.return_value = "2024-03-15"

        with patch(
            "sandboxerp.engine.installer.generate_chain",
            return_value=[[dated_tx]],
        ), patch(
            "sandboxerp.engine.installer.assign_dates",
            return_value=[dated_tx],
        ):
            _generate_transactions(
                client,
                country_pack=country_pack,
                industry_pack=industry_pack,
                profile="small",
                seed=42,
                partner_ids=[1],
                product_ids=[10],
                window=window,
            )

        # Every create call must carry date_order
        for call in client.create.call_args_list:
            _, kwargs = call
            vals = call[0][1]  # second positional arg to create()
            assert "date_order" in vals

    def test_empty_partner_ids_skips_gracefully(self):
        from sandboxerp.engine.installer import _generate_transactions

        client = MagicMock()
        client.search.return_value = []

        window = ObservationWindow(
            start=date(2024, 1, 1),
            end=date(2024, 3, 31),
        )

        with patch(
            "sandboxerp.engine.installer.generate_chain",
            return_value=_make_mock_chain(5),
        ), patch("sandboxerp.engine.installer.assign_dates",
                 side_effect=lambda chain, window, rng: chain):
            _generate_transactions(
                client,
                country_pack={"meta": {"code": "cl"}},
                industry_pack={
                    "meta": {"code": "retail"},
                    "transactions": {"so_chains_by_profile": {"small": 5}},
                },
                profile="small",
                seed=42,
                partner_ids=[],   # empty — should not crash
                product_ids=[10],
                window=window,
            )

        client.create.assert_not_called()
