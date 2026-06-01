"""
tests.test_seasonality
~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for sandboxerp.engine.seasonality.

:author: Hector Colina / Team360 <https://team360.cl>
"""

import pytest
from sandboxerp.engine.seasonality import (
    INDUSTRY_PROFILES,
    SeasonalityProfile,
    distribute_volume,
    get_monthly_weight,
    get_profile,
)


# ─────────────────────────────────────────
# SeasonalityProfile
# ─────────────────────────────────────────


class TestSeasonalityProfile:
    def test_valid_profile(self):
        p = SeasonalityProfile(industry="test", weights=tuple([1.0] * 12))
        assert p.industry == "test"
        assert len(p.weights) == 12

    def test_rejects_wrong_length(self):
        with pytest.raises(ValueError, match="12 weights"):
            SeasonalityProfile(industry="bad", weights=tuple([1.0] * 11))

    def test_weight_for_january(self):
        weights = tuple(float(i + 1) for i in range(12))
        p = SeasonalityProfile(industry="x", weights=weights)
        assert p.weight_for(1) == 1.0
        assert p.weight_for(12) == 12.0

    def test_weight_for_invalid_month(self):
        p = SeasonalityProfile(industry="x", weights=tuple([1.0] * 12))
        with pytest.raises(ValueError, match="month must be between"):
            p.weight_for(0)
        with pytest.raises(ValueError, match="month must be between"):
            p.weight_for(13)

    def test_scale_rounds_to_int(self):
        weights = tuple([1.0] * 12)
        p = SeasonalityProfile(industry="x", weights=weights)
        assert p.scale(50, 6) == 50

    def test_scale_minimum_one(self):
        weights = tuple([0.0] * 12)
        p = SeasonalityProfile(industry="x", weights=weights)
        assert p.scale(50, 1) == 1

    def test_scale_with_high_weight(self):
        weights = tuple([2.0] * 12)
        p = SeasonalityProfile(industry="x", weights=weights)
        assert p.scale(50, 12) == 100


# ─────────────────────────────────────────
# get_profile
# ─────────────────────────────────────────


class TestGetProfile:
    def test_known_industries(self):
        for industry in ("retail", "accounting", "manufacturing", "services"):
            p = get_profile(industry)
            assert isinstance(p, SeasonalityProfile)
            assert p.industry == industry
            assert len(p.weights) == 12

    def test_case_insensitive(self):
        p = get_profile("RETAIL")
        assert p.industry == "retail"

    def test_unknown_industry_returns_flat(self):
        p = get_profile("nonexistent_industry_xyz")
        assert all(w == 1.0 for w in p.weights)

    def test_all_weights_positive(self):
        for industry in INDUSTRY_PROFILES:
            p = get_profile(industry)
            assert all(w > 0 for w in p.weights), (
                f"Industry '{industry}' has a non-positive weight"
            )


# ─────────────────────────────────────────
# get_monthly_weight
# ─────────────────────────────────────────


class TestGetMonthlyWeight:
    def test_retail_december_is_peak(self):
        dec = get_monthly_weight("retail", month=12)
        feb = get_monthly_weight("retail", month=2)
        assert dec > feb

    def test_retail_november_high(self):
        nov = get_monthly_weight("retail", month=11)
        assert nov > 1.0

    def test_accounting_april_is_peak(self):
        apr = get_monthly_weight("accounting", month=4)
        aug = get_monthly_weight("accounting", month=8)
        assert apr > aug

    def test_returns_float(self):
        w = get_monthly_weight("retail", month=6)
        assert isinstance(w, float)

    def test_invalid_month_raises(self):
        with pytest.raises(ValueError):
            get_monthly_weight("retail", month=13)


# ─────────────────────────────────────────
# distribute_volume
# ─────────────────────────────────────────


class TestDistributeVolume:
    def test_returns_12_months(self):
        dist = distribute_volume("retail", annual_total=600)
        assert set(dist.keys()) == set(range(1, 13))

    def test_sum_approximates_total(self):
        total = 600
        dist = distribute_volume("retail", annual_total=total)
        # Allow ±12 rounding slack (one per month)
        assert abs(sum(dist.values()) - total) <= 12

    def test_subset_of_months(self):
        dist = distribute_volume("retail", annual_total=300, months=[11, 12])
        assert set(dist.keys()) == {11, 12}
        assert abs(sum(dist.values()) - 300) <= 2

    def test_all_counts_positive(self):
        dist = distribute_volume("manufacturing", annual_total=120)
        assert all(v >= 1 for v in dist.values())

    def test_retail_december_more_than_february(self):
        dist = distribute_volume("retail", annual_total=1200)
        assert dist[12] > dist[2]

    def test_single_month(self):
        dist = distribute_volume("services", annual_total=100, months=[3])
        assert dist[3] == 100

    def test_flat_profile_distributes_evenly(self):
        dist = distribute_volume("unknown_flat", annual_total=120)
        # All months should be equal (flat profile = 1.0 everywhere)
        values = list(dist.values())
        assert max(values) - min(values) <= 1  # rounding tolerance
