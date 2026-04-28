"""Tests for CLI deploy commands — EC2 health check + Railway deploy flows.

Consolidated from app/cli/deploy_test.py into the tests/ tree.
See: https://github.com/Tracer-Cloud/opensre/issues/899
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from app.cli.__main__ import cli
from app.cli.deploy import (
    _extract_railway_url,
    deploy_to_railway,
    get_railway_auth_status,
    is_railway_cli_installed,
    run_deploy,
)


# ─────────────────────────────────────────────────────────────────────────────
# Existing EC2 health-check test (was already in tests/cli/test_deploy.py)
# ─────────────────────────────────────────────────────────────────────────────

class TestEC2HealthCheck:
    """Tests for EC2 instance health check deploy path."""

    def test_deploy_command_exists(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["deploy", "--help"])
        assert result.exit_code == 0


# ─────────────────────────────────────────────────────────────────────────────
# Railway deploy tests (moved from app/cli/deploy_test.py)
# ─────────────────────────────────────────────────────────────────────────────

class TestIsRailwayCliInstalled:
    def test_returns_true_when_railway_found(self):
        with patch("shutil.which", return_value="/usr/local/bin/railway"):
            assert is_railway_cli_installed() is True

    def test_returns_false_when_railway_not_found(self):
        with patch("shutil.which", return_value=None):
            assert is_railway_cli_installed() is False


class TestGetRailwayAuthStatus:
    def test_returns_authenticated_on_success(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "user@example.com"
        with patch("subprocess.run", return_value=mock_result):
            status = get_railway_auth_status()
        assert status["authenticated"] is True
        assert "user@example.com" in status["user"]

    def test_returns_unauthenticated_on_failure(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        with patch("subprocess.run", return_value=mock_result):
            status = get_railway_auth_status()
        assert status["authenticated"] is False

    def test_handles_exception(self):
        with patch("subprocess.run", side_effect=FileNotFoundError("railway not found")):
            status = get_railway_auth_status()
        assert status["authenticated"] is False
        assert "error" in status


class TestExtractRailwayUrl:
    def test_extracts_url_from_output(self):
        output = "Deployment successful\nhttps://myapp.railway.app\nDone"
        url = _extract_railway_url(output)
        assert url == "https://myapp.railway.app"

    def test_returns_none_when_no_url(self):
        url = _extract_railway_url("No URL here")
        assert url is None

    def test_returns_first_url_when_multiple(self):
        output = "https://first.railway.app\nhttps://second.railway.app"
        url = _extract_railway_url(output)
        assert url == "https://first.railway.app"


class TestDeployToRailway:
    def test_successful_deploy(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Deployed to https://myapp.railway.app"
        mock_result.stderr = ""
        with patch("subprocess.run", return_value=mock_result):
            result = deploy_to_railway(service="myservice", environment="production")
        assert result["success"] is True
        assert result["url"] == "https://myapp.railway.app"

    def test_failed_deploy_returns_error(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Error: service not found"
        with patch("subprocess.run", return_value=mock_result):
            result = deploy_to_railway(service="bad-service")
        assert result["success"] is False
        assert "error" in result

    def test_handles_subprocess_exception(self):
        with patch("subprocess.run", side_effect=Exception("connection error")):
            result = deploy_to_railway(service="myservice")
        assert result["success"] is False


class TestRunDeploy:
    def test_run_deploy_railway(self):
        with patch(
            "app.cli.deploy.deploy_to_railway",
            return_value={"success": True, "url": "https://app.railway.app"},
        ):
            result = run_deploy(platform="railway", service="myapp")
        assert result["success"] is True

    def test_run_deploy_unknown_platform(self):
        result = run_deploy(platform="unknown-platform")
        assert result["success"] is False
        assert "unsupported" in result.get("error", "").lower()


class TestDeployCLICommand:
    def test_deploy_railway_command(self):
        runner = CliRunner()
        with patch(
            "app.cli.deploy.deploy_to_railway",
            return_value={"success": True, "url": "https://app.railway.app"},
        ):
            result = runner.invoke(cli, ["deploy", "railway", "--service", "myapp"])
        assert result.exit_code == 0

    def test_deploy_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["deploy", "--help"])
        assert result.exit_code == 0
        assert "deploy" in result.output.lower()
