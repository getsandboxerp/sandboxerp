"""
tests.test_pack_nl
~~~~~~~~~~~~~~~~~~

Structural integrity tests for the Netherlands country pack (country_nl.yaml).

Covers:
- meta: required fields, code, locale, layers.
- localization: odoo modules, install order, currency, language.
- fiscal: BTW tax rate, id label, faker methods.
- partner_fields: vat_prefix, empty l10n_latam fields (no LATAM dependency).
- banks: required fields, ING / ABN AMRO / Rabobank presence.
- geography: 12 provinces, Noord-Holland as default.
- addresses: cities by province.
- company: name suffixes (B.V. required), economic activities (SBI codes).
- Faker nl_NL integration smoke test.

:author: Hector Colina / Team360 <https://team360.cl>
"""

import pytest

from sandboxerp.packs.loader import load_country_pack


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def nl_pack():
    """Load country_nl.yaml once for all structural tests."""
    return load_country_pack("nl")


# ---------------------------------------------------------------------------
# Structural integrity
# ---------------------------------------------------------------------------

class TestCountryNLStructure:
    REQUIRED_SECTIONS = [
        "meta", "localization", "fiscal", "partner_fields",
        "banks", "addresses", "geography", "company",
    ]

    def test_required_sections_present(self, nl_pack):
        """All required top-level sections must be present."""
        for section in self.REQUIRED_SECTIONS:
            assert section in nl_pack, f"Missing section: {section}"


# ---------------------------------------------------------------------------
# meta
# ---------------------------------------------------------------------------

class TestCountryNLMeta:
    def test_meta_code(self, nl_pack):
        assert nl_pack["meta"]["code"] == "nl"

    def test_meta_name(self, nl_pack):
        assert nl_pack["meta"]["name"] == "Netherlands"

    def test_meta_locale(self, nl_pack):
        assert nl_pack["meta"]["locale"] == "nl_NL"

    def test_meta_layers(self, nl_pack):
        assert 1 in nl_pack["meta"]["layers"]
        assert 2 in nl_pack["meta"]["layers"]


# ---------------------------------------------------------------------------
# localization
# ---------------------------------------------------------------------------

class TestCountryNLLocalization:
    def test_has_l10n_nl_module(self, nl_pack):
        modules = nl_pack["localization"]["odoo_modules"]["install_order"]
        assert "l10n_nl" in modules

    def test_currency_is_eur(self, nl_pack):
        assert nl_pack["localization"]["currency"] == "EUR"

    def test_language_is_nl_nl(self, nl_pack):
        assert nl_pack["localization"]["language"] == "nl_NL"

    def test_country_code_is_nl(self, nl_pack):
        assert nl_pack["localization"]["country_code"] == "NL"

    def test_post_install_has_set_currency(self, nl_pack):
        actions = nl_pack["localization"]["post_install"]
        assert {"set_currency": "EUR"} in actions

    def test_post_install_has_set_country(self, nl_pack):
        actions = nl_pack["localization"]["post_install"]
        assert {"set_country": "NL"} in actions


# ---------------------------------------------------------------------------
# fiscal
# ---------------------------------------------------------------------------

class TestCountryNLFiscal:
    def test_tax_name_is_btw(self, nl_pack):
        """Dutch VAT is called BTW (Belasting over de Toegevoegde Waarde)."""
        assert nl_pack["fiscal"]["tax_name"] == "BTW"

    def test_tax_rate_is_21_percent(self, nl_pack):
        """Standard Dutch BTW rate is 21%."""
        assert nl_pack["fiscal"]["tax_rate"] == 0.21

    def test_id_label_is_btw_nummer(self, nl_pack):
        assert nl_pack["fiscal"]["id_label"] == "BTW-nummer"

    def test_faker_person_id_is_ssn(self, nl_pack):
        """nl_NL SSN generates BSN (Burgerservicenummer)."""
        assert nl_pack["fiscal"]["faker_person_id"] == "ssn"

    def test_faker_company_id_is_ssn(self, nl_pack):
        assert nl_pack["fiscal"]["faker_company_id"] == "ssn"


# ---------------------------------------------------------------------------
# partner_fields
# ---------------------------------------------------------------------------

class TestCountryNLPartnerFields:
    def test_vat_prefix_is_nl(self, nl_pack):
        """EU VAT format requires NL prefix."""
        assert nl_pack["partner_fields"]["vat_prefix"] == "NL"

    def test_no_latam_identification_type(self, nl_pack):
        """NL has no l10n_latam dependency — identification_type_name must be empty."""
        assert nl_pack["partner_fields"]["identification_type_name"] == ""

    def test_no_company_taxpayer_field(self, nl_pack):
        """l10n_nl does not require extra taxpayer fields on partners."""
        assert nl_pack["partner_fields"]["company_taxpayer_field"] == ""

    def test_no_person_taxpayer_field(self, nl_pack):
        assert nl_pack["partner_fields"]["person_taxpayer_field"] == ""

    def test_partner_fields_has_all_required_keys(self, nl_pack):
        required = [
            "vat_prefix",
            "identification_type_name",
            "company_taxpayer_field",
            "company_taxpayer_value",
            "person_taxpayer_field",
            "person_taxpayer_value",
        ]
        for key in required:
            assert key in nl_pack["partner_fields"], f"Missing partner_fields key: {key}"


# ---------------------------------------------------------------------------
# banks
# ---------------------------------------------------------------------------

class TestCountryNLBanks:
    def test_banks_have_required_fields(self, nl_pack):
        for bank in nl_pack["banks"]:
            assert "code" in bank
            assert "name" in bank
            assert "swift" in bank

    def test_ing_present(self, nl_pack):
        """ING Bank must be present (largest retail bank NL)."""
        codes = {b["code"] for b in nl_pack["banks"]}
        assert "INGB" in codes

    def test_abn_amro_present(self, nl_pack):
        codes = {b["code"] for b in nl_pack["banks"]}
        assert "ABNA" in codes

    def test_rabobank_present(self, nl_pack):
        codes = {b["code"] for b in nl_pack["banks"]}
        assert "RABO" in codes

    def test_minimum_bank_count(self, nl_pack):
        """Pack must define at least 5 banks."""
        assert len(nl_pack["banks"]) >= 5

    def test_swift_codes_have_nl_suffix(self, nl_pack):
        """All Dutch SWIFT codes must contain 'NL'."""
        for bank in nl_pack["banks"]:
            assert "NL" in bank["swift"], (
                f"SWIFT code {bank['swift']} for {bank['name']} missing NL"
            )


# ---------------------------------------------------------------------------
# geography
# ---------------------------------------------------------------------------

class TestCountryNLGeography:
    def test_has_12_provinces(self, nl_pack):
        """Netherlands has exactly 12 provinces."""
        assert len(nl_pack["geography"]["regions"]) == 12

    def test_noord_holland_is_default(self, nl_pack):
        """Noord-Holland (Amsterdam) is the default province."""
        nh = next(
            r for r in nl_pack["geography"]["regions"] if r["code"] == "NH"
        )
        assert nh.get("default") is True

    def test_regions_have_required_fields(self, nl_pack):
        for region in nl_pack["geography"]["regions"]:
            assert "code" in region
            assert "name" in region
            assert "capital" in region

    def test_exactly_one_default_region(self, nl_pack):
        defaults = [r for r in nl_pack["geography"]["regions"] if r.get("default")]
        assert len(defaults) == 1

    def test_core_provinces_present(self, nl_pack):
        codes = {r["code"] for r in nl_pack["geography"]["regions"]}
        for expected in ("NH", "ZH", "UT", "NB", "GE"):
            assert expected in codes, f"Missing province code: {expected}"


# ---------------------------------------------------------------------------
# addresses
# ---------------------------------------------------------------------------

class TestCountryNLAddresses:
    def test_has_cities_by_province(self, nl_pack):
        cities = nl_pack["addresses"]["cities_by_province"]
        assert "Noord-Holland" in cities
        assert len(cities["Noord-Holland"]) > 0

    def test_amsterdam_in_noord_holland(self, nl_pack):
        cities = nl_pack["addresses"]["cities_by_province"]["Noord-Holland"]
        assert "Amsterdam" in cities

    def test_rotterdam_in_zuid_holland(self, nl_pack):
        cities = nl_pack["addresses"]["cities_by_province"]["Zuid-Holland"]
        assert "Rotterdam" in cities

    def test_has_street_suffixes(self, nl_pack):
        suffixes = nl_pack["addresses"]["street_suffixes"]
        assert len(suffixes) > 0

    def test_dutch_street_suffixes_present(self, nl_pack):
        suffixes = nl_pack["addresses"]["street_suffixes"]
        assert "straat" in suffixes
        assert "laan" in suffixes


# ---------------------------------------------------------------------------
# company
# ---------------------------------------------------------------------------

class TestCountryNLCompany:
    def test_bv_in_name_suffixes(self, nl_pack):
        """B.V. is the most common Dutch legal form."""
        assert "B.V." in nl_pack["company"]["name_suffixes"]

    def test_nv_in_name_suffixes(self, nl_pack):
        assert "N.V." in nl_pack["company"]["name_suffixes"]

    def test_has_economic_activities(self, nl_pack):
        activities = nl_pack["company"]["economic_activities"]
        assert len(activities) > 0

    def test_economic_activities_have_required_fields(self, nl_pack):
        for act in nl_pack["company"]["economic_activities"]:
            assert "code" in act
            assert "description" in act

    def test_minimum_activity_count(self, nl_pack):
        """Pack must define at least 10 SBI codes."""
        assert len(nl_pack["company"]["economic_activities"]) >= 10


# ---------------------------------------------------------------------------
# Faker integration smoke test
# ---------------------------------------------------------------------------

class TestFakerNLIntegration:
    def test_faker_nl_nl_ssn(self):
        """Faker nl_NL must generate BSN (ssn)."""
        from faker import Faker
        fake = Faker("nl_NL")
        fake.seed_instance(42)
        bsn = fake.ssn()
        assert isinstance(bsn, str)
        assert len(bsn) > 0

    def test_faker_nl_nl_name(self):
        """Faker nl_NL must generate Dutch names."""
        from faker import Faker
        fake = Faker("nl_NL")
        fake.seed_instance(42)
        name = fake.name()
        assert isinstance(name, str)
        assert len(name) > 0

    def test_faker_nl_nl_company(self):
        """Faker nl_NL must generate company names."""
        from faker import Faker
        fake = Faker("nl_NL")
        fake.seed_instance(42)
        company = fake.company()
        assert isinstance(company, str)
        assert len(company) > 0

    def test_faker_methods_match_pack_config(self, nl_pack):
        """Faker methods declared in pack config must be callable on nl_NL."""
        from faker import Faker
        fake = Faker("nl_NL")
        fiscal = nl_pack["fiscal"]
        assert hasattr(fake, fiscal["faker_person_id"])
        assert hasattr(fake, fiscal["faker_company_id"])

    def test_faker_nl_nl_phone_number(self):
        """Faker nl_NL must generate Dutch phone numbers."""
        from faker import Faker
        fake = Faker("nl_NL")
        fake.seed_instance(42)
        phone = fake.phone_number()
        assert isinstance(phone, str)
        assert len(phone) > 0
