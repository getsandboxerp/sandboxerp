"""
tests.test_installer
~~~~~~~~~~~~~~~~~~~~

Unit tests for the SandboxERP installer engine.

All Odoo XML-RPC calls and pack loading are mocked — no real Odoo
instance or Docker environment is required.

:author: Hector Colina / Team360 <https://team360.cl>
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, call, patch

import pytest

from sandboxerp.engine.installer import (
    ODOO_DB,
    _configure_company,
    _configure_language,
    _generate_partners,
    _generate_products,
    _generate_transactions,
    _install_modules,
    _wait_for_xmlrpc,
    install,
)
from sandboxerp.engine.odoo import OdooError
from sandboxerp.engine.time_engine import ObservationWindow

# ─────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────

_COUNTRY_PACK = {
    "meta": {"code": "cl", "name": "Chile", "locale": "es_CL"},
    "localization": {
        "odoo_modules": {"install_order": ["l10n_cl", "l10n_cl_edi"]},
        "currency": "CLP",
        "country_code": "CL",
    },
    "fiscal": {
        "faker_person_id": "person_rut",
        "faker_company_id": "company_rut",
    },
}

_INDUSTRY_PACK = {
    "meta": {
        "code": "retail",
        "name": "Retail",
        "odoo_modules": {"install_order": ["sale_management", "stock"]},
    },
    "customers": {"count_by_profile": {"small": 5, "medium": 20}},
    "suppliers": {"count_by_profile": {"small": 3, "medium": 10}},
    "products": {
        "type": "product",
        "count_by_profile": {"small": 5, "medium": 20},
        "categories": [
            {"code": "ELEC", "price_range": [10000, 50000], "margin_pct": 0.25}
        ],
        "sku_prefix_by_category": {"ELEC": "EL"},
    },
    "transactions": {"so_chains_by_profile": {"small": 3, "medium": 10}},
}

# Shared observation window for transaction tests.
_WINDOW = ObservationWindow(
    start=date(2024, 1, 1),
    end=date(2024, 12, 31),
)


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.uid = 1
    client.module_is_installed.return_value = False
    client.search.return_value = [1]
    client.create.return_value = 42
    client.write.return_value = True
    return client


# ─────────────────────────────────────────
# _wait_for_xmlrpc
# ─────────────────────────────────────────

class TestWaitForXmlrpc:
    def test_returns_client_on_first_try(self):
        mock_client = MagicMock()
        with patch(
            "sandboxerp.engine.installer.OdooClient.connect_and_authenticate",
            return_value=mock_client,
        ):
            result = _wait_for_xmlrpc(host="127.0.0.1", port=8069, timeout=5)
        assert result is mock_client

    def test_raises_runtime_error_on_timeout(self):
        with patch(
            "sandboxerp.engine.installer.OdooClient.connect_and_authenticate",
            side_effect=OdooError("not ready"),
        ):
            with pytest.raises(RuntimeError, match="did not become available"):
                _wait_for_xmlrpc(host="127.0.0.1", port=8069, timeout=1, interval=1)

    def test_retries_before_succeeding(self):
        mock_client = MagicMock()
        with patch(
            "sandboxerp.engine.installer.OdooClient.connect_and_authenticate",
            side_effect=[OdooError("not ready"), mock_client],
        ) as mock_connect:
            with patch("time.sleep"):
                result = _wait_for_xmlrpc(host="127.0.0.1", port=8069, timeout=10, interval=1)
        assert result is mock_client
        assert mock_connect.call_count == 2


# ─────────────────────────────────────────
# _install_modules
# ─────────────────────────────────────────

class TestInstallModules:
    def test_installs_all_modules(self, mock_client):
        _install_modules(mock_client, _COUNTRY_PACK, _INDUSTRY_PACK)
        assert mock_client.install_module.call_count >= 1

    def test_skips_already_installed(self, mock_client):
        mock_client.module_is_installed.return_value = True
        _install_modules(mock_client, _COUNTRY_PACK, _INDUSTRY_PACK)
        mock_client.install_module.assert_not_called()

    def test_country_modules_before_industry(self, mock_client):
        installed = []
        mock_client.module_is_installed.return_value = False
        mock_client.install_module.side_effect = lambda m: installed.append(m)
        _install_modules(mock_client, _COUNTRY_PACK, _INDUSTRY_PACK)
        country_mods = _COUNTRY_PACK["localization"]["odoo_modules"]["install_order"]
        for cm in country_mods:
            if cm in installed:
                ci = installed.index(cm)
                for im in ["sale_management", "stock"]:
                    if im in installed:
                        assert ci < installed.index(im)

    def test_no_duplicate_modules(self, mock_client):
        """A module in both packs should only be installed once."""
        dup_industry = {
            "meta": {
                "code": "retail",
                "name": "Retail",
                "odoo_modules": {"install_order": ["l10n_cl", "sale_management"]},
            }
        }
        installed = []
        mock_client.module_is_installed.return_value = False
        mock_client.install_module.side_effect = lambda m: installed.append(m)
        _install_modules(mock_client, _COUNTRY_PACK, dup_industry)
        assert installed.count("l10n_cl") == 1


# ─────────────────────────────────────────
# _configure_company
# ─────────────────────────────────────────

class TestConfigureCompany:
    def test_writes_country_and_currency(self, mock_client):
        mock_client.search.return_value = [5]
        _configure_company(mock_client, _COUNTRY_PACK)
        assert mock_client.write.call_count == 2
        first_call_values = mock_client.write.mock_calls[0].args[2]
        second_call_values = mock_client.write.mock_calls[1].args[2]
        assert "country_id" in first_call_values
        assert "currency_id" in second_call_values

    def test_skips_write_if_no_ids_found(self, mock_client):
        mock_client.search.return_value = []
        _configure_company(mock_client, _COUNTRY_PACK)
        mock_client.write.assert_not_called()


# ─────────────────────────────────────────
# _generate_partners
# ─────────────────────────────────────────

class TestGeneratePartners:
    def test_creates_expected_count(self, mock_client):
        from faker import Faker
        fake = Faker("es_CL")
        fake.seed_instance(42)
        mock_client.search.return_value = [1]
        mock_client.create.return_value = 99

        ids = _generate_partners(
            mock_client, _COUNTRY_PACK, _INDUSTRY_PACK, "small", fake
        )
        assert len(ids) == 8  # small: 5 customers + 3 suppliers

    def test_returns_list_of_ints(self, mock_client):
        from faker import Faker
        fake = Faker("es_CL")
        fake.seed_instance(0)
        mock_client.search.return_value = []
        mock_client.create.return_value = 10

        ids = _generate_partners(
            mock_client, _COUNTRY_PACK, _INDUSTRY_PACK, "small", fake
        )
        assert all(isinstance(i, int) for i in ids)


# ─────────────────────────────────────────
# _generate_products
# ─────────────────────────────────────────

class TestGenerateProducts:
    def test_creates_expected_count(self, mock_client):
        from faker import Faker
        fake = Faker("es_CL")
        fake.seed_instance(42)
        mock_client.create.return_value = 55

        ids = _generate_products(mock_client, _INDUSTRY_PACK, "small", fake)
        assert len(ids) == 5  # small: 5 products

    def test_returns_list_of_ints(self, mock_client):
        from faker import Faker
        fake = Faker("es_CL")
        fake.seed_instance(0)
        mock_client.create.return_value = 7

        ids = _generate_products(mock_client, _INDUSTRY_PACK, "small", fake)
        assert all(isinstance(i, int) for i in ids)


# ─────────────────────────────────────────
# _generate_transactions
# ─────────────────────────────────────────

class TestGenerateTransactions:
    def test_creates_sale_orders(self, mock_client):
        mock_client.search.return_value = [1]
        mock_client.create.return_value = 200

        _generate_transactions(
            mock_client,
            country_pack=_COUNTRY_PACK,
            industry_pack=_INDUSTRY_PACK,
            profile="small",
            seed=42,
            partner_ids=[1, 2, 3],
            product_ids=[10, 11, 12],
            window=_WINDOW,
        )
        assert mock_client.create.call_count >= 1

    def test_skips_gracefully_with_no_partners(self, mock_client):
        """No partners → no orders created, no crash."""
        mock_client.search.return_value = []
        _generate_transactions(
            mock_client,
            country_pack=_COUNTRY_PACK,
            industry_pack=_INDUSTRY_PACK,
            profile="small",
            seed=42,
            partner_ids=[],
            product_ids=[10],
            window=_WINDOW,
        )
        mock_client.create.assert_not_called()

    def test_skips_gracefully_with_no_products(self, mock_client):
        """No products → no orders created, no crash."""
        mock_client.search.return_value = []
        _generate_transactions(
            mock_client,
            country_pack=_COUNTRY_PACK,
            industry_pack=_INDUSTRY_PACK,
            profile="small",
            seed=42,
            partner_ids=[1],
            product_ids=[],
            window=_WINDOW,
        )
        mock_client.create.assert_not_called()


# ─────────────────────────────────────────
# install (full pipeline)
# ─────────────────────────────────────────

class TestInstall:
    def test_full_pipeline_runs(self):
        mock_client = MagicMock()
        mock_client.uid = 1
        mock_client.module_is_installed.return_value = True
        mock_client.search.return_value = [1]
        mock_client.create.return_value = 42

        with patch(
            "sandboxerp.engine.installer.load_country_pack",
            return_value=_COUNTRY_PACK,
        ), patch(
            "sandboxerp.engine.installer.load_industry_pack",
            return_value=_INDUSTRY_PACK,
        ), patch(
            "sandboxerp.engine.installer._wait_for_xmlrpc",
            return_value=mock_client,
        ):
            install(
                country="cl",
                industry="retail",
                profile="small",
                seed=42,
            )

    def test_raises_if_pack_missing(self):
        with patch(
            "sandboxerp.engine.installer.load_country_pack",
            side_effect=FileNotFoundError("pack not found"),
        ):
            with pytest.raises(FileNotFoundError):
                install(
                    country="zz",
                    industry="retail",
                    profile="small",
                    seed=42,
                )


# ─────────────────────────────────────────
# _configure_language
# ─────────────────────────────────────────


class TestConfigureLanguage:
    def test_loads_and_assigns_locale(self, mock_client):
        """Happy path: locale found, assigned to admin user."""
        mock_client.search.return_value = [1]
        _configure_language(mock_client, _COUNTRY_PACK)
        mock_client.execute.assert_called_once_with(
            "res.lang", "load_lang", "es_CL"
        )
        mock_client.write.assert_called_once_with(
            "res.users", [2], {"lang": "es_CL"}
        )

    def test_falls_back_to_es_ES_when_locale_not_found(self, mock_client):
        """If es_CL is not available, falls back to es_ES."""
        def search_side_effect(model, domain, **kwargs):
            code = domain[0][2]
            return [1] if code == "es_ES" else []

        mock_client.search.side_effect = search_side_effect
        _configure_language(mock_client, _COUNTRY_PACK)
        mock_client.write.assert_called_once_with(
            "res.users", [2], {"lang": "es_ES"}
        )

    def test_no_write_when_no_locale_found(self, mock_client):
        """If neither locale is available, write is not called."""
        mock_client.search.return_value = []
        _configure_language(mock_client, _COUNTRY_PACK)
        mock_client.write.assert_not_called()

    def test_load_lang_error_is_silenced(self, mock_client):
        """If load_lang raises, the function continues without crashing."""
        mock_client.execute.side_effect = Exception("already loaded")
        mock_client.search.return_value = [1]
        _configure_language(mock_client, _COUNTRY_PACK)
        mock_client.write.assert_called_once()
