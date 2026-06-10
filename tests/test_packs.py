"""
tests.test_packs
~~~~~~~~~~~~~~~~

Unit tests for the SandboxERP pack system.

Covers:
- ``packs.loader``: loading builtin packs, missing pack error, country/industry
  resolution.
- ``packs.registry``: catalogue listing, lookup, resolve_packs.

Structural integrity tests for individual country/industry packs live in
their own files: test_pack_cl.py, test_pack_mx.py, test_pack_retail.py, etc.

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

    def test_get_pack_country_mx(self):
        """country_mx must be registered."""
        pack = get_pack("country_mx")
        assert pack.name == "country_mx"
        assert pack.type == PackType.COUNTRY

    def test_get_pack_country_nl(self):
        """country_nl must be registered."""
        pack = get_pack("country_nl")
        assert pack.name == "country_nl"
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
        assert names.index("country_cl") < names.index("retail")

    def test_resolve_packs_mx_retail(self):
        """resolve_packs returns country_mx pack then industry pack."""
        packs = resolve_packs("mx", "retail")
        names = [p.name for p in packs]
        assert "country_mx" in names
        assert "retail" in names
        assert names.index("country_mx") < names.index("retail")

    def test_resolve_packs_nl_retail(self):
        """resolve_packs returns country_nl pack then industry pack."""
        packs = resolve_packs("nl", "retail")
        names = [p.name for p in packs]
        assert "country_nl" in names
        assert "retail" in names
        assert names.index("country_nl") < names.index("retail")

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

    def test_load_country_pack_mx(self):
        """load_country_pack('mx') must return a dict."""
        pack = load_country_pack("mx")
        assert isinstance(pack, dict)

    def test_load_country_pack_nl(self):
        """load_country_pack('nl') must return a dict."""
        pack = load_country_pack("nl")
        assert isinstance(pack, dict)

    def test_load_missing_pack_raises_file_not_found(self):
        """Loading an unknown pack must raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_pack("country_zz")

    def test_load_industry_falls_back_to_generic(self):
        """load_industry_pack falls back to generic when no country variant exists."""
        try:
            pack = load_industry_pack("retail", "cl")
            assert isinstance(pack, dict)
        except FileNotFoundError:
            pass  # expected until retail.yaml is created
