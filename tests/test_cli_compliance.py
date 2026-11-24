"""
tests.test_cli_compliance
~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for the ``--compliance`` flag of ``sandbox generate``:
parsing, the previous-quarter default, and the three validation steps
(malformed flag, country without a compliance block, missing license).

Pack loading and license checks are mocked, so no real country pack,
license key or Odoo instance is needed.

:author: Hector Colina / Team360 <https://team360.cl>
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest
import typer

from sandboxerp.cli.generate import (
    _previous_quarter,
    _resolve_compliance,
    parse_compliance_flag,
)

# ---------------------------------------------------------------------------
# _previous_quarter
# ---------------------------------------------------------------------------


class TestPreviousQuarter:
    @pytest.mark.parametrize(
        ("today", "expected"),
        [
            (date(2025, 1, 15), ("4T", 2024)),   # Q1 -> Q4 of last year
            (date(2025, 3, 31), ("4T", 2024)),
            (date(2025, 4, 1), ("1T", 2025)),
            (date(2025, 7, 31), ("2T", 2025)),
            (date(2025, 12, 31), ("3T", 2025)),
        ],
    )
    def test_previous_quarter(self, today, expected):
        assert _previous_quarter(today) == expected

    def test_defaults_to_today(self):
        period, year = _previous_quarter()
        assert period in {"1T", "2T", "3T", "4T"}
        assert isinstance(year, int)


# ---------------------------------------------------------------------------
# parse_compliance_flag
# ---------------------------------------------------------------------------


class TestParseComplianceFlag:
    def test_full_value(self):
        parsed = parse_compliance_flag("tax_report,period=3T,year=2025")
        assert parsed == {"report": "tax_report", "period": "3T", "year": "2025"}

    def test_defaults_to_previous_quarter(self):
        with patch(
            "sandboxerp.cli.generate._previous_quarter", return_value=("2T", 2025)
        ):
            parsed = parse_compliance_flag("tax_report")
        assert parsed == {"report": "tax_report", "period": "2T", "year": "2025"}

    def test_explicit_period_keeps_default_year(self):
        with patch(
            "sandboxerp.cli.generate._previous_quarter", return_value=("2T", 2025)
        ):
            parsed = parse_compliance_flag("tax_report,period=1T")
        assert parsed["period"] == "1T"
        assert parsed["year"] == "2025"

    def test_extra_keys_are_kept(self):
        parsed = parse_compliance_flag("tax_report,period=3T,year=2025,format=xml")
        assert parsed["format"] == "xml"

    def test_spaces_are_trimmed(self):
        parsed = parse_compliance_flag(" tax_report , period = 3T , year = 2025 ")
        assert parsed == {"report": "tax_report", "period": "3T", "year": "2025"}

    @pytest.mark.parametrize("value", ["", "   ", ",,,"])
    def test_empty_value_rejected(self, value):
        with pytest.raises(typer.BadParameter):
            parse_compliance_flag(value)

    @pytest.mark.parametrize(
        "value",
        ["tax_report,period", "tax_report,=3T", "tax_report,period="],
    )
    def test_malformed_segment_rejected(self, value):
        with pytest.raises(typer.BadParameter):
            parse_compliance_flag(value)


# ---------------------------------------------------------------------------
# _resolve_compliance
# ---------------------------------------------------------------------------


class TestResolveCompliance:
    def test_malformed_flag_fails_before_loading_the_pack(self):
        with patch("sandboxerp.cli.generate.load_country_pack") as load:
            with pytest.raises(typer.BadParameter):
                _resolve_compliance("es", "tax_report,period")
        load.assert_not_called()

    def test_country_without_compliance_block_exits(self):
        with (
            patch(
                "sandboxerp.cli.generate.load_country_pack",
                return_value={"meta": {"code": "cl"}},
            ),
            patch("sandboxerp.cli.generate.require_premium") as premium,
        ):
            with pytest.raises(typer.Exit) as exc:
                _resolve_compliance("cl", "tax_report,period=3T,year=2025")
        assert exc.value.exit_code == 1
        premium.assert_not_called()  # pack support is checked before the license

    def test_missing_license_propagates(self, monkeypatch):
        monkeypatch.delenv("SANDBOXERP_LICENSE_KEY", raising=False)
        with (
            patch(
                "sandboxerp.cli.generate.load_country_pack",
                return_value={"compliance": {}},
            ),
            patch(
                "sandboxerp.cli.generate.require_premium",
                side_effect=PermissionError("premium license required"),
            ),
        ):
            with pytest.raises(PermissionError):
                _resolve_compliance("es", "tax_report,period=3T,year=2025")

    def test_license_key_is_read_from_the_environment(self, monkeypatch):
        monkeypatch.setenv("SANDBOXERP_LICENSE_KEY", "abc-123")
        with (
            patch(
                "sandboxerp.cli.generate.load_country_pack",
                return_value={"compliance": {}},
            ),
            patch("sandboxerp.cli.generate.require_premium") as premium,
        ):
            _resolve_compliance("es", "tax_report,period=3T,year=2025")
        key = premium.call_args.args[0]
        feature = premium.call_args.kwargs["feature"]
        assert key == "abc-123"
        assert "tax_report" in feature

    def test_valid_request_returns_parsed_dict(self, monkeypatch):
        monkeypatch.setenv("SANDBOXERP_LICENSE_KEY", "abc-123")
        with (
            patch(
                "sandboxerp.cli.generate.load_country_pack",
                return_value={"compliance": {}},
            ),
            patch("sandboxerp.cli.generate.require_premium"),
        ):
            parsed = _resolve_compliance("es", "tax_report,period=3T,year=2025")
        assert parsed == {"report": "tax_report", "period": "3T", "year": "2025"}
