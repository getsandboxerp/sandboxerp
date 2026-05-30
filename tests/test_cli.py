"""
tests.test_cli
~~~~~~~~~~~~~~

Unit tests for the SandboxERP CLI layer.

Covers:
- Root app: ``--version``, ``--help``, no-args behaviour.
- ``sandbox generate``: required flags, validation, network-exposure warning.
- ``sandbox start`` / ``stop`` / ``destroy``: basic invocability and
  ``--force`` flag on destroy.

All tests use Typer's built-in ``CliRunner`` (wraps Click's runner) so no
real Docker interaction or file I/O occurs — the engine stubs return early.
"""

import pytest
from typer.testing import CliRunner

from sandboxerp.cli.main import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def invoke(*args: str):
    """Convenience wrapper: invoke ``app`` with *args* and return the result."""
    return runner.invoke(app, list(args))


# ---------------------------------------------------------------------------
# Root app
# ---------------------------------------------------------------------------

class TestRootApp:
    def test_no_args_shows_help(self):
        """
        With no arguments the root app prints help text.

        ``no_args_is_help=True`` makes Click/Typer call ``sys.exit(0)`` after
        printing help; the CliRunner surfaces this as exit_code 0.  We assert
        on output content rather than exit code to stay robust across versions.
        """
        result = invoke()
        assert "sandbox" in result.output.lower() or "Usage" in result.output

    def test_version_flag_short(self):
        """``-V`` prints a version string and exits 0."""
        result = invoke("-V")
        assert result.exit_code == 0
        # Should contain the package name regardless of version number
        assert "SandboxERP" in result.output

    def test_version_flag_long(self):
        """``--version`` behaves identically to ``-V``."""
        result = invoke("--version")
        assert result.exit_code == 0
        assert "SandboxERP" in result.output

    def test_help_flag(self):
        """``--help`` exits 0 and mentions all registered subcommands."""
        result = invoke("--help")
        assert result.exit_code == 0
        for sub in ("generate", "start", "stop", "destroy"):
            assert sub in result.output


# ---------------------------------------------------------------------------
# sandbox generate
# ---------------------------------------------------------------------------

class TestGenerate:
    def test_missing_country_exits_nonzero(self):
        """``generate`` without --country must fail."""
        result = invoke("generate", "--industry", "retail", "--profile", "small")
        assert result.exit_code != 0

    def test_missing_industry_exits_nonzero(self):
        """``generate`` without --industry must fail."""
        result = invoke("generate", "--country", "cl", "--profile", "small")
        assert result.exit_code != 0

    def test_valid_flags_runs_stub(self):
        """
        A fully-specified generate call should reach the stub message without
        error.
        """
        result = invoke(
            "generate",
            "--country", "cl",
            "--industry", "retail",
            "--profile", "small",
            "--seed", "42",
        )
        assert result.exit_code == 0
        assert "stub" in result.output.lower() or "not yet implemented" in result.output.lower()

    def test_invalid_country_rejected(self):
        """Unsupported country code must produce a BadParameter error."""
        result = invoke(
            "generate",
            "--country", "xx",
            "--industry", "retail",
            "--profile", "small",
        )
        assert result.exit_code != 0
        assert "country" in result.output.lower() or "xx" in result.output

    def test_invalid_industry_rejected(self):
        """Unsupported industry must produce a BadParameter error."""
        result = invoke(
            "generate",
            "--country", "cl",
            "--industry", "unknown_industry",
            "--profile", "small",
        )
        assert result.exit_code != 0

    def test_invalid_profile_rejected(self):
        """Unsupported profile must produce a BadParameter error."""
        result = invoke(
            "generate",
            "--country", "cl",
            "--industry", "retail",
            "--profile", "gigantic",
        )
        assert result.exit_code != 0

    def test_default_profile_is_small(self):
        """
        Omitting --profile should default to 'small' and succeed.
        """
        result = invoke("generate", "--country", "cl", "--industry", "retail")
        assert result.exit_code == 0

    def test_bind_warning_abort(self):
        """
        Passing ``--bind 0.0.0.0`` with a 'n' confirmation should abort
        cleanly.
        """
        result = runner.invoke(
            app,
            ["generate", "--country", "cl", "--industry", "retail", "--bind", "0.0.0.0"],
            input="n\n",
        )
        # Abort raises typer.Abort which causes exit_code 1
        assert result.exit_code != 0 or "Aborted" in result.output

    def test_bind_warning_confirm(self):
        """
        Accepting the ``--bind 0.0.0.0`` warning should continue to the stub.
        """
        result = runner.invoke(
            app,
            ["generate", "--country", "cl", "--industry", "retail", "--bind", "0.0.0.0"],
            input="y\n",
        )
        assert result.exit_code == 0

    def test_generate_help(self):
        """``sandbox generate --help`` should exit 0."""
        result = invoke("generate", "--help")
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# sandbox start
# ---------------------------------------------------------------------------

class TestStart:
    def test_start_runs_stub(self):
        """``sandbox start`` must exit 0 (stub)."""
        result = invoke("start")
        assert result.exit_code == 0

    def test_start_help(self):
        result = invoke("start", "--help")
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# sandbox stop
# ---------------------------------------------------------------------------

class TestStop:
    def test_stop_runs_stub(self):
        """``sandbox stop`` must exit 0 (stub)."""
        result = invoke("stop")
        assert result.exit_code == 0

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

    def test_destroy_confirm_on_yes(self):
        """Answering 'y' should continue to the stub."""
        result = runner.invoke(app, ["destroy"], input="y\n")
        assert result.exit_code == 0

    def test_destroy_force_skips_prompt(self):
        """``--force`` must skip the confirmation prompt entirely."""
        result = invoke("destroy", "--force")
        assert result.exit_code == 0

    def test_destroy_help(self):
        result = invoke("destroy", "--help")
        assert result.exit_code == 0
