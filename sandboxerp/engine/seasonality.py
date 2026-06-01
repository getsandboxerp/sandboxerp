"""
sandboxerp.engine.seasonality
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Seasonality Engine for SandboxERP — Layer 6 complement.

Provides monthly volume weights per industry so the synthetic dataset
reflects realistic seasonal patterns rather than a flat distribution
across the year.

The engine is intentionally simple: each industry has a profile of 12
monthly weights (Jan=1 … Dec=12).  A weight of ``1.0`` means average
volume; ``2.0`` means double; ``0.5`` means half.

Typical use::

    from sandboxerp.engine.seasonality import get_monthly_weight, SeasonalityProfile

    # How many sale orders to generate for March in retail?
    base = 50
    count = round(base * get_monthly_weight("retail", month=3))

Adding a new industry profile
------------------------------
Add an entry to :data:`INDUSTRY_PROFILES` following the same structure.
The weights do **not** need to sum to 12; they are relative multipliers.

:author: Hector Colina / Team360 <https://team360.cl>
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# ─────────────────────────────────────────
# Seasonal profiles
# ─────────────────────────────────────────

#: Monthly weight tables per industry.
#: Index 0 = January, index 11 = December.
#: Weight 1.0 = average month for that industry.
INDUSTRY_PROFILES: dict[str, list[float]] = {
    # ── Retail ──────────────────────────────────────────────────────
    # Peak: Nov (CyberDay LATAM), Dec (Christmas).
    # Secondary peak: May (Mother's Day), Sep (Fiestas Patrias CL).
    # Valley: Feb–Mar (post-holiday fatigue).
    "retail": [
        0.70,  # Jan — post-holiday drop
        0.60,  # Feb — valley
        0.65,  # Mar — slow recovery
        0.80,  # Apr — pre-winter
        1.10,  # May — Mother's Day
        0.90,  # Jun — mid-year
        0.85,  # Jul — winter sales
        0.90,  # Aug — back to school
        1.20,  # Sep — Fiestas Patrias (CL) / Independence Day (MX)
        1.00,  # Oct — normal
        1.60,  # Nov — CyberDay LATAM / Black Friday
        1.70,  # Dec — Christmas / end-of-year
    ],
    # ── Accounting / Professional Services ──────────────────────────
    # Peak: Mar–Apr (annual tax closing), Jul (mid-year close), Dec.
    # Valley: Jan (post-holiday), Aug–Sep (summer southern hemisphere).
    "accounting": [
        0.70,  # Jan — low activity, holidays
        0.90,  # Feb — ramping up
        1.40,  # Mar — annual tax / audit season
        1.50,  # Apr — tax deadline peak (Chile: April 30)
        1.10,  # May — post-tax normalisation
        0.90,  # Jun — mid-year preparation
        1.30,  # Jul — mid-year close
        0.80,  # Aug — southern hemisphere summer (business slow)
        0.85,  # Sep — spring recovery
        1.00,  # Oct — normal
        1.10,  # Nov — year-end planning
        1.20,  # Dec — year-end close
    ],
    # ── Manufacturing ────────────────────────────────────────────────
    # Relatively flat — production plans smooth demand.
    # Slight dip in Jan (holidays) and Jul (plant maintenance).
    # Peak: Oct–Nov (pre-holiday inventory build).
    "manufacturing": [
        0.75,  # Jan — holiday shutdown
        0.90,  # Feb — ramp-up
        1.05,  # Mar — normal
        1.05,  # Apr — normal
        1.00,  # May — normal
        0.95,  # Jun — pre-maintenance
        0.80,  # Jul — plant maintenance / winter break
        0.95,  # Aug — back online
        1.00,  # Sep — normal
        1.15,  # Oct — pre-holiday inventory build
        1.20,  # Nov — inventory peak
        0.85,  # Dec — holiday slowdown
    ],
    # ── Services (generic) ───────────────────────────────────────────
    # Knowledge / consulting services. Follows corporate calendar.
    # Peak: Q1 (new budgets), Q3 (mid-year projects).
    # Valley: Jan, Jul–Aug (vacations).
    "services": [
        0.70,  # Jan — low (vacations)
        1.00,  # Feb — new-year projects kick off
        1.20,  # Mar — Q1 peak
        1.15,  # Apr — Q1 close
        1.00,  # May — normal
        0.90,  # Jun — mid-year lull
        0.75,  # Jul — vacations
        0.80,  # Aug — late summer
        1.10,  # Sep — Q3 push
        1.15,  # Oct — Q3/Q4 transition
        1.10,  # Nov — year-end push
        0.75,  # Dec — holiday slowdown
    ],
}

#: Fallback profile used for unknown industries.
_DEFAULT_PROFILE: list[float] = [1.0] * 12


# ─────────────────────────────────────────
# Public API
# ─────────────────────────────────────────


@dataclass(frozen=True)
class SeasonalityProfile:
    """Immutable seasonality profile for a single industry.

    :param industry: Industry name (e.g. ``"retail"``).
    :param weights: Sequence of 12 monthly multipliers (Jan … Dec).
    """

    industry: str
    weights: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.weights) != 12:
            raise ValueError(
                f"SeasonalityProfile requires exactly 12 weights, "
                f"got {len(self.weights)}."
            )

    def weight_for(self, month: int) -> float:
        """Return the weight for *month* (1 = January … 12 = December).

        :param month: Calendar month number.
        :return: Multiplicative weight for that month.
        :raises ValueError: If *month* is outside 1–12.
        """
        if not 1 <= month <= 12:
            raise ValueError(f"month must be between 1 and 12, got {month}.")
        return self.weights[month - 1]

    def scale(self, base: int, month: int) -> int:
        """Return *base* scaled by the weight for *month*, rounded to int.

        :param base: Base transaction count (e.g. average monthly volume).
        :param month: Calendar month number (1–12).
        :return: Adjusted count, minimum 1.
        """
        return max(1, round(base * self.weight_for(month)))


def get_profile(industry: str) -> SeasonalityProfile:
    """Return the :class:`SeasonalityProfile` for *industry*.

    Falls back to a flat ``1.0`` profile for unknown industries rather
    than raising an error, so new packs work without requiring a
    seasonality entry.

    :param industry: Industry name (case-insensitive).
    :return: :class:`SeasonalityProfile` for the requested industry.
    """
    key = industry.lower()
    raw = INDUSTRY_PROFILES.get(key, _DEFAULT_PROFILE)
    return SeasonalityProfile(industry=key, weights=tuple(raw))


def get_monthly_weight(industry: str, *, month: int) -> float:
    """Return the volume multiplier for *industry* in *month*.

    Convenience wrapper around :func:`get_profile`.

    :param industry: Industry name.
    :param month: Calendar month (1 = January … 12 = December).
    :return: Float multiplier (e.g. ``1.7`` for December retail).
    """
    return get_profile(industry).weight_for(month)


def distribute_volume(
    industry: str,
    *,
    annual_total: int,
    months: Optional[list[int]] = None,
) -> dict[int, int]:
    """Distribute *annual_total* transactions across months proportionally.

    :param industry: Industry name.
    :param annual_total: Total number of transactions for the year.
    :param months: Subset of months to distribute across (default: all 12).
    :return: Dict mapping month number → transaction count.
        Counts sum to approximately *annual_total* (rounding may differ
        by ±1 per month).
    """
    if months is None:
        months = list(range(1, 13))

    profile = get_profile(industry)
    weights = [profile.weight_for(m) for m in months]
    total_weight = sum(weights)

    distribution: dict[int, int] = {}
    allocated = 0

    for i, month in enumerate(months):
        if i == len(months) - 1:
            # Last month gets the remainder to avoid rounding drift.
            distribution[month] = max(1, annual_total - allocated)
        else:
            count = max(1, round(annual_total * weights[i] / total_weight))
            distribution[month] = count
            allocated += count

    return distribution
