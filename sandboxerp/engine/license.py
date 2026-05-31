"""
License engine for SandboxERP.

Validates pack licenses and manages feature gating for premium tiers.
The CLI core is always free; premium packs (Chaos, Snapshot/Restore)
require a valid license key verified against the licensing server.

:author: Hector Colina / Team360 <https://team360.cl>
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

import httpx

LICENSE_API_URL = "https://api.sandboxerp.team360.cl/v1/license/verify"
REQUEST_TIMEOUT = 5  # seconds


class Tier(str, Enum):
    """Available SandboxERP tiers.

    :cvar FREE: Open-source core. No key required.
    :cvar PREMIUM: Paid tier. Required for Chaos Packs, Snapshot/Restore.
    """

    FREE = "free"
    PREMIUM = "premium"


def verify_license(key: str) -> Tier:
    """Verify a license key against the SandboxERP licensing server.

    Makes a single POST request to the licensing API. On network failure
    or any non-200 response the function returns :attr:`Tier.FREE` so
    that the CLI remains usable offline for free-tier features.

    :param key: License key string supplied by the user.
    :return: The :class:`Tier` granted by the key, or ``FREE`` on error.
    """
    try:
        response = httpx.post(
            LICENSE_API_URL,
            json={"key": key},
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code == 200:
            data = response.json()
            return Tier(data.get("tier", Tier.FREE))
    except (httpx.RequestError, ValueError):
        pass

    return Tier.FREE


def is_premium(key: Optional[str]) -> bool:
    """Return ``True`` if *key* grants premium access.

    Convenience wrapper around :func:`verify_license`.

    :param key: License key string, or ``None`` for anonymous use.
    :return: ``True`` if the key resolves to :attr:`Tier.PREMIUM`.
    """
    if not key:
        return False
    return verify_license(key) == Tier.PREMIUM


def require_premium(key: Optional[str], feature: str) -> None:
    """Assert that the caller has a valid premium license.

    :param key: License key string, or ``None``.
    :param feature: Human-readable feature name shown in the error message.
    :raises PermissionError: If *key* does not grant premium access.
    """
    if not is_premium(key):
        raise PermissionError(
            f"'{feature}' requires a SandboxERP Premium license. "
            "Visit https://sandboxerp.team360.cl to upgrade."
        )
