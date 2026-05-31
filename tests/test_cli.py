"""
tests.test_cli
~~~~~~~~~~~~~~

Unit tests for the SandboxERP CLI layer.

Covers:
- Root app: ``--version``, ``--help``, no-args behaviour.
- ``sandbox generate``: required flags, validation, network-exposure warning.
- ``sandbox start`` / ``stop`` / ``destroy``: engine integration and error
  handling.

All tests use Typer's built-in ``CliRunner`` (wraps Click's runner) so no
real Docker interaction or file I/O occurs — engine functions are mocked
at the CLI boundary.

:author: Hector Colina / Team360 <https://team360.cl>
"""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from sandboxerp.cli.main import app

runner = CliRunner()

_GENERATE_ENGINE = "sandboxerp.cli.generate.generate_environment"
_START_ENGINE    = "sandboxerp.cli.start.start_environment"
_STOP_ENGINE     = "sandboxerp.cli.stop.stop_environment"
_DESTROY_ENGINE  = "sandboxerp.cli.destroy.destroy_environment"


def invoke(*args: str):
    """Convenience wrapper: invoke ``app`` with *args* and return the result."""
    return runner.invoke(app, list(args))


# ---------------------------------------------------------------------------
# Root app
# ---------------------------------------------------------------------------

class TestRootApp:
    def test_no_args_shows_help(self):
        result = invoke()
        assert "sandbox" in result.output.lower() or "Usage" in result.output

    def test_version_flag_short(self):
        result = invoke("-V")
        assert result.exit_code == 0
        assert "SandboxERP" in result.output

    def test_version_flag_long(self):
        result = invoke("--version")
        assert result.exit_code == 0
        assert "SandboxERP" in result.output

    def test_help_flag(self):
        result = invoke("--help")
        assert result.exit_code == 0
        for sub in ("generate", "start", "stop", "destroy"):
            assert sub in result.output


# ---------------------------------------------------------------------------
# sandbox generate
# ---------------------------------------------------------------------------

class TestGenerate:
    def test_missing_country_exits_nonzero(self):
        result = invoke("generate", "--industry", "retail", "--profile", "small")
        assert result.exit_code != 0

    def test_missing_industry_exits_nonzero(self):
        result = invoke("generate", "--country", "cl", "--profile", "small")
        assert result.exit_code != 0

    def test_valid_flags_calls_engine(self):
        with patch(_GENERATE_ENGINE) as mock_engine:
            result = invoke(
                "generate",
                "--country", "cl",
                "--industry", "retail",
                "--profile", "small",
                "--seed", "42",
            )
        assert result.exit_code == 0
        mock_engine.assert_called_once_with(
            country="cl",
            industry="retail",
            profile="small",
            seed=42,
            bind="127.0.0.1",
            port=8069,
            force=False,
        )

    def test_engine_runtime_error_exits_nonzero(self):
        with patch(_GENERATE_ENGINE, side_effect=RuntimeError("Docker not running")):
            result = invoke(
                "generate",
                "--country", "cl",
                "--industry", "retail",
                "--profile", "small",
            )
        assert result.exit_code == 1
        assert "Error" in result.output or "Docker" in result.output

    def test_invalid_country_rejected(self):
        result = invoke(
            "generate", "--country", "xx", "--industry", "retail", "--profile", "small",
        )
        assert result.exit_code != 0
        assert "country" in result.output.lower() or "xx" in result.output

    def test_invalid_industry_rejected(self):
        result = invoke(
            "generate", "--country", "cl", "--industry", "unknown_industry", "--profile", "small",
        )
        assert result.exit_code != 0

    def test_invalid_profile_rejected(self):
        result = invoke(
            "generate", "--country", "cl", "--industry", "retail", "--profile", "gigantic",
        )
        assert result.exit_code != 0

    def test_default_profile_is_small(self):
        with patch(_GENERATE_ENGINE):
            result = invoke("generate", "--country", "cl", "--industry", "retail")
        assert result.exit_code == 0

    def test_force_flag_passed_to_engine(self):
        with patch(_GENERATE_ENGINE) as mock_engine:
            invoke("generate", "--country", "cl", "--industry", "retail", "--force")
        _, kwargs = mock_engine.call_args
        assert kwargs["force"] is True

    def test_bind_warning_abort(self):
        result = runner.invoke(
            app,
            ["generate", "--country", "cl", "--industry", "retail", "--bind", "0.0.0.0"],
            input="n\n",
        )
        assert result.exit_code != 0 or "Aborted" in result.output

    def test_bind_warning_confirm(self):
        with patch(_GENERATE_ENGINE) as mock_engine:
            result = runner.invoke(
                app,
                ["generate", "--country", "cl", "--industry", "retail", "--bind", "0.0.0.0"],
                input="y\n",
            )
        assert result.exit_code == 0
        mock_engine.assert_called_once()

    def test_generate_help(self):
        result = invoke("generate", "--help")
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# sandbox start
# ---------------------------------------------------------------------------

class TestStart:
    def test_start_calls_engine(self):
        """``sandbox start`` must call ``start_environment`` when env exists and is stopped."""
        with patch("sandboxerp.cli.start.get_client", return_value=MagicMock()), \
             patch("sandboxerp.cli.start.environment_exists", return_value=True), \
             patch("sandboxerp.cli.start.environment_is_running", return_value=False), \
             patch(_START_ENGINE) as mock_start:
            result = invoke("start")
        assert result.exit_code == 0
        mock_start.assert_called_once()

    def test_start_exits_if_no_environment(self):
        """``sandbox start`` must exit 1 when no environment exists."""
        with patch("sandboxerp.cli.start.get_client", return_value=MagicMock()), \
             patch("sandboxerp.cli.start.environment_exists", return_value=False):
            result = invoke("start")
        assert result.exit_code == 1

    def test_start_exits_if_already_running(self):
        """``sandbox start`` must exit 0 with a warning if already running."""
        with patch("sandboxerp.cli.start.get_client", return_value=MagicMock()), \
             patch("sandboxerp.cli.start.environment_exists", return_value=True), \
             patch("sandboxerp.cli.start.environment_is_running", return_value=True):
            result = invoke("start")
        assert result.exit_code == 0
        assert "already running" in result.output.lower()

    def test_start_exits_on_docker_error(self):
        """``sandbox start`` must exit 1 when Docker is not available."""
        with patch("sandboxerp.cli.start.get_client", side_effect=RuntimeError("no docker")):
            result = invoke("start")
        assert result.exit_code == 1

    def test_start_help(self):
        result = invoke("start", "--help")
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# sandbox stop
# ---------------------------------------------------------------------------

class TestStop:
    def test_stop_calls_engine(self):
        """``sandbox stop`` must call ``stop_environment`` when env is running."""
        with patch("sandboxerp.cli.stop.get_client", return_value=MagicMock()), \
             patch("sandboxerp.cli.stop.environment_exists", return_value=True), \
             patch("sandboxerp.cli.stop.environment_is_running", return_value=True), \
             patch(_STOP_ENGINE) as mock_stop:
            result = invoke("stop")
        assert result.exit_code == 0
        mock_stop.assert_called_once()

    def test_stop_exits_if_no_environment(self):
        """``sandbox stop`` must exit 1 when no environment exists."""
        with patch("sandboxerp.cli.stop.get_client", return_value=MagicMock()), \
             patch("sandboxerp.cli.stop.environment_exists", return_value=False):
            result = invoke("stop")
        assert result.exit_code == 1

    def test_stop_exits_if_already_stopped(self):
        """``sandbox stop`` must exit 0 with a warning if already stopped."""
        with patch("sandboxerp.cli.stop.get_client", return_value=MagicMock()), \
             patch("sandboxerp.cli.stop.environment_exists", return_value=True), \
             patch("sandboxerp.cli.stop.environment_is_running", return_value=False):
            result = invoke("stop")
        assert result.exit_code == 0
        assert "already stopped" in result.output.lower()

    def test_stop_exits_on_docker_error(self):
        """``sandbox stop`` must exit 1 when Docker is not available."""
        with patch("sandboxerp.cli.stop.get_client", side_effect=RuntimeError("no docker")):
            result = invoke("stop")
        assert result.exit_code == 1

    def test_stop_help(self):
        result = invoke("stop", "--help")
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# sandbox destroy
# ---------------------------------------------------------------------------

class TestDestroy:
    def test_destroy_abort_on_no(self):
        """Answering 'n' to the confirmation must abort."""
        result = runner.invoke(app, ["destroy"], input="n\n")
        assert result.exit_code != 0 or "Aborted" in result.output

    def test_destroy_calls_engine_on_confirm(self):
        """Answering 'y' must call ``destroy_environment``."""
        with patch("sandboxerp.cli.destroy.get_client", return_value=MagicMock()), \
             patch("sandboxerp.cli.destroy.environment_exists", return_value=True), \
             patch(_DESTROY_ENGINE) as mock_destroy:
            result = runner.invoke(app, ["destroy"], input="y\n")
        assert result.exit_code == 0
        mock_destroy.assert_called_once()

    def test_destroy_force_skips_prompt(self):
        """``--force`` must skip the confirmation prompt entirely."""
        with patch("sandboxerp.cli.destroy.get_client", return_value=MagicMock()), \
             patch("sandboxerp.cli.destroy.environment_exists", return_value=True), \
             patch(_DESTROY_ENGINE):
            result = invoke("destroy", "--force")
        assert result.exit_code == 0

    def test_destroy_exits_if_no_environment(self):
        """``sandbox destroy`` must exit 1 when no environment exists."""
        with patch("sandboxerp.cli.destroy.get_client", return_value=MagicMock()), \
             patch("sandboxerp.cli.destroy.environment_exists", return_value=False):
            result = invoke("destroy", "--force")
        assert result.exit_code == 1

    def test_destroy_exits_on_docker_error(self):
        """``sandbox destroy`` must exit 1 when Docker is not available."""
        with patch("sandboxerp.cli.destroy.get_client", side_effect=RuntimeError("no docker")):
            result = invoke("destroy", "--force")
        assert result.exit_code == 1

    def test_destroy_help(self):
        result = invoke("destroy", "--help")
        assert result.exit_code == 0
