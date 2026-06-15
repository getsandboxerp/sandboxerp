"""
tests.test_pack_es
~~~~~~~~~~~~~~~~~~

Structural integrity tests for the Spain country pack (country_es.yaml).

Covers:
- meta: required fields, code, locale, layers.
- localization: odoo modules, install order, currency, language.
- fiscal: IVA tax rate 21%, id label, faker methods.
- partner_fields: vat_prefix ES, empty l10n_latam fields.
- banks: required fields, Santander / BBVA / CaixaBank presence.
- geography: 17 CCAA, Madrid as default.
- addresses: cities by region.
- company: name suffixes (S.L. required), economic activities (CNAE codes).
- vat_generators._es_nif: control letter validation.
- vat_generators._es_cif: control character validation.

:author: Hector Colina / Team360 <https://team360.cl>
"""

import pytest

from sandboxerp.packs.loader import load_country_pack


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def es_pack():
    """Load country_es.yaml once for all structural tests."""
    return load_country_pack("es")


# ---------------------------------------------------------------------------
# Structural integrity
# ---------------------------------------------------------------------------

class TestCountryESStructure:
    REQUIRED_SECTIONS = [
        "meta", "localization", "fiscal", "partner_fields",
        "banks", "addresses", "geography", "company",
    ]

    def test_required_sections_present(self, es_pack):
        for section in self.REQUIRED_SECTIONS:
            assert section in es_pack, f"Missing section: {section}"


# ---------------------------------------------------------------------------
# meta
# ---------------------------------------------------------------------------

class TestCountryESMeta:
    def test_meta_code(self, es_pack):
        assert es_pack["meta"]["code"] == "es"

    def test_meta_name(self, es_pack):
        assert es_pack["meta"]["name"] == "Spain"

    def test_meta_locale(self, es_pack):
        assert es_pack["meta"]["locale"] == "es_ES"

    def test_meta_layers(self, es_pack):
        assert 1 in es_pack["meta"]["layers"]
        assert 2 in es_pack["meta"]["layers"]


# ---------------------------------------------------------------------------
# localization
# ---------------------------------------------------------------------------

class TestCountryESLocalization:
    def test_has_l10n_es_module(self, es_pack):
        modules = es_pack["localization"]["odoo_modules"]["install_order"]
        assert "l10n_es" in modules

    def test_currency_is_eur(self, es_pack):
        assert es_pack["localization"]["currency"] == "EUR"

    def test_language_is_es_es(self, es_pack):
        assert es_pack["localization"]["language"] == "es_ES"

    def test_country_code_is_es(self, es_pack):
        assert es_pack["localization"]["country_code"] == "ES"

    def test_post_install_has_set_currency(self, es_pack):
        actions = es_pack["localization"]["post_install"]
        assert {"set_currency": "EUR"} in actions

    def test_post_install_has_set_country(self, es_pack):
        actions = es_pack["localization"]["post_install"]
        assert {"set_country": "ES"} in actions


# ---------------------------------------------------------------------------
# fiscal
# ---------------------------------------------------------------------------

class TestCountryESFiscal:
    def test_tax_name_is_iva(self, es_pack):
        assert es_pack["fiscal"]["tax_name"] == "IVA"

    def test_tax_rate_is_21_percent(self, es_pack):
        """Standard Spanish IVA rate is 21%."""
        assert es_pack["fiscal"]["tax_rate"] == 0.21

    def test_id_label_is_nif(self, es_pack):
        assert es_pack["fiscal"]["id_label"] == "NIF"


# ---------------------------------------------------------------------------
# partner_fields
# ---------------------------------------------------------------------------

class TestCountryESPartnerFields:
    def test_vat_prefix_is_es(self, es_pack):
        assert es_pack["partner_fields"]["vat_prefix"] == "ES"

    def test_no_latam_identification_type(self, es_pack):
        assert es_pack["partner_fields"]["identification_type_name"] == ""

    def test_no_company_taxpayer_field(self, es_pack):
        assert es_pack["partner_fields"]["company_taxpayer_field"] == ""

    def test_no_person_taxpayer_field(self, es_pack):
        assert es_pack["partner_fields"]["person_taxpayer_field"] == ""

    def test_partner_fields_has_all_required_keys(self, es_pack):
        required = [
            "vat_prefix",
            "identification_type_name",
            "company_taxpayer_field",
            "company_taxpayer_value",
            "person_taxpayer_field",
            "person_taxpayer_value",
        ]
        for key in required:
            assert key in es_pack["partner_fields"], f"Missing key: {key}"


# ---------------------------------------------------------------------------
# banks
# ---------------------------------------------------------------------------

class TestCountryESBanks:
    def test_banks_have_required_fields(self, es_pack):
        for bank in es_pack["banks"]:
            assert "code" in bank
            assert "name" in bank
            assert "swift" in bank

    def test_santander_present(self, es_pack):
        codes = {b["code"] for b in es_pack["banks"]}
        assert "0049" in codes

    def test_bbva_present(self, es_pack):
        codes = {b["code"] for b in es_pack["banks"]}
        assert "0182" in codes

    def test_caixabank_present(self, es_pack):
        codes = {b["code"] for b in es_pack["banks"]}
        assert "2100" in codes

    def test_minimum_bank_count(self, es_pack):
        assert len(es_pack["banks"]) >= 5

    def test_swift_codes_have_es(self, es_pack):
        for bank in es_pack["banks"]:
            assert "ES" in bank["swift"], (
                f"SWIFT code {bank['swift']} for {bank['name']} missing ES"
            )


# ---------------------------------------------------------------------------
# geography
# ---------------------------------------------------------------------------

class TestCountryESGeography:
    def test_has_17_ccaa(self, es_pack):
        """Spain has 17 Comunidades Autónomas."""
        assert len(es_pack["geography"]["regions"]) == 17

    def test_madrid_is_default(self, es_pack):
        mad = next(
            r for r in es_pack["geography"]["regions"] if r["code"] == "MD"
        )
        assert mad.get("default") is True

    def test_regions_have_required_fields(self, es_pack):
        for region in es_pack["geography"]["regions"]:
            assert "code" in region
            assert "name" in region
            assert "capital" in region

    def test_exactly_one_default_region(self, es_pack):
        defaults = [r for r in es_pack["geography"]["regions"] if r.get("default")]
        assert len(defaults) == 1

    def test_core_regions_present(self, es_pack):
        codes = {r["code"] for r in es_pack["geography"]["regions"]}
        for expected in ("MD", "CT", "AN", "VC", "PV"):
            assert expected in codes, f"Missing region code: {expected}"


# ---------------------------------------------------------------------------
# addresses
# ---------------------------------------------------------------------------

class TestCountryESAddresses:
    def test_has_cities_by_region(self, es_pack):
        cities = es_pack["addresses"]["cities_by_region"]
        assert "Madrid" in cities
        assert len(cities["Madrid"]) > 0

    def test_madrid_in_madrid_region(self, es_pack):
        cities = es_pack["addresses"]["cities_by_region"]["Madrid"]
        assert "Madrid" in cities

    def test_barcelona_in_cataluna(self, es_pack):
        cities = es_pack["addresses"]["cities_by_region"]["Cataluña"]
        assert "Barcelona" in cities

    def test_has_street_suffixes(self, es_pack):
        assert len(es_pack["addresses"]["street_suffixes"]) > 0

    def test_spanish_street_suffixes_present(self, es_pack):
        suffixes = es_pack["addresses"]["street_suffixes"]
        assert "Calle" in suffixes
        assert "Avenida" in suffixes


# ---------------------------------------------------------------------------
# company
# ---------------------------------------------------------------------------

class TestCountryESCompany:
    def test_sl_in_name_suffixes(self, es_pack):
        """S.L. is the most common Spanish legal form."""
        assert "S.L." in es_pack["company"]["name_suffixes"]

    def test_sa_in_name_suffixes(self, es_pack):
        assert "S.A." in es_pack["company"]["name_suffixes"]

    def test_has_economic_activities(self, es_pack):
        assert len(es_pack["company"]["economic_activities"]) > 0

    def test_economic_activities_have_required_fields(self, es_pack):
        for act in es_pack["company"]["economic_activities"]:
            assert "code" in act
            assert "description" in act

    def test_minimum_activity_count(self, es_pack):
        assert len(es_pack["company"]["economic_activities"]) >= 10


# ---------------------------------------------------------------------------
# vat_generators — ES NIF control letter
# ---------------------------------------------------------------------------

class TestESNIFGenerator:
    _NIF_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"

    def test_generates_9_char_string(self):
        import random
        from sandboxerp.engine.vat_generators import generate_vat
        rng = random.Random(42)
        nif = generate_vat("es", rng)
        assert isinstance(nif, str)
        assert len(nif) == 9

    def test_first_8_chars_are_digits(self):
        import random
        from sandboxerp.engine.vat_generators import generate_vat
        rng = random.Random(42)
        nif = generate_vat("es", rng)
        assert nif[:8].isdigit()

    def test_last_char_is_letter(self):
        import random
        from sandboxerp.engine.vat_generators import generate_vat
        rng = random.Random(42)
        nif = generate_vat("es", rng)
        assert nif[-1].isalpha()

    def test_control_letter_is_correct(self):
        import random
        from sandboxerp.engine.vat_generators import generate_vat
        rng = random.Random(42)
        for _ in range(20):
            nif = generate_vat("es", rng)
            number = int(nif[:8])
            expected_letter = self._NIF_LETTERS[number % 23]
            assert nif[-1] == expected_letter, (
                f"NIF {nif} has wrong control letter: expected {expected_letter}"
            )


# ---------------------------------------------------------------------------
# vat_generators — ES CIF control character
# ---------------------------------------------------------------------------

class TestESCIFGenerator:
    def test_generates_9_char_string(self):
        import random
        from sandboxerp.engine.vat_generators import _es_cif
        rng = random.Random(42)
        cif = _es_cif(rng)
        assert isinstance(cif, str)
        assert len(cif) == 9

    def test_first_char_is_org_letter(self):
        import random
        from sandboxerp.engine.vat_generators import _es_cif
        rng = random.Random(42)
        valid_orgs = set("ABCDEFGHJNPQRSUVW")
        for _ in range(20):
            cif = _es_cif(rng)
            assert cif[0] in valid_orgs, f"CIF {cif} has invalid org letter"

    def test_middle_7_chars_are_digits(self):
        import random
        from sandboxerp.engine.vat_generators import _es_cif
        rng = random.Random(42)
        for _ in range(20):
            cif = _es_cif(rng)
            assert cif[1:8].isdigit(), f"CIF {cif} middle chars not digits"

    def test_control_char_is_valid(self):
        import random
        from sandboxerp.engine.vat_generators import _es_cif
        rng = random.Random(42)
        _LETTER_CONTROL_TYPES = "PQSW"
        _CIF_LETTERS = "JABCDEFGHI"
        for _ in range(50):
            cif = _es_cif(rng)
            org = cif[0]
            digits = [int(d) for d in cif[1:8]]
            odd_sum = sum(digits[i] for i in range(0, 7, 2))
            even_sum = 0
            for i in range(1, 7, 2):
                d = digits[i] * 2
                even_sum += d if d < 10 else d - 9
            total = odd_sum + even_sum
            control_digit = (10 - (total % 10)) % 10
            if org in _LETTER_CONTROL_TYPES:
                expected = _CIF_LETTERS[control_digit]
            else:
                expected = str(control_digit)
            assert cif[-1] == expected, (
                f"CIF {cif} has wrong control: expected {expected}"
            )
