"""
tests.test_pack_fr
~~~~~~~~~~~~~~~~~~

Structural and unit tests for the France country pack (``country_fr.yaml``)
and its associated VAT generators.

Covers:
- ``country_fr.yaml``: meta, fiscal, partner_fields, currency, locale.
- ``vat_generators._fr_siren``: Luhn checksum, length, La Poste exclusion.
- ``vat_generators._fr_siret``: Luhn checksum, length, embedded SIREN validity.

:author: Hector Colina / Team360 <hector.colina@team360.cl> | https://team360.cl
"""

import random

import pytest

from sandboxerp.packs.loader import load_country_pack


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def fr_pack():
    """Load country_fr.yaml once for all structural tests."""
    return load_country_pack("fr")


# ---------------------------------------------------------------------------
# Luhn helper — mirrors the validation logic in vat_generators
# ---------------------------------------------------------------------------

def _luhn_valid(number: str) -> bool:
    """Return True if *number* passes the Luhn checksum (mod 10)."""
    digits = [int(c) for c in number]
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            doubled = d * 2
            total += doubled if doubled < 10 else doubled - 9
        else:
            total += d
    return total % 10 == 0


# ---------------------------------------------------------------------------
# country_fr.yaml — meta
# ---------------------------------------------------------------------------

class TestCountryFRMeta:
    def test_meta_exists(self, fr_pack):
        assert "meta" in fr_pack

    def test_country_code_is_fr(self, fr_pack):
        assert fr_pack["localization"]["country_code"] == "FR"

    def test_locale_is_fr(self, fr_pack):
        assert fr_pack["meta"]["locale"] == "fr_FR"

    def test_currency_is_eur(self, fr_pack):
        assert fr_pack["localization"]["currency"] == "EUR"


# ---------------------------------------------------------------------------
# country_fr.yaml — fiscal
# ---------------------------------------------------------------------------

class TestCountryFRFiscal:
    def test_fiscal_exists(self, fr_pack):
        assert "fiscal" in fr_pack

    def test_vat_rate_is_20(self, fr_pack):
        assert fr_pack["fiscal"]["tax_rate"] == pytest.approx(0.20)

    def test_id_label_is_siret(self, fr_pack):
        assert fr_pack["fiscal"]["id_label"] == "SIRET"

    def test_vat_format_is_generator(self, fr_pack):
        assert fr_pack["fiscal"]["vat_format"] == "__generator__"


# ---------------------------------------------------------------------------
# country_fr.yaml — partner_fields
# ---------------------------------------------------------------------------

class TestCountryFRPartnerFields:
    def test_vat_prefix_is_fr(self, fr_pack):
        assert fr_pack["partner_fields"]["vat_prefix"] == "FR"

    def test_no_latam_identification_type(self, fr_pack):
        assert fr_pack["partner_fields"]["identification_type_name"] == ""

    def test_partner_fields_has_all_required_keys(self, fr_pack):
        required = [
            "vat_prefix",
            "identification_type_name",
            "company_taxpayer_field",
            "company_taxpayer_value",
            "person_taxpayer_field",
            "person_taxpayer_value",
        ]
        for key in required:
            assert key in fr_pack["partner_fields"], f"Missing key: {key}"


# ---------------------------------------------------------------------------
# vat_generators — FR SIREN
# ---------------------------------------------------------------------------

class TestFRSIRENGenerator:
    """Tests for _fr_siren: 9-digit number validated by Luhn."""

    def test_generates_9_char_string(self):
        from sandboxerp.engine.vat_generators import _fr_siren
        rng = random.Random(42)
        siren = _fr_siren(rng)
        assert isinstance(siren, str)
        assert len(siren) == 9

    def test_all_chars_are_digits(self):
        from sandboxerp.engine.vat_generators import _fr_siren
        rng = random.Random(42)
        for _ in range(20):
            siren = _fr_siren(rng)
            assert siren.isdigit(), f"SIREN {siren} contains non-digit characters"

    def test_luhn_checksum_is_valid(self):
        from sandboxerp.engine.vat_generators import _fr_siren
        rng = random.Random(42)
        for _ in range(50):
            siren = _fr_siren(rng)
            assert _luhn_valid(siren), f"SIREN {siren} failed Luhn validation"

    def test_laposte_siren_is_excluded(self):
        """356000000 (La Poste) must never be generated."""
        from sandboxerp.engine.vat_generators import _fr_siren
        rng = random.Random(42)
        generated = {_fr_siren(rng) for _ in range(1000)}
        assert "356000000" not in generated

    def test_generate_vat_returns_fr_vat(self):
        """generate_vat('fr') returns an 11-char TVA intracommunautaire number.

        Format: 2-digit key + 9-digit SIREN (not a 14-digit SIRET).
        """
        from sandboxerp.engine.vat_generators import generate_vat
        rng = random.Random(42)
        result = generate_vat("fr", rng)
        assert result is not None
        assert len(result) == 11
        assert result.isdigit()


# ---------------------------------------------------------------------------
# vat_generators — FR SIRET
# ---------------------------------------------------------------------------

class TestFRSIRETGenerator:
    """Tests for _fr_siret: 14-digit number validated by Luhn."""

    def test_generates_14_char_string(self):
        from sandboxerp.engine.vat_generators import _fr_siret
        rng = random.Random(42)
        siret = _fr_siret(rng)
        assert isinstance(siret, str)
        assert len(siret) == 14

    def test_all_chars_are_digits(self):
        from sandboxerp.engine.vat_generators import _fr_siret
        rng = random.Random(42)
        for _ in range(20):
            siret = _fr_siret(rng)
            assert siret.isdigit(), f"SIRET {siret} contains non-digit characters"

    def test_full_siret_passes_luhn(self):
        from sandboxerp.engine.vat_generators import _fr_siret
        rng = random.Random(42)
        for _ in range(50):
            siret = _fr_siret(rng)
            assert _luhn_valid(siret), f"SIRET {siret} failed Luhn validation"

    def test_embedded_siren_passes_luhn(self):
        """The first 9 digits of a SIRET must also be a valid SIREN."""
        from sandboxerp.engine.vat_generators import _fr_siret
        rng = random.Random(42)
        for _ in range(50):
            siret = _fr_siret(rng)
            siren = siret[:9]
            assert _luhn_valid(siren), (
                f"SIRET {siret} has invalid embedded SIREN {siren}"
            )

    def test_laposte_siren_never_embedded(self):
        """SIRET must never be built on La Poste's reserved SIREN 356000000."""
        from sandboxerp.engine.vat_generators import _fr_siret
        rng = random.Random(42)
        for _ in range(1000):
            siret = _fr_siret(rng)
            assert siret[:9] != "356000000", (
                f"SIRET {siret} uses La Poste's reserved SIREN"
            )

    def test_reproducible_with_same_seed(self):
        """Same seed must always produce the same SIRET sequence."""
        from sandboxerp.engine.vat_generators import _fr_siret
        rng_a = random.Random(99)
        rng_b = random.Random(99)
        for _ in range(10):
            assert _fr_siret(rng_a) == _fr_siret(rng_b)
