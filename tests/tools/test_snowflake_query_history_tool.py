"""Tests for SnowflakeQueryHistoryTool."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.tools.SnowflakeQueryHistoryTool import (
    _auth_header,
    _bounded_limit,
    _ensure_sql_limit,
    _normalize_rows,
    _snowflake_available,
    _snowflake_extract_params,
    query_snowflake_history,
)


# ---------------------------------------------------------------------------
# _snowflake_available
# ---------------------------------------------------------------------------

def test_available_true_when_all_fields_present() -> None:
    sources = {
        "snowflake": {
            "connection_verified": True,
            "account_identifier": "acct123",
            "token": "tok",
        }
    }
    assert _snowflake_available(sources) is True


def test_available_false_without_connection_verified() -> None:
    sources = {"snowflake": {"account_identifier": "acct123", "token": "tok"}}
    assert _snowflake_available(sources) is False


def test_available_false_when_token_blank() -> None:
    sources = {
        "snowflake": {
            "connection_verified": True,
            "account_identifier": "acct123",
            "token": "   ",
        }
    }
    assert _snowflake_available(sources) is False


def test_available_false_missing_account_identifier() -> None:
    sources = {"snowflake": {"connection_verified": True, "token": "tok"}}
    assert _snowflake_available(sources) is False


def test_available_false_no_snowflake_key() -> None:
    assert _snowflake_available({}) is False


# ---------------------------------------------------------------------------
# _snowflake_extract_params
# ---------------------------------------------------------------------------

def test_extract_params_maps_all_fields() -> None:
    sources = {
        "snowflake": {
            "account_identifier": " acct ",
            "user": "alice",
            "password": "secret",
            "token": "mytoken",
            "warehouse": "WH1",
            "role": "SYSADMIN",
            "database": "DB",
            "schema": "PUBLIC",
            "query": "SELECT 1",
            "max_results": 100,
            "integration_id": "sf-01",
        }
    }
    params = _snowflake_extract_params(sources)
    assert params["account_identifier"] == "acct"
    assert params["user"] == "alice"
    assert params["token"] == "mytoken"
    assert params["warehouse"] == "WH1"
    assert params["role"] == "SYSADMIN"
    assert params["database"] == "DB"
    assert params["db_schema"] == "PUBLIC"
    assert params["query"] == "SELECT 1"
    assert params["max_results"] == 100
    assert params["integration_id"] == "sf-01"


def test_extract_params_defaults_max_results() -> None:
    sources = {"snowflake": {"account_identifier": "acct", "token": "tok"}}
    params = _snowflake_extract_params(sources)
    assert params["max_results"] == 50


# ---------------------------------------------------------------------------
# _bounded_limit
# ---------------------------------------------------------------------------

def test_bounded_limit_clamps_to_max_hard_limit() -> None:
    assert _bounded_limit(999, 50) == 50


def test_bounded_limit_respects_max_results() -> None:
    assert _bounded_limit(10, 30) == 10


def test_bounded_limit_minimum_one() -> None:
    assert _bounded_limit(0, 0) == 1


# ---------------------------------------------------------------------------
# _ensure_sql_limit
# ---------------------------------------------------------------------------

def test_ensure_sql_limit_appends_limit_when_absent() -> None:
    result = _ensure_sql_limit("SELECT * FROM foo", 25)
    assert result.upper().endswith("LIMIT 25")


def test_ensure_sql_limit_preserves_existing_limit() -> None:
    q = "SELECT * FROM foo LIMIT 10"
    assert _ensure_sql_limit(q, 25) == q


def test_ensure_sql_limit_returns_default_for_empty_query() -> None:
    result = _ensure_sql_limit("", 5)
    assert "QUERY_HISTORY" in result
    assert "5" in result


# ---------------------------------------------------------------------------
# _auth_header
# ---------------------------------------------------------------------------

def test_auth_header_uses_bearer_token() -> None:
    headers = _auth_header("mytoken")
    assert headers["Authorization"] == "Bearer mytoken"


# ---------------------------------------------------------------------------
# _normalize_rows — dict-of-dicts format
# ---------------------------------------------------------------------------

def test_normalize_rows_list_of_dicts() -> None:
    payload = {"data": [{"query_id": "q1"}, {"query_id": "q2"}]}
    rows = _normalize_rows(payload)
    assert len(rows) == 2
    assert rows[0]["query_id"] == "q1"


def test_normalize_rows_tabular_format() -> None:
    payload = {
        "resultSetMetaData": {"rowType": [{"name": "query_id"}, {"name": "user_name"}]},
        "data": [["q1", "alice"], ["q2", "bob"]],
    }
    rows = _normalize_rows(payload)
    assert rows[0] == {"query_id": "q1", "user_name": "alice"}
    assert rows[1] == {"query_id": "q2", "user_name": "bob"}


def test_normalize_rows_empty_data() -> None:
    assert _normalize_rows({}) == []


# ---------------------------------------------------------------------------
# query_snowflake_history — integration tests (httpx patched)
# ---------------------------------------------------------------------------

def test_run_returns_unavailable_when_account_missing() -> None:
    result = query_snowflake_history(account_identifier="", token="tok")
    assert result["available"] is False
    assert "account" in result["error"].lower()


def test_run_returns_unavailable_when_token_missing() -> None:
    result = query_snowflake_history(account_identifier="acct123", token="")
    assert result["available"] is False
    assert "token" in result["error"].lower()


def test_run_happy_path() -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": [{"query_id": "q1"}, {"query_id": "q2"}]}
    mock_response.raise_for_status.return_value = None

    with patch("app.tools.SnowflakeQueryHistoryTool.httpx.post", return_value=mock_response):
        result = query_snowflake_history(
            account_identifier="acct123",
            token="tok",
            limit=10,
        )

    assert result["available"] is True
    assert result["total_returned"] == 2
    assert result["rows"][0]["query_id"] == "q1"


def test_run_http_error_returns_unavailable() -> None:
    with patch(
        "app.tools.SnowflakeQueryHistoryTool.httpx.post",
        side_effect=Exception("connection refused"),
    ):
        result = query_snowflake_history(account_identifier="acct123", token="tok")

    assert result["available"] is False
    assert "connection refused" in result["error"]


def test_run_respects_hard_limit() -> None:
    rows = [{"query_id": f"q{i}"} for i in range(300)]
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": rows}
    mock_response.raise_for_status.return_value = None

    with patch("app.tools.SnowflakeQueryHistoryTool.httpx.post", return_value=mock_response):
        result = query_snowflake_history(
            account_identifier="acct123",
            token="tok",
            limit=200,
            max_results=200,
        )

    assert result["total_returned"] <= 200


def test_run_passes_warehouse_and_role_in_payload() -> None:
    captured: list[dict] = []

    def fake_post(url, *, headers, json, timeout):
        captured.append(json)
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": []}
        mock_resp.raise_for_status.return_value = None
        return mock_resp

    with patch("app.tools.SnowflakeQueryHistoryTool.httpx.post", side_effect=fake_post):
        query_snowflake_history(
            account_identifier="acct123",
            token="tok",
            warehouse="COMPUTE_WH",
            role="SYSADMIN",
        )

    assert captured[0]["warehouse"] == "COMPUTE_WH"
    assert captured[0]["role"] == "SYSADMIN"
