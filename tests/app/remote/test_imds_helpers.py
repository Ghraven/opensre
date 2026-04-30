"""Failure-path tests for the IMDS helper functions in app/remote/server.py.

Covers:
- _imds_token(): returns None when urlopen() raises URLError
- _imds_get(): returns None for TimeoutError and OSError

All tests are fully offline — no real network calls.

See: https://github.com/Tracer-Cloud/opensre/issues/1126
"""

from __future__ import annotations

import urllib.error
from unittest.mock import patch

import pytest

from app.remote.server import _imds_get, _imds_token


class TestImdsToken:
    """_imds_token() must return None on every network failure."""

    def test_returns_none_on_url_error(self) -> None:
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("no route")):
            assert _imds_token() is None

    def test_returns_none_on_timeout_error(self) -> None:
        with patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")):
            assert _imds_token() is None

    def test_returns_none_on_os_error(self) -> None:
        with patch("urllib.request.urlopen", side_effect=OSError("network unreachable")):
            assert _imds_token() is None

    def test_returns_none_when_response_is_empty(self) -> None:
        mock_response = __import__("unittest.mock", fromlist=["MagicMock"]).MagicMock()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = __import__("unittest.mock", fromlist=["MagicMock"]).MagicMock(return_value=False)
        mock_response.read.return_value = b"   "  # whitespace-only → stripped to "" → None
        with patch("urllib.request.urlopen", return_value=mock_response):
            assert _imds_token() is None


class TestImdsGet:
    """_imds_get() must return None on every network failure."""

    def test_returns_none_on_url_error(self) -> None:
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("connection refused")):
            assert _imds_get("latest/meta-data/instance-id", token="tok") is None

    def test_returns_none_on_timeout_error(self) -> None:
        with patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")):
            assert _imds_get("latest/meta-data/instance-id", token="tok") is None

    def test_returns_none_on_os_error(self) -> None:
        with patch("urllib.request.urlopen", side_effect=OSError("network down")):
            assert _imds_get("latest/meta-data/placement/region", token=None) is None

    def test_returns_none_when_no_token(self) -> None:
        """token=None path should still fail cleanly."""
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("no token")):
            assert _imds_get("latest/meta-data/public-ipv4", token=None) is None

    def test_returns_none_when_response_is_empty(self) -> None:
        from unittest.mock import MagicMock
        mock_response = MagicMock()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.read.return_value = b""
        with patch("urllib.request.urlopen", return_value=mock_response):
            assert _imds_get("latest/meta-data/instance-id", token="tok") is None
