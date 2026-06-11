"""
tests.test_pack_pt
~~~~~~~~~~~~~~~~~~

Structural integrity tests for the Portugal country pack (country_pt.yaml).

Covers:
- meta: required fields, code, locale, layers.
- localization: odoo modules, install order, currency, language.
- fiscal: IVA tax rate, id label, faker methods.
- partner_fields: vat_prefix, empty l10n_latam fields (no LATAM dependency).
- banks: required fields, CGD / Millennium / BPI presence.
- geography: 20 regions (18 districts + Açores + Madeira), Lisboa as default.
- addresses: cities by district.
- company: name suffixes (Lda. required), economic activities (CAE codes).
- Faker pt_PT integration smoke test.
- vat_generators._pt_nif: mod-11 checksum validation.

:author: Hector Colina / Team360 <https://team360.cl>
"""

import pytest

from sandboxerp.packs.loader import load_country_pack


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def pt_pack():
    """Load country_pt.yaml once for all structural tests."""
    return load_country_pack("pt")


# ---------------------------------------------------------------------------
# Structural integrity
# ---------------------------------------------------------------------------

class TestCountryPTStructure:
    REQUIRED_SECTIONS = [
        "meta", "localization", "fiscal", "partner_fields",
        "banks", "addresses", "geography", "company",
    ]

    def test_required_sections_present(self, pt_pack):
        for section in self.REQUIRED_SECTIONS:
            assert section in pt_pack, f"Missing section: {section}"


# ---------------------------------------------------------------------------
# meta
# ---------------------------------------------------------------------------

class TestCountryPTMeta:
    def test_meta_code(self, pt_pack):
        assert pt_pack["meta"]["code"] == "pt"

    def test_meta_name(self, pt_pack):
        assert pt_pack["meta"]["name"] == "Portugal"

    def test_meta_locale(self, pt_pack):
        assert pt_pack["meta"]["locale"] == "pt_PT"

    def test_meta_layers(self, pt_pack):
        assert 1 in pt_pack["meta"]["layers"]
        assert 2 in pt_pack["meta"]["layers"]


# ---------------------------------------------------------------------------
# localization
# ---------------------------------------------------------------------------

class TestCountryPTLocalization:
    def test_has_l10n_pt_module(self, pt_pack):
        modules = pt_pack["localization"]["odoo_modules"]["install_order"]
        assert "l10n_pt" in modules

    def test_currency_is_eur(self, pt_pack):
        assert pt_pack["localization"]["currency"] == "EUR"

    def test_language_is_pt_pt(self, pt_pack):
        assert pt_pack["localization"]["language"] == "pt_PT"

    def test_country_code_is_pt(self, pt_pack):
        assert pt_pack["localization"]["country_code"] == "PT"

    def test_post_install_has_set_currency(self, pt_pack):
        actions = pt_pack["localization"]["post_install"]
        assert {"set_currency": "EUR"} in actions

    def test_post_install_has_set_country(self, pt_pack):
        actions = pt_pack["localization"]["post_install"]
        assert {"set_country": "PT"} in actions


# ---------------------------------------------------------------------------
# fiscal
# ---------------------------------------------------------------------------

class TestCountryPTFiscal:
    def test_tax_name_is_iva(self, pt_pack):
        """Portuguese VAT is called IVA."""
        assert pt_pack["fiscal"]["tax_name"] == "IVA"

    def test_tax_rate_is_23_percent(self, pt_pack):
        """Standard Portuguese IVA rate is 23%."""
        assert pt_pack["fiscal"]["tax_rate"] == 0.23

    def test_id_label_is_nif(self, pt_pack):
        assert pt_pack["fiscal"]["id_label"] == "NIF"

    def test_faker_person_id_is_vat_id(self, pt_pack):
        assert pt_pack["fiscal"]["faker_person_id"] == "vat_id"

    def test_faker_company_id_is_vat_id(self, pt_pack):
        assert pt_pack["fiscal"]["faker_company_id"] == "vat_id"


# ---------------------------------------------------------------------------
# partner_fields
# ---------------------------------------------------------------------------

class TestCountryPTPartnerFields:
    def test_vat_prefix_is_pt(self, pt_pack):
        """EU VAT format requires PT prefix."""
        assert pt_pack["partner_fields"]["vat_prefix"] == "PT"

    def test_no_latam_identification_type(self, pt_pack):
        """PT has no l10n_latam dependency."""
        assert pt_pack["partner_fields"]["identification_type_name"] == ""

    def test_no_company_taxpayer_field(self, pt_pack):
        assert pt_pack["partner_fields"]["company_taxpayer_field"] == ""

    def test_no_person_taxpayer_field(self, pt_pack):
        assert pt_pack["partner_fields"]["person_taxpayer_field"] == ""

    def test_partner_fields_has_all_required_keys(self, pt_pack):
        required = [
            "vat_prefix",
            "identification_type_name",
            "company_taxpayer_field",
            "company_taxpayer_value",
            "person_taxpayer_field",
            "person_taxpayer_value",
        ]
        for key in required:
            assert key in pt_pack["partner_fields"], f"Missing key: {key}"


# ---------------------------------------------------------------------------
# banks
# ---------------------------------------------------------------------------

class TestCountryPTBanks:
    def test_banks_have_required_fields(self, pt_pack):
        for bank in pt_pack["banks"]:
            assert "code" in bank
            assert "name" in bank
            assert "swift" in bank

    def test_cgd_present(self, pt_pack):
        """Caixa Geral de Depósitos must be present (largest PT bank)."""
        codes = {b["code"] for b in pt_pack["banks"]}
        assert "0010" in codes

    def test_millennium_present(self, pt_pack):
        codes = {b["code"] for b in pt_pack["banks"]}
        assert "0033" in codes

    def test_bpi_present(self, pt_pack):
        codes = {b["code"] for b in pt_pack["banks"]}
        assert "0035" in codes

    def test_minimum_bank_count(self, pt_pack):
        assert len(pt_pack["banks"]) >= 5

    def test_swift_codes_have_pt_suffix(self, pt_pack):
        """All Portuguese SWIFT codes must contain 'PT'."""
        for bank in pt_pack["banks"]:
            assert "PT" in bank["swift"], (
                f"SWIFT code {bank['swift']} for {bank['name']} missing PT"
            )


# ---------------------------------------------------------------------------
# geography
# ---------------------------------------------------------------------------

class TestCountryPTGeography:
    def test_has_20_regions(self, pt_pack):
        """Portugal has 18 districts + Açores + Madeira = 20 regions."""
        assert len(pt_pack["geography"]["regions"]) == 20

    def test_lisboa_is_default(self, pt_pack):
        lis = next(
            r for r in pt_pack["geography"]["regions"] if r["code"] == "LIS"
        )
        assert lis.get("default") is True

    def test_regions_have_required_fields(self, pt_pack):
        for region in pt_pack["geography"]["regions"]:
            assert "code" in region
            assert "name" in region
            assert "capital" in region

    def test_exactly_one_default_region(self, pt_pack):
        defaults = [r for r in pt_pack["geography"]["regions"] if r.get("default")]
        assert len(defaults) == 1

    def test_core_regions_present(self, pt_pack):
        codes = {r["code"] for r in pt_pack["geography"]["regions"]}
        for expected in ("LIS", "POR", "FAR", "ACO", "MAD"):
            assert expected in codes, f"Missing region code: {expected}"


# ---------------------------------------------------------------------------
# addresses
# ---------------------------------------------------------------------------

class TestCountryPTAddresses:
    def test_has_cities_by_district(self, pt_pack):
        cities = pt_pack["addresses"]["cities_by_district"]
        assert "Lisboa" in cities
        assert len(cities["Lisboa"]) > 0

    def test_lisboa_in_lisboa_district(self, pt_pack):
        cities = pt_pack["addresses"]["cities_by_district"]["Lisboa"]
        assert "Lisboa" in cities

    def test_porto_in_porto_district(self, pt_pack):
        cities = pt_pack["addresses"]["cities_by_district"]["Porto"]
        assert "Porto" in cities

    def test_has_street_suffixes(self, pt_pack):
        suffixes = pt_pack["addresses"]["street_suffixes"]
        assert len(suffixes) > 0

    def test_portuguese_street_suffixes_present(self, pt_pack):
        suffixes = pt_pack["addresses"]["street_suffixes"]
        assert "Rua" in suffixes
        assert "Avenida" in suffixes


# ---------------------------------------------------------------------------
# company
# ---------------------------------------------------------------------------

class TestCountryPTCompany:
    def test_lda_in_name_suffixes(self, pt_pack):
        """Lda. is the most common Portuguese legal form."""
        assert "Lda." in pt_pack["company"]["name_suffixes"]

    def test_sa_in_name_suffixes(self, pt_pack):
        assert "S.A." in pt_pack["company"]["name_suffixes"]

    def test_has_economic_activities(self, pt_pack):
        assert len(pt_pack["company"]["economic_activities"]) > 0

    def test_economic_activities_have_required_fields(self, pt_pack):
        for act in pt_pack["company"]["economic_activities"]:
            assert "code" in act
            assert "description" in act

    def test_minimum_activity_count(self, pt_pack):
        assert len(pt_pack["company"]["economic_activities"]) >= 10


# ---------------------------------------------------------------------------
# Faker integration smoke test
# ---------------------------------------------------------------------------

class TestFakerPTIntegration:
    def test_faker_pt_pt_vat_id(self):
        """Faker pt_PT must generate VAT IDs."""
        from faker import Faker
        fake = Faker("pt_PT")
        fake.seed_instance(42)
        vat = fake.vat_id()
        assert isinstance(vat, str)
        assert vat.startswith("PT")
        assert len(vat) == 11  # PT + 9 digits

    def test_faker_pt_pt_name(self):
        from faker import Faker
        fake = Faker("pt_PT")
        fake.seed_instance(42)
        assert isinstance(fake.name(), str)

    def test_faker_pt_pt_company(self):
        from faker import Faker
        fake = Faker("pt_PT")
        fake.seed_instance(42)
        assert isinstance(fake.company(), str)

    def test_faker_methods_match_pack_config(self, pt_pack):
        from faker import Faker
        fake = Faker("pt_PT")
        fiscal = pt_pack["fiscal"]
        assert hasattr(fake, fiscal["faker_person_id"])
        assert hasattr(fake, fiscal["faker_company_id"])


# ---------------------------------------------------------------------------
# vat_generators — PT NIF mod-11 checksum
# ---------------------------------------------------------------------------

class TestPTNIFGenerator:
    def test_generates_9_digit_string(self):
        import random
        from sandboxerp.engine.vat_generators import generate_vat
        rng = random.Random(42)
        nif = generate_vat("pt", rng)
        assert isinstance(nif, str)
        assert len(nif) == 9
        assert nif.isdigit()

    def test_passes_mod11_checksum(self):
        import random
        from sandboxerp.engine.vat_generators import generate_vat
        rng = random.Random(42)
        for _ in range(20):
            nif = generate_vat("pt", rng)
            digits = [int(d) for d in nif]
            weights = [9, 8, 7, 6, 5, 4, 3, 2]
            total = sum(d * w for d, w in zip(digits[:8], weights))
            remainder = total % 11
            expected_check = 0 if remainder <= 1 else 11 - remainder
            assert digits[8] == expected_check, (
                f"NIF {nif} failed mod-11: expected check {expected_check}, got {digits[8]}"
            )

    def test_first_digit_is_valid_person_type(self):
        import random
        from sandboxerp.engine.vat_generators import generate_vat
        rng = random.Random(42)
        first_digits = {int(generate_vat("pt", rng)[0]) for _ in range(50)}
        assert first_digits.issubset({1, 2, 5})
