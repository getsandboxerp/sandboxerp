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

:author: Hector Colina / Team360 <hector.colina@team360.cl> | https://team360.cl
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


# ─────────────────────────────────────────
# Spain — NIF (persona física) y CIF (persona jurídica)
# ─────────────────────────────────────────

# Control letter table for NIF — index = number % 23.
_NIF_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"


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


# ─────────────────────────────────────────
# France — SIREN / SIRET / TVA intracommunautaire
# ─────────────────────────────────────────

# SIREN of La Poste — uses a non-standard checksum (sum of all digits
# divisible by 5 instead of Luhn). We never generate this SIREN in
# synthetic data, but the validator must handle it when reading real data.
_FR_LAPOSTE_SIREN = "356000000"

# Length constants — defined as module-level constants to avoid magic numbers.
_FR_SIREN_LEN = 9
_FR_SIRET_LEN = 14  # SIREN (9) + NIC (5)


def _luhn_checksum(digits: list[int]) -> int:
    """Compute the Luhn checksum digit for a sequence of digits.

    The checksum digit is chosen so that appending it to *digits* makes
    the full number pass the Luhn validation (sum divisible by 10).

    :param digits: List of int digits (0–9), most significant first,
        **without** the checksum digit.
    :return: Single checksum digit (0–9).
    """
    total = 0
    for i, d in enumerate(reversed(digits)):
        pos = i + 1  # position from the right in the complete number
        if pos % 2 == 1:  # odd positions (from the right) are doubled
            doubled = d * 2
            total += doubled if doubled < 10 else doubled - 9
        else:
            total += d
    check = (10 - (total % 10)) % 10
    return check


def _fr_siren(rng: random.Random) -> str:
    """Generate a valid French SIREN number.

    Format: 9 digits validated by the Luhn algorithm (e.g. ``404833048``).

    The first 8 digits are random; the 9th (rightmost) is the Luhn
    checksum digit. La Poste's reserved SIREN (``356000000``) is
    excluded from the generation space.

    :param rng: Seeded :class:`random.Random` instance.
    :return: SIREN string (9 digits, no spaces).
    """
    while True:
        base = [rng.randint(0, 9) for _ in range(_FR_SIREN_LEN - 1)]
        check = _luhn_checksum(base)
        siren = "".join(str(d) for d in base) + str(check)
        if siren == _FR_LAPOSTE_SIREN:
            continue  # exclude La Poste's reserved SIREN
        return siren


def _fr_siret(rng: random.Random) -> str:
    """Generate a valid French SIRET number.

    Format: 14 digits = SIREN (9) + NIC (5), validated by the Luhn
    algorithm over all 14 digits (e.g. ``40483304800038``).

    A valid SIRET requires both:
    - The full 14-digit number to pass Luhn.
    - The embedded 9-digit SIREN to pass Luhn (guaranteed here since
      we derive the SIRET from a valid SIREN).

    La Poste establishments (SIREN ``356000000``) use a non-standard
    checksum (sum of digits divisible by 5) — excluded from generation.

    :param rng: Seeded :class:`random.Random` instance.
    :return: SIRET string (14 digits, no spaces).
    """
    siren = _fr_siren(rng)  # always a valid SIREN (9 digits)
    siren_digits = [int(c) for c in siren]
    # Generate 4 free NIC digits; the 5th (checksum) makes the full 14
    # digits pass Luhn.
    nic_base = [rng.randint(0, 9) for _ in range(4)]
    check = _luhn_checksum(siren_digits + nic_base)
    return siren + "".join(str(d) for d in nic_base) + str(check)


def _fr_vat(rng: random.Random) -> str:
    """Generate a valid French TVA intracommunautaire number (without FR prefix).

    Format: 2-digit key + 9-digit SIREN (11 chars total, e.g. ``61775670417``).

    The 2-digit key is derived from the SIREN using the official DGFiP formula:
        key = (12 + 3 x (SIREN mod 97)) mod 97

    This is what Odoo expects in the ``vat`` field for French partners —
    not the SIRET (14 digits) nor the SIREN alone (9 digits).

    :param rng: Seeded :class:`random.Random` instance.
    :return: TVA string without country prefix (e.g. ``61775670417``).
    """
    siren = _fr_siren(rng)
    key = (12 + 3 * (int(siren) % 97)) % 97
    return f"{key:02d}{siren}"


# ─────────────────────────────────────────
# Colombia — NIT (Número de Identificación Tributaria)
# ─────────────────────────────────────────

# Weights for the DIAN mod-11 algorithm, applied left to right
# over the 9 base digits of the NIT (Orden Administrativa 4, 1989).
_CO_NIT_WEIGHTS = [41, 37, 29, 23, 19, 17, 13, 7, 3]


def _co_nit(rng: random.Random) -> str:
    """Generate a valid Colombian NIT with verification digit (without CO prefix).

    Format: 9 digits + hyphen + 1 verification digit (e.g. ``900123456-7``).

    This is the format Odoo expects in the ``vat`` field for Colombian partners
    when the identification type is NIT, as documented in the official Odoo 17
    Colombia localization guide.

    Algorithm (DIAN Orden Administrativa 4, 1989 — mod-11 with prime weights):
    - Multiply each of the 9 base digits (left to right) by the corresponding
      weight from _CO_NIT_WEIGHTS: [41, 37, 29, 23, 19, 17, 13, 7, 3].
    - Sum all products.
    - remainder = sum % 11
    - If remainder == 0 or remainder == 1 → DV = remainder
    - If remainder >= 2 → DV = 11 - remainder

    :param rng: Seeded :class:`random.Random` instance.
    :return: NIT string without country prefix (e.g. ``900123456-7``).
    """
    digits = [rng.randint(0, 9) for _ in range(len(_CO_NIT_WEIGHTS))]
    total = sum(d * w for d, w in zip(digits, _CO_NIT_WEIGHTS))
    remainder = total % 11
    dv = remainder if remainder <= 1 else 11 - remainder
    base = "".join(str(d) for d in digits)
    return f"{base}-{dv}"


# ─────────────────────────────────────────
# Dominican Republic — RNC
# ─────────────────────────────────────────

_DO_RNC_WEIGHTS = (7, 9, 8, 6, 5, 4, 3, 2)


def _do_rnc(rng: random.Random) -> str:
    """Generate a valid Dominican Republic RNC (without country prefix).

    Format: 9 digits, no separators (e.g. ``101850043``). The first digit is
    ``1`` (legal entity), the next seven are random and the last one is the
    DGII check digit.

    The check digit is a weighted mod-11 over the first eight digits::

        weights = (7, 9, 8, 6, 5, 4, 3, 2)
        digit = (10 - (sum(weight * digit) mod 11)) mod 9 + 1

    Individuals in the Dominican Republic use their 11-digit cedula as tax ID.
    The installer calls one generator for every partner, so all generated
    partners receive an RNC.

    :param rng: Seeded :class:`random.Random` instance.
    :return: RNC string (9 digits, no separators).
    """
    body = "1" + "".join(str(rng.randint(0, 9)) for _ in range(7))
    total = sum(w * int(d) for w, d in zip(_DO_RNC_WEIGHTS, body))
    return body + str((10 - total % 11) % 9 + 1)


# ─────────────────────────────────────────
# Registry
# ─────────────────────────────────────────

VAT_GENERATORS: dict[str, callable] = {
    "nl": _nl_btw,
    "pt": _pt_nif,
    "es": _es_nif,
    "fr": _fr_vat,  # TVA intracommunautaire: 2-digit key + 9-digit SIREN
    "co": _co_nit,  # NIT: 9 digits + hyphen + verification digit (DIAN mod-11)
    "do": _do_rnc,  # RNC: 9 digits, DGII mod-11 check digit
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
