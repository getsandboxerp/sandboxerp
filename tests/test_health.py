"""Tests for the health check company line."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from sandboxerp.engine.health import _print_company

_COMPANY = [{"name": "SandboxERP", "country_id": [1, "DO"], "currency_id": [2, "DOP"]}]
_METRICS = {"country_pack": {"meta": {"locale": "es_MX"}}}


def _client(users):
    """Build a mock client returning the company and the given users."""
    client = MagicMock()

    def search_read(model, domain, fields=None, **kwargs):
        if model == "res.company":
            return _COMPANY
        if model == "res.users":
            return users
        return []

    client.search_read.side_effect = search_read
    return client


class TestPrintCompany:
    def test_shows_admin_language_not_faker_locale(self):
        """The line shows the language configured in Odoo (es_DO)."""
        with patch("sandboxerp.engine.health.console") as console:
            _print_company(_client([{"lang": "es_DO"}]), _METRICS)
        line = console.print.call_args.args[0]
        assert "es_DO" in line
        assert "es_MX" not in line

    def test_falls_back_to_pack_locale_when_user_has_no_lang(self):
        """If the admin language cannot be read, meta.locale is used."""
        with patch("sandboxerp.engine.health.console") as console:
            _print_company(_client([]), _METRICS)
        assert "es_MX" in console.print.call_args.args[0]

    def test_prints_nothing_when_company_missing(self):
        """No company record means nothing is printed."""
        client = MagicMock()
        client.search_read.return_value = []
        with patch("sandboxerp.engine.health.console") as console:
            _print_company(client, _METRICS)
        console.print.assert_not_called()
