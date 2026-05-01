"""Tests for OpenObserveLogsTool."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.tools.OpenObserveLogsTool import (
    _auth_headers,
    _bounded_limit,
    _extract_records,
    _openobserve_available,
    _openobserve_extract_params,
    query_openobserve_logs,
)


# ---------------------------------------------------------------------------
# _openobserve_available
# ---------------------------------------------------------------------------

def test_available_true_with_token() -> None:
    sources = {
        "openobserve": {
            "connection_verified": True,
            "base_url": "http://oo.example.com",
            "api_token": "mytoken",
        }
    }
    assert _openobserve_available(sources) is True


def test_available_true_with_username_password() -> None:
    sources = {
        "openobserve": {
            "connection_verified": True,
            "base_url": "http://oo.example.com",
            "username": "admin",
            "password": "secret",
        }
    }
    assert _openobserve_available(sources) is True


def test_available_false_without_credentials() -> None:
    sources = {
        "openobserve": {"connection_verified": True, "base_url": "http://oo.example.com"}
    }
    assert _openobserve_available(sources) is False


def test_available_false_without_base_url() -> None:
    sources = {"openobserve": {"connection_verified": True, "api_token": "tok"}}
    assert _openobserve_available(sources) is False


def test_available_false_without_connection_verified() -> None:
    sources = {
        "openobserve": {"base_url": "http://oo.example.com", "api_token": "tok"}
    }
    assert _openobserve_available(sources) is False


def test_available_false_no_openobserve_key() -> None:
    assert _openobserve_available({}) is False


# ---------------------------------------------------------------------------
# _openobserve_extract_params
# ---------------------------------------------------------------------------

def test_extract_params_maps_all_fields() -> None:
    sources = {
        "openobserve": {
            "base_url": " http://oo.example.com ",
            "org": "myorg",
            "stream": "logs",
            "query": "SELECT * FROM logs",
            "api_token": "tok",
            "username": "admin",
            "password": "secret",
            "time_range_minutes": 30,
            "max_results": 80,
            "integration_id": "oo-01",
        }
    }
    params = _openobserve_extract_params(sources)
    assert params["base_url"] == "http://oo.example.com"
    assert params["org"] == "myorg"
    assert params["stream"] == "logs"
    assert params["api_token"] == "tok"
    assert params["time_range_minutes"] == 30
    assert params["max_results"] == 80
    assert params["integration_id"] == "oo-01"


def test_extract_params_defaults_org_to_default() -> None:
    sources = {"openobserve": {"base_url": "http://oo.example.com", "api_token": "tok"}}
    params = _openobserve_extract_params(sources)
    assert params["org"] == "default"


# ---------------------------------------------------------------------------
# _bounded_limit
# ---------------------------------------------------------------------------

def test_bounded_limit_clamps_above_hard_limit() -> None:
    assert _bounded_limit(500, 100) == 100


def test_bounded_limit_minimum_one() -> None:
    assert _bounded_limit(0, 0) == 1


# ---------------------------------------------------------------------------
# _auth_headers
# ---------------------------------------------------------------------------

def test_auth_headers_bearer_when_token_present() -> None:
    headers = _auth_headers("mytoken", "", "")
    assert headers["Authorization"] == "Bearer mytoken"


def test_auth_headers_basic_when_username_password() -> None:
    import base64

    headers = _auth_headers("", "alice", "secret")
    expected = "Basic " + base64.b64encode(b"alice:secret").decode("ascii")
    assert headers["Authorization"] == expected


# ---------------------------------------------------------------------------
# _extract_records
# ---------------------------------------------------------------------------

def test_extract_records_from_hits_dict() -> None:
    body = {
        "hits": {
            "hits": [
                {"_source": {"level": "error", "msg": "oops"}},
                {"_source": {"level": "info", "msg": "ok"}},
            ]
        }
    }
    records = _extract_records(body)
    assert len(records) == 2
    assert records[0]["level"] == "error"


def test_extract_records_from_hits_list() -> None:
    body = {"hits": [{"level": "warn"}, {"level": "debug"}]}
    records = _extract_records(body)
    assert len(records) == 2


def test_extract_records_from_records_key() -> None:
    body = {"records": [{"ts": "2026-01-01", "msg": "hi"}]}
    records = _extract_records(body)
    assert records[0]["msg"] == "hi"


def test_extract_records_from_data_key() -> None:
    body = {"data": [{"id": 1}]}
    records = _extract_records(body)
    assert records[0]["id"] == 1


def test_extract_records_empty_body() -> None:
    assert _extract_records({}) == []


# ---------------------------------------------------------------------------
# query_openobserve_logs — integration tests (httpx patched)
# ---------------------------------------------------------------------------

def test_run_returns_unavailable_when_base_url_missing() -> None:
    result = query_openobserve_logs(base_url="", api_token="tok")
    assert result["available"] is False
    assert "url" in result["error"].lower()


def test_run_returns_unavailable_when_no_credentials() -> None:
    result = query_openobserve_logs(base_url="http://oo.example.com")
    assert result["available"] is False
    assert "credentials" in result["error"].lower()


def test_run_happy_path_with_token() -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "records": [{"level": "error"}, {"level": "warn"}]
    }
    mock_response.raise_for_status.return_value = None

    with patch("app.tools.OpenObserveLogsTool.httpx.post", return_value=mock_response):
        result = query_openobserve_logs(
            base_url="http://oo.example.com",
            api_token="tok",
            limit=50,
        )

    assert result["available"] is True
    assert result["total_returned"] == 2


def test_run_uses_default_query_when_none_provided() -> None:
    captured: list[dict] = []

    def fake_post(url, *, headers, json, timeout):
        captured.append(json)
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"records": []}
        mock_resp.raise_for_status.return_value = None
        return mock_resp

    with patch("app.tools.OpenObserveLogsTool.httpx.post", side_effect=fake_post):
        query_openobserve_logs(base_url="http://oo.example.com", api_token="tok")

    assert "SELECT" in captured[0]["query"]["sql"]


def test_run_http_error_returns_unavailable() -> None:
    with patch(
        "app.tools.OpenObserveLogsTool.httpx.post",
        side_effect=Exception("timeout"),
    ):
        result = query_openobserve_logs(base_url="http://oo.example.com", api_token="tok")

    assert result["available"] is False
    assert "timeout" in result["error"]


def test_run_respects_hard_limit() -> None:
    records = [{"level": "info"} for _ in range(300)]
    mock_response = MagicMock()
    mock_response.json.return_value = {"records": records}
    mock_response.raise_for_status.return_value = None

    with patch("app.tools.OpenObserveLogsTool.httpx.post", return_value=mock_response):
        result = query_openobserve_logs(
            base_url="http://oo.example.com",
            api_token="tok",
            limit=200,
            max_results=200,
        )

    assert result["total_returned"] <= 200
