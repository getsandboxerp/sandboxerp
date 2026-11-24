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
    _configure_admin_user,
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

    def test_always_writes_name_and_logo(self, mock_client):
        mock_client.search.return_value = []
        _configure_company(mock_client, _COUNTRY_PACK)
        mock_client.write.assert_called_once()
        call_args = mock_client.write.call_args[0]
        assert call_args[0] == "res.company"
        assert "name" in call_args[2]
        assert "logo" in call_args[2]
        assert "website" in call_args[2]


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

        ids, _, _ = _generate_partners(
            mock_client, _COUNTRY_PACK, _INDUSTRY_PACK, "small", fake
        )
        assert len(ids) == 8  # small: 5 customers + 3 suppliers

    def test_returns_list_of_ints(self, mock_client):
        from faker import Faker
        fake = Faker("es_CL")
        fake.seed_instance(0)
        mock_client.search.return_value = []
        mock_client.create.return_value = 10

        ids, _, _ = _generate_partners(
            mock_client, _COUNTRY_PACK, _INDUSTRY_PACK, "small", fake
        )
        assert all(isinstance(i, int) for i in ids)

    def test_vat_is_unique_when_generator_collides(self, mock_client):
        """A generator that repeats values must not yield duplicate VATs."""
        from faker import Faker
        fake = Faker("es_CL")
        fake.seed_instance(42)
        mock_client.search.return_value = [1]
        mock_client.create.return_value = 99
        values = iter(
            [v for n in range(1, 40) for v in (f"V{n}", f"V{n}")]
        )

        with patch(
            "sandboxerp.engine.installer.generate_vat",
            side_effect=lambda *a, **k: next(values),
        ):
            _generate_partners(
                mock_client, _COUNTRY_PACK, _INDUSTRY_PACK, "small", fake
            )

        vats = [
            c.args[1]["vat"]
            for c in mock_client.create.call_args_list
            if c.args[0] == "res.partner"
        ]
        assert len(vats) == 8
        assert len(set(vats)) == 8

    def test_vat_retries_are_bounded(self, mock_client):
        """A generator stuck on one value must not hang the installer."""
        from faker import Faker
        fake = Faker("es_CL")
        fake.seed_instance(42)
        mock_client.search.return_value = [1]
        mock_client.create.return_value = 99

        with patch(
            "sandboxerp.engine.installer.generate_vat", return_value="SAME"
        ) as gen:
            ids, _, _ = _generate_partners(
                mock_client, _COUNTRY_PACK, _INDUSTRY_PACK, "small", fake
            )

        assert len(ids) == 8
        assert gen.call_count <= 8 * 101

    def test_unique_vat_draws_once_without_collision(self):
        """With no collision the generator is called exactly once."""
        from sandboxerp.engine.installer import _unique_vat
        calls = []

        def make():
            calls.append(1)
            return "A"

        used: set[str] = set()
        assert _unique_vat(make, used) == "A"
        assert len(calls) == 1
        assert used == {"A"}


# ─────────────────────────────────────────
# _generate_products
# ─────────────────────────────────────────

class TestGenerateProducts:
    def test_creates_expected_count(self, mock_client):
        from faker import Faker
        fake = Faker("es_CL")
        fake.seed_instance(42)
        mock_client.create.return_value = 55

        ids, _ = _generate_products(mock_client, _INDUSTRY_PACK, "small", fake)
        assert len(ids) == 5  # small: 5 products

    def test_returns_list_of_ints(self, mock_client):
        from faker import Faker
        fake = Faker("es_CL")
        fake.seed_instance(0)
        mock_client.create.return_value = 7

        ids, _ = _generate_products(mock_client, _INDUSTRY_PACK, "small", fake)
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
            result = install(
                country="cl",
                industry="retail",
                profile="small",
                seed=42,
            )
            assert isinstance(result, dict)
            assert "client" in result
            assert "customers" in result
            assert "suppliers" in result
            assert "products" in result
            assert "so_created" in result
            assert "so_confirmed" in result
            assert "so_invoiced" in result
            assert "so_paid" in result

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
    def test_assigns_locale_when_already_active(self, mock_client):
        """If locale is already active, wizard is skipped and lang assigned."""
        # First search (active_test=False) finds it, second search (active) also finds it
        mock_client.search.return_value = [70]
        mock_client.create.return_value = 1
        _configure_language(mock_client, _COUNTRY_PACK)
        # wizard not invoked — lang already active
        mock_client.execute.assert_not_called()
        mock_client.write.assert_called_once_with(
            "res.users", [2], {"lang": "es_CL"}
        )

    def test_installs_via_wizard_when_inactive(self, mock_client):
        """If locale exists but inactive, wizard is created and executed."""
        call_count = 0

        def search_side_effect(model, domain, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [70]   # found with active_test=False
            return []          # inactive (not found without active_test)

        mock_client.search.side_effect = search_side_effect
        mock_client.create.return_value = 1
        _configure_language(mock_client, _COUNTRY_PACK)
        mock_client.create.assert_called_once()
        mock_client.execute.assert_called_once_with(
            "base.language.install", "lang_install", [1]
        )
        mock_client.write.assert_called_once_with(
            "res.users", [2], {"lang": "es_CL"}
        )

    def test_falls_back_to_es_ES_when_locale_not_found(self, mock_client):
        """If es_CL is not available, falls back to es_ES."""
        call_count = 0

        def search_side_effect(model, domain, **kwargs):
            nonlocal call_count
            call_count += 1
            code = domain[0][2]
            if code == "es_CL":
                return []
            if code == "es_ES":
                return [82]
            return [82]  # active check for es_ES

        mock_client.search.side_effect = search_side_effect
        mock_client.create.return_value = 1
        _configure_language(mock_client, _COUNTRY_PACK)
        mock_client.write.assert_called_once_with(
            "res.users", [2], {"lang": "es_ES"}
        )

    def test_no_write_when_no_locale_found(self, mock_client):
        """If neither locale is available, write is not called."""
        mock_client.search.return_value = []
        _configure_language(mock_client, _COUNTRY_PACK)
        mock_client.write.assert_not_called()

    def test_wizard_error_is_silenced(self, mock_client):
        """If wizard raises, the function continues and still assigns lang."""
        call_count = 0

        def search_side_effect(model, domain, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [70]
            return []

        mock_client.search.side_effect = search_side_effect
        mock_client.create.side_effect = Exception("wizard failed")
        _configure_language(mock_client, _COUNTRY_PACK)
        mock_client.write.assert_called_once_with(
            "res.users", [2], {"lang": "es_CL"}
        )

    def test_prefers_localization_language_over_meta_locale(self, mock_client):
        """localization.language wins over meta.locale (Faker locale)."""
        pack = {
            "meta": {"code": "do", "locale": "es_MX"},
            "localization": {"language": "es_DO"},
        }
        mock_client.search.return_value = [70]
        _configure_language(mock_client, pack)
        first_domain = mock_client.search.call_args_list[0].args[1]
        assert first_domain == [["code", "=", "es_DO"]]
        mock_client.write.assert_called_once_with(
            "res.users", [2], {"lang": "es_DO"}
        )

    def test_falls_back_to_meta_locale_when_language_missing(self, mock_client):
        """If localization.language is not in res.lang, meta.locale is used."""

        def search_side_effect(model, domain, **kwargs):
            code = domain[0][2]
            return [] if code == "es_DO" else [70]

        mock_client.search.side_effect = search_side_effect
        pack = {
            "meta": {"code": "do", "locale": "es_MX"},
            "localization": {"language": "es_DO"},
        }
        _configure_language(mock_client, pack)
        mock_client.write.assert_called_once_with(
            "res.users", [2], {"lang": "es_MX"}
        )

    def test_falls_back_to_es_ES_when_language_and_locale_missing(self, mock_client):
        """If neither language nor locale exist, es_ES is the last resort."""

        def search_side_effect(model, domain, **kwargs):
            code = domain[0][2]
            return [82] if code == "es_ES" else []

        mock_client.search.side_effect = search_side_effect
        pack = {
            "meta": {"code": "do", "locale": "es_MX"},
            "localization": {"language": "es_DO"},
        }
        _configure_language(mock_client, pack)
        mock_client.write.assert_called_once_with(
            "res.users", [2], {"lang": "es_ES"}
        )



# ─────────────────────────────────────────
# _configure_admin_user
# ─────────────────────────────────────────


class TestConfigureAdminUser:
    def test_assigns_all_three_groups(self, mock_client):
        """All three admin groups are assigned when found."""
        mock_client.search_read.return_value = [
            {"id": 10, "full_name": "Inventory/Administrator"},
            {"id": 11, "full_name": "Sales/Administrator"},
            {"id": 12, "full_name": "Purchase/Administrator"},
        ]
        _configure_admin_user(mock_client)
        assert mock_client.execute.call_count == 3
        for call_args in mock_client.execute.call_args_list:
            args = call_args.args
            assert args[0] == "res.groups"
            assert args[1] == "write"
            assert args[3] == {"users": [[4, 2]]}

    def test_handles_empty_groups(self, mock_client):
        """No execute calls when no groups are found."""
        mock_client.search_read.return_value = []
        _configure_admin_user(mock_client)
        mock_client.execute.assert_not_called()

    def test_silences_group_write_error(self, mock_client):
        """A failure on one group does not abort the rest."""
        mock_client.search_read.return_value = [
            {"id": 10, "full_name": "Inventory/Administrator"},
            {"id": 11, "full_name": "Sales/Administrator"},
        ]
        mock_client.execute.side_effect = [Exception("write failed"), None]
        _configure_admin_user(mock_client)
        assert mock_client.execute.call_count == 2

    def test_searches_correct_group_names(self, mock_client):
        """search_read targets the three expected full_name values."""
        mock_client.search_read.return_value = []
        _configure_admin_user(mock_client)
        domain = mock_client.search_read.call_args.args[1]
        names = domain[0][2]
        assert "Inventory/Administrator" in names
        assert "Sales/Administrator" in names
        assert "Purchase/Administrator" in names
