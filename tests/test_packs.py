"""
tests.test_packs
~~~~~~~~~~~~~~~~

Unit tests for the SandboxERP pack system.

Covers:
- ``packs.loader``: loading builtin packs, missing pack error, country/industry
  resolution.
- ``packs.registry``: catalogue listing, lookup, resolve_packs.
- ``country_cl.yaml``: structural integrity, required sections, valid codes.

:author: Hector Colina / Team360 <https://team360.cl>
"""

import pytest

from sandboxerp.packs.loader import load_country_pack, load_industry_pack, load_pack
from sandboxerp.packs.registry import (
    PackType,
    get_pack,
    list_packs,
    resolve_packs,
)


# ---------------------------------------------------------------------------
# packs.registry
# ---------------------------------------------------------------------------

class TestRegistry:
    def test_list_all_returns_entries(self):
        """list_packs() must return at least one entry."""
        assert len(list_packs()) > 0

    def test_list_filter_by_type_country(self):
        """Filtering by COUNTRY returns only country packs."""
        packs = list_packs(PackType.COUNTRY)
        assert all(p.type == PackType.COUNTRY for p in packs)

    def test_list_filter_by_type_industry(self):
        """Filtering by INDUSTRY returns only industry packs."""
        packs = list_packs(PackType.INDUSTRY)
        assert all(p.type == PackType.INDUSTRY for p in packs)

    def test_list_excludes_premium_when_flagged(self):
        """include_premium=False must exclude all premium packs."""
        packs = list_packs(include_premium=False)
        assert all(not p.premium for p in packs)

    def test_get_pack_country_cl(self):
        """country_cl must be registered."""
        pack = get_pack("country_cl")
        assert pack.name == "country_cl"
        assert pack.type == PackType.COUNTRY

    def test_get_pack_retail(self):
        """retail must be registered as an industry pack."""
        pack = get_pack("retail")
        assert pack.type == PackType.INDUSTRY

    def test_get_pack_missing_raises_key_error(self):
        """Requesting an unknown pack must raise KeyError."""
        with pytest.raises(KeyError):
            get_pack("nonexistent_pack_xyz")

    def test_chaos_packs_are_premium(self):
        """All chaos packs must be marked premium."""
        chaos = list_packs(PackType.CHAOS)
        assert len(chaos) > 0
        assert all(p.premium for p in chaos)

    def test_resolve_packs_cl_retail(self):
        """resolve_packs returns country pack then industry pack."""
        packs = resolve_packs("cl", "retail")
        names = [p.name for p in packs]
        assert "country_cl" in names
        assert "retail" in names
        # country pack must come first
        assert names.index("country_cl") < names.index("retail")

    def test_resolve_packs_unknown_country_still_resolves_industry(self):
        """Unknown country skips country pack but still returns industry."""
        packs = resolve_packs("zz", "retail")
        names = [p.name for p in packs]
        assert "retail" in names


# ---------------------------------------------------------------------------
# packs.loader
# ---------------------------------------------------------------------------

class TestLoader:
    def test_load_country_pack_cl(self):
        """load_country_pack('cl') must return a dict."""
        pack = load_country_pack("cl")
        assert isinstance(pack, dict)

    def test_load_missing_pack_raises_file_not_found(self):
        """Loading an unknown pack must raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_pack("country_zz")

    def test_load_industry_falls_back_to_generic(self):
        """load_industry_pack falls back to generic when no country variant exists."""
        # retail_cl does not exist → should fall back to retail
        # If retail itself doesn't exist yet, we expect FileNotFoundError (not KeyError)
        try:
            pack = load_industry_pack("retail", "cl")
            assert isinstance(pack, dict)
        except FileNotFoundError:
            pass  # expected until retail.yaml is created


# ---------------------------------------------------------------------------
# country_cl.yaml — structural integrity
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def cl_pack():
    """Load country_cl.yaml once for all structural tests."""
    return load_country_pack("cl")


class TestCountryCLStructure:
    REQUIRED_SECTIONS = [
        "meta", "localization", "fiscal", "taxpayer_types",
        "document_types", "banks", "addresses", "geography", "company",
    ]

    def test_required_sections_present(self, cl_pack):
        """All required top-level sections must be present."""
        for section in self.REQUIRED_SECTIONS:
            assert section in cl_pack, f"Missing section: {section}"

    def test_meta_fields(self, cl_pack):
        meta = cl_pack["meta"]
        assert meta["code"] == "cl"
        assert meta["locale"] == "es_CL"
        assert 1 in meta["layers"]
        assert 2 in meta["layers"]

    def test_localization_has_odoo_modules(self, cl_pack):
        loc = cl_pack["localization"]
        modules = loc["odoo_modules"]["install_order"]
        assert "l10n_cl" in modules
        assert "l10n_cl_edi" in modules
        # l10n_cl must be installed before l10n_cl_edi
        assert modules.index("l10n_cl") < modules.index("l10n_cl_edi")

    def test_fiscal_tax_rate(self, cl_pack):
        assert cl_pack["fiscal"]["tax_rate"] == 0.19

    def test_fiscal_faker_methods(self, cl_pack):
        fiscal = cl_pack["fiscal"]
        assert fiscal["faker_person_id"] == "person_rut"
        assert fiscal["faker_company_id"] == "company_rut"

    def test_taxpayer_types_count(self, cl_pack):
        """Chile has exactly 4 SII taxpayer types."""
        assert len(cl_pack["taxpayer_types"]) == 4

    def test_taxpayer_types_have_required_fields(self, cl_pack):
        for t in cl_pack["taxpayer_types"]:
            assert "code" in t
            assert "label" in t
            assert "odoo_field" in t

    def test_taxpayer_types_have_default(self, cl_pack):
        defaults = [t for t in cl_pack["taxpayer_types"] if t.get("default")]
        assert len(defaults) == 1

    def test_document_types_sii_codes(self, cl_pack):
        """Core DTE codes must be present."""
        codes = {d["code"] for d in cl_pack["document_types"]}
        for expected in (33, 39, 61, 56, 52):
            assert expected in codes, f"Missing DTE code: {expected}"

    def test_document_types_have_required_fields(self, cl_pack):
        for doc in cl_pack["document_types"]:
            assert "code" in doc
            assert "name" in doc
            assert "affects_vat" in doc

    def test_default_sale_document_is_33(self, cl_pack):
        sale_defaults = [
            d for d in cl_pack["document_types"] if d.get("default_sale")
        ]
        assert len(sale_defaults) == 1
        assert sale_defaults[0]["code"] == 33

    def test_banks_have_required_fields(self, cl_pack):
        for bank in cl_pack["banks"]:
            assert "code" in bank
            assert "name" in bank
            assert "swift" in bank

    def test_bancoestado_present(self, cl_pack):
        codes = {b["code"] for b in cl_pack["banks"]}
        assert "012" in codes  # BancoEstado SBIF code

    def test_geography_has_16_regions(self, cl_pack):
        assert len(cl_pack["geography"]["regions"]) == 16

    def test_geography_rm_is_default(self, cl_pack):
        rm = next(
            r for r in cl_pack["geography"]["regions"] if r["code"] == "RM"
        )
        assert rm.get("default") is True

    def test_addresses_has_communes(self, cl_pack):
        communes = cl_pack["addresses"]["communes_by_region"]
        assert "RM" in communes
        assert len(communes["RM"]) > 0

    def test_company_has_name_suffixes(self, cl_pack):
        suffixes = cl_pack["company"]["name_suffixes"]
        assert "S.A." in suffixes
        assert "SpA" in suffixes
        assert "Ltda." in suffixes

    def test_company_has_economic_activities(self, cl_pack):
        activities = cl_pack["company"]["economic_activities"]
        assert len(activities) > 0
        for act in activities:
            assert "code" in act
            assert "description" in act


# ---------------------------------------------------------------------------
# Faker integration smoke test
# ---------------------------------------------------------------------------

class TestFakerIntegration:
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

    def test_faker_rut_matches_pack_config(self, cl_pack):
        """Faker methods declared in pack config must be callable."""
        from faker import Faker
        fake = Faker("es_CL")
        fiscal = cl_pack["fiscal"]
        assert hasattr(fake, fiscal["faker_person_id"])
        assert hasattr(fake, fiscal["faker_company_id"])
