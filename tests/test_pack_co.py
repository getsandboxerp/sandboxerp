"""
tests.test_pack_co
~~~~~~~~~~~~~~~~~~

Structural and unit tests for the Colombia country pack (``country_co.yaml``)
and its associated VAT generator.

Covers:
- ``country_co.yaml``: meta, fiscal, partner_fields, localization.
- ``vat_generators._co_nit``: DIAN mod-11 verification digit, format,
  reproducibility.

:author: Hector Colina / Team360 <hector.colina@team360.cl> | https://team360.cl
"""

import random

import pytest

from sandboxerp.packs.loader import load_country_pack


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def co_pack():
    """Load country_co.yaml once for all structural tests."""
    return load_country_pack("co")


# ---------------------------------------------------------------------------
# NIT verification digit helper — mirrors _co_nit algorithm
# ---------------------------------------------------------------------------

_CO_NIT_WEIGHTS = [41, 37, 29, 23, 19, 17, 13, 7, 3]


def _validate_nit(nit_str: str) -> bool:
    """Return True if *nit_str* has a valid DIAN verification digit.

    Expected format: ``XXXXXXXXX-D`` (9 digits, hyphen, 1 digit).
    """
    parts = nit_str.split("-")
    if len(parts) != 2:
        return False
    base, dv_str = parts
    if len(base) != 9 or not base.isdigit() or not dv_str.isdigit():
        return False
    digits = [int(c) for c in base]
    total = sum(d * w for d, w in zip(digits, _CO_NIT_WEIGHTS))
    remainder = total % 11
    expected_dv = remainder if remainder <= 1 else 11 - remainder
    return int(dv_str) == expected_dv


# ---------------------------------------------------------------------------
# country_co.yaml — meta
# ---------------------------------------------------------------------------

class TestCountryCOMeta:
    def test_meta_exists(self, co_pack):
        assert "meta" in co_pack

    def test_country_code_is_co(self, co_pack):
        assert co_pack["meta"]["code"] == "co"

    def test_locale_is_es_co(self, co_pack):
        assert co_pack["meta"]["locale"] == "es_CO"

    def test_layers_include_1_and_2(self, co_pack):
        assert 1 in co_pack["meta"]["layers"]
        assert 2 in co_pack["meta"]["layers"]


# ---------------------------------------------------------------------------
# country_co.yaml — localization
# ---------------------------------------------------------------------------

class TestCountryCOLocalization:
    def test_localization_exists(self, co_pack):
        assert "localization" in co_pack

    def test_currency_is_cop(self, co_pack):
        assert co_pack["localization"]["currency"] == "COP"

    def test_country_code_is_co(self, co_pack):
        assert co_pack["localization"]["country_code"] == "CO"

    def test_l10n_co_in_install_order(self, co_pack):
        modules = co_pack["localization"]["odoo_modules"]["install_order"]
        assert "l10n_co" in modules


# ---------------------------------------------------------------------------
# country_co.yaml — fiscal
# ---------------------------------------------------------------------------

class TestCountryCOFiscal:
    def test_fiscal_exists(self, co_pack):
        assert "fiscal" in co_pack

    def test_vat_rate_is_19(self, co_pack):
        assert co_pack["fiscal"]["tax_rate"] == pytest.approx(0.19)

    def test_id_label_is_nit(self, co_pack):
        assert co_pack["fiscal"]["id_label"] == "NIT"

    def test_vat_format_is_generator(self, co_pack):
        assert co_pack["fiscal"]["vat_format"] == "__generator__"

    def test_tax_name_is_iva(self, co_pack):
        assert co_pack["fiscal"]["tax_name"] == "IVA"


# ---------------------------------------------------------------------------
# country_co.yaml — partner_fields
# ---------------------------------------------------------------------------

class TestCountryCOPartnerFields:
    def test_partner_fields_exists(self, co_pack):
        assert "partner_fields" in co_pack

    def test_vat_prefix_is_empty(self, co_pack):
        """NIT in Odoo CO needs no country prefix — stored as XXXXXXXXX-D."""
        assert co_pack["partner_fields"]["vat_prefix"] == ""

    def test_identification_type_is_nit(self, co_pack):
        assert co_pack["partner_fields"]["identification_type_name"] == "NIT"

    def test_partner_fields_has_all_required_keys(self, co_pack):
        required = [
            "vat_prefix",
            "identification_type_name",
            "company_taxpayer_field",
            "company_taxpayer_value",
            "person_taxpayer_field",
            "person_taxpayer_value",
        ]
        for key in required:
            assert key in co_pack["partner_fields"], f"Missing key: {key}"


# ---------------------------------------------------------------------------
# vat_generators — CO NIT
# ---------------------------------------------------------------------------

class TestCONITGenerator:
    """Tests for _co_nit: 9-digit base + hyphen + DIAN verification digit."""

    def test_generates_string_with_hyphen(self):
        from sandboxerp.engine.vat_generators import _co_nit
        rng = random.Random(42)
        nit = _co_nit(rng)
        assert isinstance(nit, str)
        assert "-" in nit

    def test_format_is_9_digits_hyphen_1_digit(self):
        from sandboxerp.engine.vat_generators import _co_nit
        rng = random.Random(42)
        for _ in range(20):
            nit = _co_nit(rng)
            parts = nit.split("-")
            assert len(parts) == 2, f"NIT {nit} has wrong number of parts"
            assert len(parts[0]) == 9, f"NIT {nit} base is not 9 digits"
            assert parts[0].isdigit(), f"NIT {nit} base contains non-digits"
            assert parts[1].isdigit(), f"NIT {nit} DV is not a digit"

    def test_verification_digit_is_valid(self):
        """Verification digit must satisfy the DIAN mod-11 algorithm."""
        from sandboxerp.engine.vat_generators import _co_nit
        rng = random.Random(42)
        for _ in range(50):
            nit = _co_nit(rng)
            assert _validate_nit(nit), f"NIT {nit} has invalid verification digit"

    def test_1000_nits_all_valid(self):
        from sandboxerp.engine.vat_generators import _co_nit
        rng = random.Random(42)
        errors = [
            nit for nit in (_co_nit(rng) for _ in range(1000))
            if not _validate_nit(nit)
        ]
        assert not errors, f"Invalid NITs: {errors[:5]}"

    def test_generate_vat_returns_nit_for_co(self):
        """generate_vat('co') returns a NIT string in XXXXXXXXX-D format."""
        from sandboxerp.engine.vat_generators import generate_vat
        rng = random.Random(42)
        result = generate_vat("co", rng)
        assert result is not None
        assert "-" in result
        assert _validate_nit(result)

    def test_reproducible_with_same_seed(self):
        from sandboxerp.engine.vat_generators import _co_nit
        rng_a = random.Random(99)
        rng_b = random.Random(99)
        for _ in range(10):
            assert _co_nit(rng_a) == _co_nit(rng_b)

    def test_dv_is_single_digit(self):
        """Verification digit must always be 0–9 (mod-11 guarantees this)."""
        from sandboxerp.engine.vat_generators import _co_nit
        rng = random.Random(42)
        for _ in range(100):
            nit = _co_nit(rng)
            dv = int(nit.split("-")[1])
            assert 0 <= dv <= 9, f"NIT {nit} has DV outside 0-9 range"
