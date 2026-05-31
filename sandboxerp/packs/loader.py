"""
Pack loader for SandboxERP.

Discovers and loads YAML-based pack definitions from the filesystem.
Packs live under ``~/.sandboxerp/packs/`` or the built-in ``packs/``
directory shipped with the package.

:author: Hector Colina / Team360 <https://team360.cl>
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

# Built-in packs directory (relative to this file).
BUILTIN_PACKS_DIR = Path(__file__).parent / "builtin"

# User-level packs directory.
USER_PACKS_DIR = Path.home() / ".sandboxerp" / "packs"


def load_pack(name: str) -> dict[str, Any]:
    """Load a pack definition by name.

    Search order:
    1. User packs directory (``~/.sandboxerp/packs/<name>.yaml``).
    2. Built-in packs directory (bundled with the package).

    :param name: Pack name without extension (e.g. ``"cl_retail"``).
    :return: Pack definition as a plain Python dict.
    :raises FileNotFoundError: If no matching pack file is found.
    """
    for directory in (USER_PACKS_DIR, BUILTIN_PACKS_DIR):
        candidate = directory / f"{name}.yaml"
        if candidate.exists():
            return _read_yaml(candidate)

    raise FileNotFoundError(
        f"Pack '{name}' not found. "
        f"Searched: {USER_PACKS_DIR}, {BUILTIN_PACKS_DIR}"
    )


def load_country_pack(country: str) -> dict[str, Any]:
    """Load the country-level pack for *country*.

    :param country: ISO country code (e.g. ``"cl"``).
    :return: Country pack definition dict.
    :raises FileNotFoundError: If no country pack exists for *country*.
    """
    return load_pack(f"country_{country}")


def load_industry_pack(industry: str, country: str) -> dict[str, Any]:
    """Load an industry pack, preferring a country-specific variant.

    Lookup order:
    1. ``<industry>_<country>`` (e.g. ``retail_cl``)
    2. ``<industry>`` (e.g. ``retail``)

    :param industry: Industry name (e.g. ``"retail"``).
    :param country: ISO country code used for the variant lookup.
    :return: Industry pack definition dict.
    :raises FileNotFoundError: If no matching industry pack is found.
    """
    try:
        return load_pack(f"{industry}_{country}")
    except FileNotFoundError:
        return load_pack(industry)


def _read_yaml(path: Path) -> dict[str, Any]:
    """Read and parse a YAML file.

    :param path: Absolute path to the YAML file.
    :return: Parsed content as a dict.
    :raises ValueError: If the file content is not a YAML mapping.
    """
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    if not isinstance(data, dict):
        raise ValueError(f"Pack file must be a YAML mapping: {path}")

    return data
