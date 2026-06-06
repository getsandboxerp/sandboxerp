"""
sandboxerp.engine.odoo
~~~~~~~~~~~~~~~~~~~~~~

Odoo XML-RPC client for SandboxERP.

Provides a thin, typed wrapper around Odoo's two XML-RPC endpoints:

- ``/xmlrpc/2/common``  — authentication and version info.
- ``/xmlrpc/2/object``  — model operations (create, read, write, search…).

All public methods raise :class:`OdooError` on failure so callers can
handle errors uniformly without inspecting raw XML-RPC faults.

Examples::

    client = OdooClient.connect(host="127.0.0.1", port=8069)
    uid = client.authenticate("sandbox", "admin", "admin")
    partner_id = client.create("res.partner", {"name": "Acme SpA"})

:author: Hector Colina / Team360 <https://team360.cl>
"""

from __future__ import annotations

import xmlrpc.client
from dataclasses import dataclass, field
from typing import Any


def _to_list(obj: Any) -> Any:
    """Recursively convert tuples to lists for Odoo 17 XML-RPC compatibility.

    Odoo 17 domain_combine_anies requires list items, not tuples.

    :param obj: Any Python object.
    :return: Same structure with all tuples converted to lists.
    """
    if isinstance(obj, (list, tuple)):
        return [_to_list(i) for i in obj]
    return obj


# ─────────────────────────────────────────
# Exceptions
# ─────────────────────────────────────────


class OdooError(RuntimeError):
    """Raised when an Odoo XML-RPC call fails.

    :param message: Human-readable description of the failure.
    :param fault: Optional underlying :class:`xmlrpc.client.Fault`, if any.
    """

    def __init__(self, message: str, fault: xmlrpc.client.Fault | None = None):
        super().__init__(message)
        self.fault = fault


# ─────────────────────────────────────────
# Client
# ─────────────────────────────────────────


@dataclass
class OdooClient:
    """XML-RPC client connected to a running Odoo instance.

    Do not instantiate directly — use :meth:`connect` or
    :meth:`connect_and_authenticate`.

    :param host: Odoo host (default ``127.0.0.1``).
    :param port: Odoo HTTP port (default ``8069``).
    :param db: Database name.
    :param uid: Authenticated user ID (0 if not yet authenticated).
    :param password: Odoo password used for XML-RPC calls (set by :meth:`authenticate`).
    :param _common: Proxy for the ``/xmlrpc/2/common`` endpoint.
    :param _models: Proxy for the ``/xmlrpc/2/object`` endpoint.
    """

    host: str
    port: int
    db: str
    uid: int = 0
    password: str = "admin"
    _common: Any = field(default=None, repr=False)
    _models: Any = field(default=None, repr=False)

    # ------------------------------------------------------------------
    # Constructors
    # ------------------------------------------------------------------

    @classmethod
    def connect(
        cls,
        host: str = "127.0.0.1",
        port: int = 8069,
        db: str = "sandbox",
    ) -> "OdooClient":
        """Create a client and open XML-RPC proxies (no authentication yet).

        :param host: Odoo host.
        :param port: Odoo HTTP port.
        :param db: Target database name.
        :return: Unauthenticated :class:`OdooClient`.
        :raises OdooError: If the XML-RPC endpoints are unreachable.
        """
        base_url = f"http://{host}:{port}"
        try:
            common = xmlrpc.client.ServerProxy(f"{base_url}/xmlrpc/2/common", allow_none=True)
            models = xmlrpc.client.ServerProxy(f"{base_url}/xmlrpc/2/object", allow_none=True)
            # Verify connectivity
            common.version()
        except Exception as exc:
            raise OdooError(
                f"Cannot reach Odoo at {base_url}. Is the instance running?"
            ) from exc

        return cls(host=host, port=port, db=db, _common=common, _models=models)

    @classmethod
    def connect_and_authenticate(
        cls,
        host: str = "127.0.0.1",
        port: int = 8069,
        db: str = "sandbox",
        user: str = "admin",
        password: str = "admin",
    ) -> "OdooClient":
        """Connect and authenticate in a single call.

        :param host: Odoo host.
        :param port: Odoo HTTP port.
        :param db: Target database name.
        :param user: Odoo login (default ``admin``).
        :param password: Odoo password (default ``admin``).
        :return: Authenticated :class:`OdooClient`.
        :raises OdooError: On connection or authentication failure.
        """
        client = cls.connect(host=host, port=port, db=db)
        client.authenticate(user=user, password=password)
        return client

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def authenticate(self, user: str = "admin", password: str = "admin") -> int:
        """Authenticate against the Odoo database.

        Sets :attr:`uid` and :attr:`password` on success.

        :param user: Odoo login.
        :param password: Odoo password.
        :return: Authenticated user ID.
        :raises OdooError: If credentials are invalid.
        """
        try:
            uid = self._common.authenticate(self.db, user, password, {})
        except xmlrpc.client.Fault as exc:
            raise OdooError("Authentication failed.", fault=exc) from exc

        if not uid:
            raise OdooError(
                f"Authentication failed for user '{user}' on database '{self.db}'."
            )

        self.uid = uid
        self.password = password
        return uid

    # ------------------------------------------------------------------
    # Version / health
    # ------------------------------------------------------------------

    def version(self) -> dict[str, Any]:
        """Return Odoo server version info.

        :return: Dict with keys like ``server_version``, ``server_serie``.
        :raises OdooError: On XML-RPC failure.
        """
        try:
            return self._common.version()
        except xmlrpc.client.Fault as exc:
            raise OdooError("Could not retrieve Odoo version.", fault=exc) from exc

    def is_ready(self) -> bool:
        """Return ``True`` if Odoo responds to a version ping.

        :return: ``True`` if the server is reachable and healthy.
        """
        try:
            self._common.version()
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Generic model operations
    # ------------------------------------------------------------------

    def execute(
        self,
        model: str,
        method: str,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Call any model method via ``execute_kw``.

        :param model: Odoo model technical name (e.g. ``res.partner``).
        :param method: Method name (e.g. ``create``, ``search``, ``write``).
        :param args: Positional arguments forwarded to the method.
        :param kwargs: Keyword arguments forwarded as the options dict.
        :return: Raw return value from Odoo.
        :raises OdooError: If the call fails or the client is not authenticated.
        """
        self._require_auth()
        try:
            return self._models.execute_kw(
                self.db, self.uid, self.password, model, method, list(args), kwargs
            )
        except xmlrpc.client.Fault as exc:
            raise OdooError(
                f"execute_kw({model}.{method}) failed: {exc.faultString}",
                fault=exc,
            ) from exc

    def create(self, model: str, values: dict[str, Any]) -> int:
        """Create a single record and return its ID.

        :param model: Odoo model technical name.
        :param values: Field values for the new record.
        :return: ID of the created record.
        :raises OdooError: On failure.
        """
        return self.execute(model, "create", values)

    def create_many(self, model: str, records: list[dict[str, Any]]) -> list[int]:
        """Create multiple records in a single call.

        :param model: Odoo model technical name.
        :param records: List of field-value dicts.
        :return: List of created record IDs.
        :raises OdooError: On failure.
        """
        return self.execute(model, "create", records)

    def search(
        self,
        model: str,
        domain: list,
        *,
        limit: int = 0,
        offset: int = 0,
        order: str = "",
        context: dict[str, Any] | None = None,
    ) -> list[int]:
        """Search records and return their IDs.

        :param model: Odoo model technical name.
        :param domain: Odoo domain expression.
        :param limit: Maximum number of records (0 = no limit).
        :param offset: Number of records to skip.
        :param order: Sort expression (e.g. ``"name asc"``).
        :param context: Optional Odoo context dict (e.g. ``{"active_test": False}``).
        :return: List of matching record IDs.
        :raises OdooError: On failure.
        """
        kwargs: dict[str, Any] = {}
        if limit:
            kwargs["limit"] = limit
        if offset:
            kwargs["offset"] = offset
        if order:
            kwargs["order"] = order
        if context:
            kwargs["context"] = context
        return self.execute(model, "search", _to_list(domain), **kwargs)

    def search_read(
        self,
        model: str,
        domain: list,
        fields: list[str],
        *,
        limit: int = 0,
        context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Search records and return field values in one call.

        :param model: Odoo model technical name.
        :param domain: Odoo domain expression.
        :param fields: List of field names to return.
        :param limit: Maximum number of records (0 = no limit).
        :param context: Optional Odoo context dict (e.g. ``{"active_test": False}``).
        :return: List of dicts with requested field values.
        :raises OdooError: On failure.
        """
        kwargs: dict[str, Any] = {"fields": fields}
        if limit:
            kwargs["limit"] = limit
        if context:
            kwargs["context"] = context
        return self.execute(model, "search_read", _to_list(domain), **kwargs)

    def read(self, model: str, ids: list[int], fields: list[str]) -> list[dict]:
        """Read specific fields from records by ID.

        :param model: Odoo model technical name.
        :param ids: List of record IDs.
        :param fields: List of field names to return.
        :return: List of dicts with requested field values.
        :raises OdooError: On failure.
        """
        return self.execute(model, "read", [ids], fields=fields)

    def write(self, model: str, ids: list[int], values: dict[str, Any]) -> bool:
        """Update records by ID.

        :param model: Odoo model technical name.
        :param ids: List of record IDs to update.
        :param values: Field values to set.
        :return: ``True`` on success.
        :raises OdooError: On failure.
        """
        return self.execute(model, "write", ids, values)

    def unlink(self, model: str, ids: list[int]) -> bool:
        """Delete records by ID.

        :param model: Odoo model technical name.
        :param ids: List of record IDs to delete.
        :return: ``True`` on success.
        :raises OdooError: On failure.
        """
        return self.execute(model, "unlink", [ids])

    # ------------------------------------------------------------------
    # Module management
    # ------------------------------------------------------------------

    def install_module(self, module_name: str) -> None:
        """Install an Odoo module if not already installed.

        Calls ``button_immediate_install`` on the module record.

        :param module_name: Technical name of the module (e.g. ``l10n_cl``).
        :raises OdooError: If the module is not found or installation fails.
        """
        ids = self.search(
            "ir.module.module",
            [("name", "=", module_name), ("state", "!=", "installed")],
        )
        if not ids:
            return  # already installed
        self.execute("ir.module.module", "button_immediate_install", ids)

    def module_is_installed(self, module_name: str) -> bool:
        """Check whether a module is currently installed.

        :param module_name: Technical name of the module.
        :return: ``True`` if the module state is ``installed``.
        """
        ids = self.search(
            "ir.module.module",
            [("name", "=", module_name), ("state", "=", "installed")],
        )
        return len(ids) > 0

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def get_ref(self, xml_id: str) -> int:
        """Resolve an XML external ID to a database record ID.

        :param xml_id: External ID in ``module.name`` format.
        :return: Database record ID.
        :raises OdooError: If the XML ID is not found.
        """
        self._require_auth()
        try:
            result = self._models.execute_kw(
                self.db, self.uid, self.password,
                "ir.model.data", "xmlid_to_res_id",
                [xml_id], {}
            )
        except xmlrpc.client.Fault as exc:
            raise OdooError(f"XML ID not found: {xml_id}", fault=exc) from exc
        if not result:
            raise OdooError(f"XML ID not found: {xml_id}")
        return result

    def find_or_create(
        self,
        model: str,
        domain: list,
        values: dict[str, Any],
    ) -> int:
        """Return the ID of a matching record, or create it if not found.

        :param model: Odoo model technical name.
        :param domain: Search domain to check for existing record.
        :param values: Values used for creation if no record is found.
        :return: ID of the existing or newly created record.
        :raises OdooError: On failure.
        """
        ids = self.search(model, domain, limit=1)
        if ids:
            return ids[0]
        return self.create(model, values)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _require_auth(self) -> None:
        """Assert the client is authenticated.

        :raises OdooError: If :attr:`uid` is 0 (not authenticated).
        """
        if not self.uid:
            raise OdooError(
                "Client is not authenticated. Call authenticate() first."
            )
