"""
tests.test_odoo
~~~~~~~~~~~~~~~

Unit tests for the SandboxERP Odoo XML-RPC client.

All XML-RPC calls are mocked — no real Odoo instance is required.

:author: Hector Colina / Team360 <https://team360.cl>
"""

from __future__ import annotations

import xmlrpc.client
from unittest.mock import MagicMock, patch

import pytest

from sandboxerp.engine.odoo import OdooClient, OdooError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(uid: int = 1) -> OdooClient:
    """Return a pre-authenticated OdooClient with mocked proxies."""
    client = OdooClient(
        host="127.0.0.1",
        port=8069,
        db="sandbox",
        uid=uid,
        _common=MagicMock(),
        _models=MagicMock(),
    )
    return client


# ---------------------------------------------------------------------------
# OdooClient.connect
# ---------------------------------------------------------------------------

class TestConnect:
    def test_connect_returns_client(self):
        with patch("xmlrpc.client.ServerProxy") as mock_proxy:
            mock_proxy.return_value.version.return_value = {"server_version": "17.0"}
            client = OdooClient.connect()
        assert isinstance(client, OdooClient)

    def test_connect_raises_on_unreachable(self):
        with patch("xmlrpc.client.ServerProxy") as mock_proxy:
            mock_proxy.return_value.version.side_effect = ConnectionRefusedError
            with pytest.raises(OdooError):
                OdooClient.connect()

    def test_connect_sets_host_and_port(self):
        with patch("xmlrpc.client.ServerProxy") as mock_proxy:
            mock_proxy.return_value.version.return_value = {}
            client = OdooClient.connect(host="10.0.0.1", port=8888)
        assert client.host == "10.0.0.1"
        assert client.port == 8888


# ---------------------------------------------------------------------------
# OdooClient.authenticate
# ---------------------------------------------------------------------------

class TestAuthenticate:
    def test_authenticate_sets_uid(self):
        client = _make_client(uid=0)
        client._common.authenticate.return_value = 5
        uid = client.authenticate("admin", "admin")
        assert uid == 5
        assert client.uid == 5

    def test_authenticate_raises_on_invalid_credentials(self):
        client = _make_client(uid=0)
        client._common.authenticate.return_value = False
        with pytest.raises(OdooError):
            client.authenticate("wrong", "creds")

    def test_authenticate_raises_on_fault(self):
        client = _make_client(uid=0)
        client._common.authenticate.side_effect = xmlrpc.client.Fault(1, "error")
        with pytest.raises(OdooError):
            client.authenticate()


# ---------------------------------------------------------------------------
# OdooClient.version / is_ready
# ---------------------------------------------------------------------------

class TestVersionAndHealth:
    def test_version_returns_dict(self):
        client = _make_client()
        client._common.version.return_value = {"server_version": "17.0"}
        result = client.version()
        assert result["server_version"] == "17.0"

    def test_is_ready_returns_true(self):
        client = _make_client()
        client._common.version.return_value = {}
        assert client.is_ready() is True

    def test_is_ready_returns_false_on_error(self):
        client = _make_client()
        client._common.version.side_effect = ConnectionRefusedError
        assert client.is_ready() is False


# ---------------------------------------------------------------------------
# OdooClient.execute
# ---------------------------------------------------------------------------

class TestExecute:
    def test_execute_calls_execute_kw(self):
        client = _make_client()
        client._models.execute_kw.return_value = [1, 2, 3]
        result = client.execute("res.partner", "search", [[]])
        assert result == [1, 2, 3]
        client._models.execute_kw.assert_called_once()

    def test_execute_raises_odoo_error_on_fault(self):
        client = _make_client()
        client._models.execute_kw.side_effect = xmlrpc.client.Fault(2, "boom")
        with pytest.raises(OdooError):
            client.execute("res.partner", "search", [[]])

    def test_execute_raises_if_not_authenticated(self):
        client = _make_client(uid=0)
        with pytest.raises(OdooError, match="not authenticated"):
            client.execute("res.partner", "search", [[]])


# ---------------------------------------------------------------------------
# OdooClient.create
# ---------------------------------------------------------------------------

class TestCreate:
    def test_create_returns_id(self):
        client = _make_client()
        client._models.execute_kw.return_value = 42
        result = client.create("res.partner", {"name": "Acme"})
        assert result == 42

    def test_create_many_returns_ids(self):
        client = _make_client()
        client._models.execute_kw.return_value = [10, 11, 12]
        result = client.create_many("res.partner", [{"name": "A"}, {"name": "B"}, {"name": "C"}])
        assert result == [10, 11, 12]


# ---------------------------------------------------------------------------
# OdooClient.search / search_read / read
# ---------------------------------------------------------------------------

class TestSearch:
    def test_search_returns_ids(self):
        client = _make_client()
        client._models.execute_kw.return_value = [1, 2]
        result = client.search("res.partner", [("name", "=", "Acme")])
        assert result == [1, 2]

    def test_search_read_returns_records(self):
        client = _make_client()
        client._models.execute_kw.return_value = [{"id": 1, "name": "Acme"}]
        result = client.search_read("res.partner", [], ["name"])
        assert result[0]["name"] == "Acme"

    def test_read_returns_field_values(self):
        client = _make_client()
        client._models.execute_kw.return_value = [{"id": 1, "name": "Acme"}]
        result = client.read("res.partner", [1], ["name"])
        assert result[0]["id"] == 1


# ---------------------------------------------------------------------------
# OdooClient.write / unlink
# ---------------------------------------------------------------------------

class TestWriteUnlink:
    def test_write_returns_true(self):
        client = _make_client()
        client._models.execute_kw.return_value = True
        assert client.write("res.partner", [1], {"name": "New"}) is True

    def test_unlink_returns_true(self):
        client = _make_client()
        client._models.execute_kw.return_value = True
        assert client.unlink("res.partner", [1]) is True


# ---------------------------------------------------------------------------
# OdooClient.install_module / module_is_installed
# ---------------------------------------------------------------------------

class TestModules:
    def test_install_module_skips_if_already_installed(self):
        client = _make_client()
        # search returns empty → module already installed
        client._models.execute_kw.return_value = []
        client.install_module("sale_management")
        # execute_kw called once for search, button_immediate_install NOT called
        assert client._models.execute_kw.call_count == 1

    def test_install_module_calls_button_install(self):
        client = _make_client()
        # First call: search returns [5] (not installed)
        # Second call: button_immediate_install
        client._models.execute_kw.side_effect = [[5], True]
        client.install_module("sale_management")
        assert client._models.execute_kw.call_count == 2

    def test_module_is_installed_true(self):
        client = _make_client()
        client._models.execute_kw.return_value = [3]
        assert client.module_is_installed("sale_management") is True

    def test_module_is_installed_false(self):
        client = _make_client()
        client._models.execute_kw.return_value = []
        assert client.module_is_installed("sale_management") is False


# ---------------------------------------------------------------------------
# OdooClient.get_ref
# ---------------------------------------------------------------------------

class TestGetRef:
    def test_get_ref_returns_id(self):
        client = _make_client()
        client._models.execute_kw.return_value = 7
        result = client.get_ref("base.main_company")
        assert result == 7

    def test_get_ref_raises_if_not_found(self):
        client = _make_client()
        client._models.execute_kw.return_value = False
        with pytest.raises(OdooError):
            client.get_ref("base.nonexistent")


# ---------------------------------------------------------------------------
# OdooClient.find_or_create
# ---------------------------------------------------------------------------

class TestFindOrCreate:
    def test_returns_existing_id(self):
        client = _make_client()
        client._models.execute_kw.return_value = [99]
        result = client.find_or_create("res.partner", [("name", "=", "Acme")], {"name": "Acme"})
        assert result == 99
        assert client._models.execute_kw.call_count == 1  # only search

    def test_creates_if_not_found(self):
        client = _make_client()
        client._models.execute_kw.side_effect = [[], 55]
        result = client.find_or_create("res.partner", [("name", "=", "New")], {"name": "New"})
        assert result == 55
        assert client._models.execute_kw.call_count == 2  # search + create
