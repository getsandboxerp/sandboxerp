"""
tests.test_pack_do
~~~~~~~~~~~~~~~~~~

Structural and unit tests for the Dominican Republic country pack
(``country_do.yaml``) and its associated VAT generator.

Covers:
- ``country_do.yaml``: meta, localization, fiscal, partner_fields, geography,
  banks, addresses, company.
- ``vat_generators._do_rnc``: DGII mod-11 check digit, format, reproducibility
  and registration in ``VAT_GENERATORS``.

:author: Hector Colina / Team360 <hector.colina@team360.cl> | https://team360.cl
"""

import random

import pytest
from faker import Faker

from sandboxerp.engine.vat_generators import VAT_GENERATORS, _do_rnc, generate_vat
from sandboxerp.packs.loader import load_country_pack


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def do_pack():
    """Load country_do.yaml once for all structural tests."""
    return load_country_pack("do")


# ---------------------------------------------------------------------------
# RNC check digit helper — independent re-implementation of the algorithm
# ---------------------------------------------------------------------------

_DO_RNC_WEIGHTS = [7, 9, 8, 6, 5, 4, 3, 2]


def _validate_rnc(rnc_str: str) -> bool:
    """Return True if *rnc_str* is a 9-digit RNC with a valid check digit."""
    rnc = rnc_str.replace("-", "")
    if len(rnc) != 9 or not rnc.isdigit():
        return False
    total = sum(int(d) * w for d, w in zip(rnc[:8], _DO_RNC_WEIGHTS))
    expected = (10 - total % 11) % 9 + 1
    return int(rnc[8]) == expected


# ---------------------------------------------------------------------------
# country_do.yaml — meta
# ---------------------------------------------------------------------------

class TestCountryDOMeta:
    def test_meta_exists(self, do_pack):
        assert "meta" in do_pack

    def test_country_code_is_do(self, do_pack):
        assert do_pack["meta"]["code"] == "do"

    def test_locale_is_supported_by_faker(self, do_pack):
        """Faker has no es_DO locale, so the pack must use one it supports."""
        Faker(do_pack["meta"]["locale"])

    def test_layers_include_1_and_2(self, do_pack):
        assert 1 in do_pack["meta"]["layers"]
        assert 2 in do_pack["meta"]["layers"]


# ---------------------------------------------------------------------------
# country_do.yaml — localization
# ---------------------------------------------------------------------------

class TestCountryDOLocalization:
    def test_localization_exists(self, do_pack):
        assert "localization" in do_pack

    def test_currency_is_dop(self, do_pack):
        assert do_pack["localization"]["currency"] == "DOP"

    def test_country_code_is_do(self, do_pack):
        assert do_pack["localization"]["country_code"] == "DO"

    def test_l10n_do_in_install_order(self, do_pack):
        modules = do_pack["localization"]["odoo_modules"]["install_order"]
        assert "l10n_do" in modules


# ---------------------------------------------------------------------------
# country_do.yaml — fiscal
# ---------------------------------------------------------------------------

class TestCountryDOFiscal:
    def test_fiscal_exists(self, do_pack):
        assert "fiscal" in do_pack

    def test_tax_rate_is_18(self, do_pack):
        assert do_pack["fiscal"]["tax_rate"] == pytest.approx(0.18)

    def test_tax_name_is_itbis(self, do_pack):
        assert do_pack["fiscal"]["tax_name"] == "ITBIS"

    def test_id_label_is_rnc(self, do_pack):
        assert do_pack["fiscal"]["id_label"] == "RNC"

    def test_vat_format_is_generator(self, do_pack):
        assert do_pack["fiscal"]["vat_format"] == "__generator__"


# ---------------------------------------------------------------------------
# country_do.yaml — partner_fields
# ---------------------------------------------------------------------------

class TestCountryDOPartnerFields:
    def test_partner_fields_exists(self, do_pack):
        assert "partner_fields" in do_pack

    def test_vat_prefix_is_empty(self, do_pack):
        assert do_pack["partner_fields"]["vat_prefix"] == ""

    def test_identification_type_is_rnc(self, do_pack):
        assert do_pack["partner_fields"]["identification_type_name"] == "RNC"

    def test_partner_fields_has_all_required_keys(self, do_pack):
        required = [
            "vat_prefix",
            "identification_type_name",
            "company_taxpayer_field",
            "company_taxpayer_value",
            "person_taxpayer_field",
            "person_taxpayer_value",
        ]
        for key in required:
            assert key in do_pack["partner_fields"], f"Missing key: {key}"


# ---------------------------------------------------------------------------
# country_do.yaml — geography, addresses, banks, company
# ---------------------------------------------------------------------------

class TestCountryDOGeography:
    def test_has_32_regions(self, do_pack):
        """31 provincias + Distrito Nacional."""
        assert len(do_pack["geography"]["regions"]) == 32

    def test_region_codes_are_unique(self, do_pack):
        codes = [r["code"] for r in do_pack["geography"]["regions"]]
        assert len(codes) == len(set(codes))

    def test_exactly_one_default_region(self, do_pack):
        defaults = [r for r in do_pack["geography"]["regions"] if r.get("default")]
        assert len(defaults) == 1
        assert defaults[0]["name"] == "Distrito Nacional"

    def test_cities_keys_are_known_regions(self, do_pack):
        names = {r["name"] for r in do_pack["geography"]["regions"]}
        for region in do_pack["addresses"]["cities_by_region"]:
            assert region in names, f"Unknown region in cities_by_region: {region}"

    def test_every_region_with_cities_has_at_least_one(self, do_pack):
        for region, cities in do_pack["addresses"]["cities_by_region"].items():
            assert cities, f"No cities for {region}"


class TestCountryDOBanksAndCompany:
    def test_has_banks_with_required_keys(self, do_pack):
        assert len(do_pack["banks"]) >= 5
        for bank in do_pack["banks"]:
            for key in ("code", "name", "short", "swift"):
                assert key in bank, f"Bank missing {key}: {bank}"

    def test_name_suffixes_include_srl(self, do_pack):
        assert "S.R.L." in do_pack["company"]["name_suffixes"]

    def test_activities_have_code_and_description(self, do_pack):
        for act in do_pack["company"]["economic_activities"]:
            assert act["code"] and act["description"]


# ---------------------------------------------------------------------------
# vat_generators — DO RNC
# ---------------------------------------------------------------------------

class TestDORNCGenerator:
    """Tests for _do_rnc: 9 digits, first digit 1, DGII mod-11 check digit."""

    def test_published_vectors_are_valid_for_helper(self):
        """Real RNCs from python-stdnum docs and a DGII lookup example."""
        assert _validate_rnc("101850043")
        assert _validate_rnc("1-01-85004-3")
        assert _validate_rnc("133032015")

    def test_helper_rejects_wrong_check_digit(self):
        assert not _validate_rnc("101850042")

    def test_format_is_nine_digits(self):
        rng = random.Random(42)
        for _ in range(100):
            rnc = _do_rnc(rng)
            assert len(rnc) == 9 and rnc.isdigit(), f"Bad format: {rnc}"

    def test_first_digit_is_one(self):
        rng = random.Random(42)
        for _ in range(100):
            assert _do_rnc(rng).startswith("1")

    def test_check_digit_valid_over_1000_samples(self):
        rng = random.Random(42)
        for _ in range(1000):
            rnc = _do_rnc(rng)
            assert _validate_rnc(rnc), f"Invalid RNC generated: {rnc}"

    def test_reproducible_with_same_seed(self):
        a = [_do_rnc(random.Random(7)) for _ in range(5)]
        b = [_do_rnc(random.Random(7)) for _ in range(5)]
        assert a == b

    def test_registered_in_vat_generators(self):
        assert VAT_GENERATORS["do"] is _do_rnc

    def test_generate_vat_dispatches_to_do(self):
        rnc = generate_vat("do", random.Random(42))
        assert rnc is not None and _validate_rnc(rnc)
