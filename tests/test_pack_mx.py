"""
tests.test_pack_mx
~~~~~~~~~~~~~~~~~~

Unit tests for the Mexico country pack (country_mx.yaml).

Covers:
- Structural integrity: all required sections present.
- Meta, localization, fiscal, taxpayer_types, document_types.
- Banks, geography, addresses, company.
- Faker es_MX integration smoke test.

:author: Hector Colina / Team360 <https://team360.cl>
"""

import pytest

from sandboxerp.packs.loader import load_country_pack


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def mx_pack():
    """Load country_mx.yaml once for all structural tests."""
    return load_country_pack("mx")


# ---------------------------------------------------------------------------
# Structural integrity
# ---------------------------------------------------------------------------

class TestCountryMXStructure:
    REQUIRED_SECTIONS = [
        "meta", "localization", "fiscal", "taxpayer_types",
        "document_types", "banks", "addresses", "geography", "company",
    ]

    def test_required_sections_present(self, mx_pack):
        """All required top-level sections must be present."""
        for section in self.REQUIRED_SECTIONS:
            assert section in mx_pack, f"Missing section: {section}"


# ---------------------------------------------------------------------------
# meta
# ---------------------------------------------------------------------------

class TestCountryMXMeta:
    def test_meta_code(self, mx_pack):
        assert mx_pack["meta"]["code"] == "mx"

    def test_meta_locale(self, mx_pack):
        assert mx_pack["meta"]["locale"] == "es_MX"

    def test_meta_layers(self, mx_pack):
        assert 1 in mx_pack["meta"]["layers"]
        assert 2 in mx_pack["meta"]["layers"]


# ---------------------------------------------------------------------------
# localization
# ---------------------------------------------------------------------------

class TestCountryMXLocalization:
    def test_has_odoo_modules(self, mx_pack):
        modules = mx_pack["localization"]["odoo_modules"]["install_order"]
        assert "l10n_mx" in modules
        assert "l10n_mx_edi" in modules

    def test_l10n_mx_before_l10n_mx_edi(self, mx_pack):
        """l10n_mx must be installed before l10n_mx_edi."""
        modules = mx_pack["localization"]["odoo_modules"]["install_order"]
        assert modules.index("l10n_mx") < modules.index("l10n_mx_edi")

    def test_currency_is_mxn(self, mx_pack):
        assert mx_pack["localization"]["currency"] == "MXN"

    def test_language_is_es_mx(self, mx_pack):
        assert mx_pack["localization"]["language"] == "es_MX"

    def test_country_code_is_mx(self, mx_pack):
        assert mx_pack["localization"]["country_code"] == "MX"

    def test_post_install_has_set_currency(self, mx_pack):
        actions = mx_pack["localization"]["post_install"]
        assert {"set_currency": "MXN"} in actions

    def test_post_install_has_set_country(self, mx_pack):
        actions = mx_pack["localization"]["post_install"]
        assert {"set_country": "MX"} in actions


# ---------------------------------------------------------------------------
# fiscal
# ---------------------------------------------------------------------------

class TestCountryMXFiscal:
    def test_tax_name_is_iva(self, mx_pack):
        assert mx_pack["fiscal"]["tax_name"] == "IVA"

    def test_tax_rate_is_16_percent(self, mx_pack):
        assert mx_pack["fiscal"]["tax_rate"] == 0.16

    def test_id_label_is_rfc(self, mx_pack):
        assert mx_pack["fiscal"]["id_label"] == "RFC"

    def test_faker_person_id_is_rfc(self, mx_pack):
        assert mx_pack["fiscal"]["faker_person_id"] == "rfc"

    def test_faker_company_id_is_rfc(self, mx_pack):
        assert mx_pack["fiscal"]["faker_company_id"] == "rfc"


# ---------------------------------------------------------------------------
# taxpayer_types
# ---------------------------------------------------------------------------

class TestCountryMXTaxpayerTypes:
    def test_taxpayer_types_count(self, mx_pack):
        """Mexico pack must define at least 4 regímenes fiscales SAT."""
        assert len(mx_pack["taxpayer_types"]) >= 4

    def test_taxpayer_types_have_required_fields(self, mx_pack):
        for t in mx_pack["taxpayer_types"]:
            assert "code" in t
            assert "label" in t
            assert "odoo_field" in t

    def test_taxpayer_types_have_exactly_one_default(self, mx_pack):
        defaults = [t for t in mx_pack["taxpayer_types"] if t.get("default")]
        assert len(defaults) == 1

    def test_regimen_601_present(self, mx_pack):
        """Régimen General de Ley (601) must be present — most common for companies."""
        codes = {t["code"] for t in mx_pack["taxpayer_types"]}
        assert "601" in codes

    def test_default_is_601(self, mx_pack):
        default = next(t for t in mx_pack["taxpayer_types"] if t.get("default"))
        assert default["code"] == "601"


# ---------------------------------------------------------------------------
# document_types
# ---------------------------------------------------------------------------

class TestCountryMXDocumentTypes:
    def test_document_types_have_required_fields(self, mx_pack):
        for doc in mx_pack["document_types"]:
            assert "code" in doc
            assert "name" in doc
            assert "affects_vat" in doc

    def test_cfdi_ingreso_present(self, mx_pack):
        """CFDI tipo Ingreso (I) must be present — default sale document."""
        codes = {d["code"] for d in mx_pack["document_types"]}
        assert "I" in codes

    def test_cfdi_egreso_present(self, mx_pack):
        """CFDI tipo Egreso (E) must be present — credit note."""
        codes = {d["code"] for d in mx_pack["document_types"]}
        assert "E" in codes

    def test_cfdi_pago_present(self, mx_pack):
        """CFDI tipo Pago (P) must be present — payment complement."""
        codes = {d["code"] for d in mx_pack["document_types"]}
        assert "P" in codes

    def test_default_sale_is_ingreso(self, mx_pack):
        sale_defaults = [d for d in mx_pack["document_types"] if d.get("default_sale")]
        assert len(sale_defaults) == 1
        assert sale_defaults[0]["code"] == "I"


# ---------------------------------------------------------------------------
# banks
# ---------------------------------------------------------------------------

class TestCountryMXBanks:
    def test_banks_have_required_fields(self, mx_pack):
        for bank in mx_pack["banks"]:
            assert "code" in bank
            assert "name" in bank
            assert "swift" in bank

    def test_banamex_present(self, mx_pack):
        """Citibanamex (110) must be present."""
        codes = {b["code"] for b in mx_pack["banks"]}
        assert "110" in codes

    def test_banorte_present(self, mx_pack):
        """Banorte (072) must be present."""
        codes = {b["code"] for b in mx_pack["banks"]}
        assert "072" in codes

    def test_santander_present(self, mx_pack):
        """Santander (126) must be present."""
        codes = {b["code"] for b in mx_pack["banks"]}
        assert "126" in codes

    def test_minimum_bank_count(self, mx_pack):
        """Pack must define at least 10 banks."""
        assert len(mx_pack["banks"]) >= 10


# ---------------------------------------------------------------------------
# geography
# ---------------------------------------------------------------------------

class TestCountryMXGeography:
    def test_has_32_states(self, mx_pack):
        """Mexico has 31 states + CDMX = 32 entities."""
        assert len(mx_pack["geography"]["regions"]) == 32

    def test_cdmx_is_default(self, mx_pack):
        cdmx = next(
            r for r in mx_pack["geography"]["regions"] if r["code"] == "CDMX"
        )
        assert cdmx.get("default") is True

    def test_regions_have_required_fields(self, mx_pack):
        for region in mx_pack["geography"]["regions"]:
            assert "code" in region
            assert "name" in region
            assert "capital" in region

    def test_jalisco_present(self, mx_pack):
        codes = {r["code"] for r in mx_pack["geography"]["regions"]}
        assert "JAL" in codes

    def test_nuevo_leon_present(self, mx_pack):
        codes = {r["code"] for r in mx_pack["geography"]["regions"]}
        assert "NL" in codes


# ---------------------------------------------------------------------------
# addresses
# ---------------------------------------------------------------------------

class TestCountryMXAddresses:
    def test_has_municipalities(self, mx_pack):
        municipalities = mx_pack["addresses"]["municipalities_by_state"]
        assert "CDMX" in municipalities
        assert len(municipalities["CDMX"]) > 0

    def test_has_street_suffixes(self, mx_pack):
        suffixes = mx_pack["addresses"]["street_suffixes"]
        assert len(suffixes) > 0

    def test_jalisco_municipalities_present(self, mx_pack):
        municipalities = mx_pack["addresses"]["municipalities_by_state"]
        assert "JAL" in municipalities
        assert "Guadalajara" in municipalities["JAL"]


# ---------------------------------------------------------------------------
# company
# ---------------------------------------------------------------------------

class TestCountryMXCompany:
    def test_has_name_suffixes(self, mx_pack):
        suffixes = mx_pack["company"]["name_suffixes"]
        assert "S.A. de C.V." in suffixes
        assert "S. de R.L. de C.V." in suffixes

    def test_has_economic_activities(self, mx_pack):
        activities = mx_pack["company"]["economic_activities"]
        assert len(activities) > 0

    def test_economic_activities_have_required_fields(self, mx_pack):
        for act in mx_pack["company"]["economic_activities"]:
            assert "code" in act
            assert "description" in act


# ---------------------------------------------------------------------------
# Faker integration smoke test
# ---------------------------------------------------------------------------

class TestFakerMXIntegration:
    def test_faker_es_mx_person_rfc(self):
        """Faker es_MX must generate valid person RFCs (13 chars)."""
        from faker import Faker
        fake = Faker("es_MX")
        fake.seed_instance(42)
        rfc = fake.rfc(natural=True)
        assert isinstance(rfc, str)
        assert len(rfc) == 13

    def test_faker_es_mx_company_rfc(self):
        """Faker es_MX must generate valid company RFCs (12 chars)."""
        from faker import Faker
        fake = Faker("es_MX")
        fake.seed_instance(42)
        rfc = fake.rfc(natural=False)
        assert isinstance(rfc, str)
        assert len(rfc) == 12

    def test_faker_rfc_methods_match_pack_config(self, mx_pack):
        """Faker method declared in pack config must be callable."""
        from faker import Faker
        fake = Faker("es_MX")
        fiscal = mx_pack["fiscal"]
        assert hasattr(fake, fiscal["faker_person_id"])
        assert hasattr(fake, fiscal["faker_company_id"])
