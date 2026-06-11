"""
sandboxerp.engine.vat_generators
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Country-specific VAT number generators for locales where Faker does not
provide a valid format accepted by Odoo's VAT validation.

Each generator is a callable that accepts a :class:`random.Random` instance
and returns a valid VAT string (without country prefix — the prefix is
applied by the installer from ``partner_fields.vat_prefix``).

Registry
--------
VAT_GENERATORS maps a country code (lowercase) to its generator function.
The installer looks up this registry when ``fiscal.vat_format`` is set to
the special value ``"__generator__"`` in a country pack.

:author: Hector Colina / Team360 <https://team360.cl>
"""

from __future__ import annotations

import random


# ─────────────────────────────────────────
# Netherlands — BTW-nummer
# ─────────────────────────────────────────


def _nl_btw(rng: random.Random) -> str:
    """Generate a valid Dutch BTW-nummer (without NL prefix).

    Format: 9 digits + B + 2 digits (e.g. ``104332189B12``).

    The 9-digit number uses a modulo-11 checksum:
    - weights [9, 8, 7, 6, 5, 4, 3, 2] applied to the first 8 digits.
    - check digit = sum % 11.
    - If check digit is 10 (invalid), regenerate.

    The 2-digit suffix after ``B`` is free (01–99).

    :param rng: Seeded :class:`random.Random` instance.
    :return: BTW number string without country prefix (e.g. ``104332189B12``).
    """
    while True:
        digits = [rng.randint(0, 9) for _ in range(8)]
        weights = [9, 8, 7, 6, 5, 4, 3, 2]
        total = sum(d * w for d, w in zip(digits, weights))
        check = total % 11
        if check == 10:
            continue  # invalid — retry
        digits.append(check)
        number = "".join(str(d) for d in digits)
        suffix = str(rng.randint(1, 99)).zfill(2)
        return f"{number}B{suffix}"


# ─────────────────────────────────────────
# Registry
# ─────────────────────────────────────────

# ─────────────────────────────────────────
# Portugal — NIF (Número de Identificação Fiscal)
# ─────────────────────────────────────────


def _pt_nif(rng: random.Random, is_company: bool = False) -> str:
    """Generate a valid Portuguese NIF without country prefix.

    Format: 9 digits (e.g. ``123456789``).

    Algorithm (modulo 11):
    - Weights [9, 8, 7, 6, 5, 4, 3, 2] applied to the first 8 digits.
    - remainder = sum % 11
    - check digit = 0 if remainder <= 1, else 11 - remainder.
    - First digit: 1 or 2 for natural persons, 5 for legal entities.

    :param rng: Seeded :class:`random.Random` instance.
    :param is_company: When ``True``, first digit is 5 (legal entity).
    :return: NIF string without country prefix (e.g. ``123456789``).
    """
    first = 5 if is_company else rng.choice([1, 2])
    weights = [9, 8, 7, 6, 5, 4, 3, 2]
    while True:
        digits = [first] + [rng.randint(0, 9) for _ in range(7)]
        total = sum(d * w for d, w in zip(digits, weights))
        remainder = total % 11
        check = 0 if remainder <= 1 else 11 - remainder
        if check > 9:
            continue  # invalid check digit — retry
        digits.append(check)
        return "".join(str(d) for d in digits)


VAT_GENERATORS: dict[str, callable] = {
    "nl": _nl_btw,
    "pt": _pt_nif,
}


def generate_vat(country_code: str, rng: random.Random) -> str | None:
    """Generate a valid VAT number for the given country.

    :param country_code: Lowercase ISO country code (e.g. ``"nl"``).
    :param rng: Seeded :class:`random.Random` instance.
    :return: VAT string without country prefix, or ``None`` if no generator
        is registered for this country.
    """
    generator = VAT_GENERATORS.get(country_code.lower())
    if generator is None:
        return None
    return generator(rng)
