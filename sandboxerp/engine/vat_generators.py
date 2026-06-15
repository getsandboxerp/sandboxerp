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


def _es_nif(rng: random.Random) -> str:
    """Generate a valid Spanish NIF (persona física) without country prefix.

    Format: 8 digits + 1 control letter (e.g. ``12345678Z``).

    Algorithm:
    - number mod 23 → index into _NIF_LETTERS.

    :param rng: Seeded :class:`random.Random` instance.
    :return: NIF string without country prefix (e.g. ``12345678Z``).
    """
    number = rng.randint(10000000, 99999999)
    letter = _NIF_LETTERS[number % 23]
    return f"{number}{letter}"


def _es_cif(rng: random.Random) -> str:
    """Generate a valid Spanish CIF (persona jurídica) without country prefix.

    Format: 1 letter + 7 digits + 1 control character (e.g. ``B12345670``).

    Algorithm:
    - Sum odd-position digits (1-based) directly.
    - Sum even-position digits after doubling (if >= 10, sum its digits).
    - Total sum → control = (10 - (total % 10)) % 10.
    - Control char: letter for org types P Q S W, digit otherwise.

    :param rng: Seeded :class:`random.Random` instance.
    :return: CIF string without country prefix (e.g. ``B12345670``).
    """
    _CIF_LETTERS = "JABCDEFGHI"
    _ORG_TYPES = "ABCDEFGHJNPQRSUVW"
    _LETTER_CONTROL_TYPES = "PQSW"

    org = rng.choice(_ORG_TYPES)
    digits = [rng.randint(0, 9) for _ in range(7)]

    odd_sum = sum(digits[i] for i in range(0, 7, 2))
    even_sum = 0
    for i in range(1, 7, 2):
        d = digits[i] * 2
        even_sum += d if d < 10 else d - 9

    total = odd_sum + even_sum
    control_digit = (10 - (total % 10)) % 10

    if org in _LETTER_CONTROL_TYPES:
        control = _CIF_LETTERS[control_digit]
    else:
        control = str(control_digit)

    return f"{org}{''.join(str(d) for d in digits)}{control}"


VAT_GENERATORS: dict[str, callable] = {
    "nl": _nl_btw,
    "pt": _pt_nif,
    "es": _es_nif,
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


# ─────────────────────────────────────────
# Spain — NIF (persona física) y CIF (persona jurídica)
# ─────────────────────────────────────────

_NIF_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"


