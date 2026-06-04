"""
tests.test_pack_cl
~~~~~~~~~~~~~~~~~~

Structural integrity tests for the Chile country pack (country_cl.yaml).

Covers:
- meta: required fields, code, locale, layers.
- localization: odoo modules, install order, currency, language.
- fiscal: tax rate, id label, faker methods.
- taxpayer_types: count, required fields, single default.
- document_types: SII DTE codes, required fields, default sale document.
- banks: required fields, BancoEstado presence.
- geography: 16 regions, RM as default.
- addresses: communes by region.
- company: name suffixes, economic activities.
- Faker es_CL integration smoke test.

:author: Hector Colina / Team360 <https://team360.cl>
"""

import pytest

from sandboxerp.packs.loader import load_country_pack


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def cl_pack():
    """Load country_cl.yaml once for all structural tests."""
    return load_country_pack("cl")


# ---------------------------------------------------------------------------
# Structural integrity
# ---------------------------------------------------------------------------

class TestCountryCLStructure:
    REQUIRED_SECTIONS = [
        "meta", "localization", "fiscal", "taxpayer_types",
        "document_types", "banks", "addresses", "geography", "company",
    ]

    def test_required_sections_present(self, cl_pack):
        """All required top-level sections must be present."""
        for section in self.REQUIRED_SECTIONS:
            assert section in cl_pack, f"Missing section: {section}"


# ---------------------------------------------------------------------------
# meta
# ---------------------------------------------------------------------------

class TestCountryCLMeta:
    def test_meta_code(self, cl_pack):
        assert cl_pack["meta"]["code"] == "cl"

    def test_meta_locale(self, cl_pack):
        assert cl_pack["meta"]["locale"] == "es_CL"

    def test_meta_layers(self, cl_pack):
        assert 1 in cl_pack["meta"]["layers"]
        assert 2 in cl_pack["meta"]["layers"]


# ---------------------------------------------------------------------------
# localization
# ---------------------------------------------------------------------------

class TestCountryCLLocalization:
    def test_has_odoo_modules(self, cl_pack):
        modules = cl_pack["localization"]["odoo_modules"]["install_order"]
        assert "l10n_cl" in modules
        assert "l10n_cl_edi" in modules

    def test_l10n_cl_before_l10n_cl_edi(self, cl_pack):
        """l10n_cl must be installed before l10n_cl_edi."""
        modules = cl_pack["localization"]["odoo_modules"]["install_order"]
        assert modules.index("l10n_cl") < modules.index("l10n_cl_edi")

    def test_currency_is_clp(self, cl_pack):
        assert cl_pack["localization"]["currency"] == "CLP"

    def test_language_is_es_cl(self, cl_pack):
        assert cl_pack["localization"]["language"] == "es_CL"

    def test_country_code_is_cl(self, cl_pack):
        assert cl_pack["localization"]["country_code"] == "CL"

    def test_post_install_has_set_currency(self, cl_pack):
        actions = cl_pack["localization"]["post_install"]
        assert {"set_currency": "CLP"} in actions

    def test_post_install_has_set_country(self, cl_pack):
        actions = cl_pack["localization"]["post_install"]
        assert {"set_country": "CL"} in actions


# ---------------------------------------------------------------------------
# fiscal
# ---------------------------------------------------------------------------

class TestCountryCLFiscal:
    def test_tax_name_is_iva(self, cl_pack):
        assert cl_pack["fiscal"]["tax_name"] == "IVA"

    def test_tax_rate_is_19_percent(self, cl_pack):
        assert cl_pack["fiscal"]["tax_rate"] == 0.19

    def test_id_label_is_rut(self, cl_pack):
        assert cl_pack["fiscal"]["id_label"] == "RUT"

    def test_faker_person_id(self, cl_pack):
        assert cl_pack["fiscal"]["faker_person_id"] == "person_rut"

    def test_faker_company_id(self, cl_pack):
        assert cl_pack["fiscal"]["faker_company_id"] == "company_rut"


# ---------------------------------------------------------------------------
# taxpayer_types
# ---------------------------------------------------------------------------

class TestCountryCLTaxpayerTypes:
    def test_taxpayer_types_count(self, cl_pack):
        """Chile has exactly 4 SII taxpayer types."""
        assert len(cl_pack["taxpayer_types"]) == 4

    def test_taxpayer_types_have_required_fields(self, cl_pack):
        for t in cl_pack["taxpayer_types"]:
            assert "code" in t
            assert "label" in t
            assert "odoo_field" in t

    def test_taxpayer_types_have_exactly_one_default(self, cl_pack):
        defaults = [t for t in cl_pack["taxpayer_types"] if t.get("default")]
        assert len(defaults) == 1

    def test_default_is_primera_categoria(self, cl_pack):
        default = next(t for t in cl_pack["taxpayer_types"] if t.get("default"))
        assert default["code"] == "1"


# ---------------------------------------------------------------------------
# document_types
# ---------------------------------------------------------------------------

class TestCountryCLDocumentTypes:
    def test_document_types_have_required_fields(self, cl_pack):
        for doc in cl_pack["document_types"]:
            assert "code" in doc
            assert "name" in doc
            assert "affects_vat" in doc

    def test_core_dte_codes_present(self, cl_pack):
        """Core DTE codes must be present."""
        codes = {d["code"] for d in cl_pack["document_types"]}
        for expected in (33, 39, 61, 56, 52):
            assert expected in codes, f"Missing DTE code: {expected}"

    def test_default_sale_is_33(self, cl_pack):
        sale_defaults = [d for d in cl_pack["document_types"] if d.get("default_sale")]
        assert len(sale_defaults) == 1
        assert sale_defaults[0]["code"] == 33


# ---------------------------------------------------------------------------
# banks
# ---------------------------------------------------------------------------

class TestCountryCLBanks:
    def test_banks_have_required_fields(self, cl_pack):
        for bank in cl_pack["banks"]:
            assert "code" in bank
            assert "name" in bank
            assert "swift" in bank

    def test_bancoestado_present(self, cl_pack):
        """BancoEstado (012) must be present."""
        codes = {b["code"] for b in cl_pack["banks"]}
        assert "012" in codes

    def test_minimum_bank_count(self, cl_pack):
        """Pack must define at least 5 banks."""
        assert len(cl_pack["banks"]) >= 5


# ---------------------------------------------------------------------------
# geography
# ---------------------------------------------------------------------------

class TestCountryCLGeography:
    def test_has_16_regions(self, cl_pack):
        assert len(cl_pack["geography"]["regions"]) == 16

    def test_rm_is_default(self, cl_pack):
        rm = next(
            r for r in cl_pack["geography"]["regions"] if r["code"] == "RM"
        )
        assert rm.get("default") is True

    def test_regions_have_required_fields(self, cl_pack):
        for region in cl_pack["geography"]["regions"]:
            assert "code" in region
            assert "name" in region
            assert "capital" in region


# ---------------------------------------------------------------------------
# addresses
# ---------------------------------------------------------------------------

class TestCountryCLAddresses:
    def test_has_communes_by_region(self, cl_pack):
        communes = cl_pack["addresses"]["communes_by_region"]
        assert "RM" in communes
        assert len(communes["RM"]) > 0

    def test_has_street_suffixes(self, cl_pack):
        suffixes = cl_pack["addresses"]["street_suffixes"]
        assert len(suffixes) > 0


# ---------------------------------------------------------------------------
# company
# ---------------------------------------------------------------------------

class TestCountryCLCompany:
    def test_has_name_suffixes(self, cl_pack):
        suffixes = cl_pack["company"]["name_suffixes"]
        assert "S.A." in suffixes
        assert "SpA" in suffixes
        assert "Ltda." in suffixes

    def test_has_economic_activities(self, cl_pack):
        activities = cl_pack["company"]["economic_activities"]
        assert len(activities) > 0

    def test_economic_activities_have_required_fields(self, cl_pack):
        for act in cl_pack["company"]["economic_activities"]:
            assert "code" in act
            assert "description" in act


# ---------------------------------------------------------------------------
# Faker integration smoke test
# ---------------------------------------------------------------------------

class TestFakerCLIntegration:
    def test_faker_es_cl_person_rut(self):
        """Faker es_CL must generate valid person RUTs."""
        from faker import Faker
        fake = Faker("es_CL")
        fake.seed_instance(42)
        rut = fake.person_rut()
        assert "-" in rut

    def test_faker_es_cl_company_rut(self):
        """Faker es_CL must generate valid company RUTs."""
        from faker import Faker
        fake = Faker("es_CL")
        fake.seed_instance(42)
        rut = fake.company_rut()
        assert "-" in rut

    def test_faker_rut_methods_match_pack_config(self, cl_pack):
        """Faker methods declared in pack config must be callable."""
        from faker import Faker
        fake = Faker("es_CL")
        fiscal = cl_pack["fiscal"]
        assert hasattr(fake, fiscal["faker_person_id"])
        assert hasattr(fake, fiscal["faker_company_id"])
