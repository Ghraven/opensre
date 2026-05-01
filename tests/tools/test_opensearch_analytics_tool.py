"""Tests for OpenSearchAnalyticsTool."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.tools.OpenSearchAnalyticsTool import (
    _bounded_limit,
    _opensearch_available,
    _opensearch_extract_params,
    query_opensearch_analytics,
)


# ---------------------------------------------------------------------------
# _opensearch_available
# ---------------------------------------------------------------------------

def test_available_true_when_connection_verified_and_url() -> None:
    sources = {
        "opensearch": {"connection_verified": True, "url": "http://os.example.com"}
    }
    assert _opensearch_available(sources) is True


def test_available_false_without_connection_verified() -> None:
    sources = {"opensearch": {"url": "http://os.example.com"}}
    assert _opensearch_available(sources) is False


def test_available_false_without_url() -> None:
    sources = {"opensearch": {"connection_verified": True}}
    assert _opensearch_available(sources) is False


def test_available_false_no_opensearch_key() -> None:
    assert _opensearch_available({}) is False


# ---------------------------------------------------------------------------
# _opensearch_extract_params
# ---------------------------------------------------------------------------

def test_extract_params_maps_all_fields() -> None:
    sources = {
        "opensearch": {
            "url": " http://os.example.com ",
            "api_key": "apikey123",
            "index_pattern": "logs-*",
            "default_query": "error",
            "time_range_minutes": 120,
            "max_results": 75,
            "integration_id": "os-01",
        }
    }
    params = _opensearch_extract_params(sources)
    assert params["url"] == "http://os.example.com"
    assert params["api_key"] == "apikey123"
    assert params["index_pattern"] == "logs-*"
    assert params["query"] == "error"
    assert params["time_range_minutes"] == 120
    assert params["max_results"] == 75
    assert params["integration_id"] == "os-01"


def test_extract_params_defaults_index_pattern_to_wildcard() -> None:
    sources = {"opensearch": {"url": "http://os.example.com", "connection_verified": True}}
    params = _opensearch_extract_params(sources)
    assert params["index_pattern"] == "*"


def test_extract_params_defaults_query_to_wildcard() -> None:
    sources = {"opensearch": {"url": "http://os.example.com"}}
    params = _opensearch_extract_params(sources)
    assert params["query"] == "*"


# ---------------------------------------------------------------------------
# _bounded_limit
# ---------------------------------------------------------------------------

def test_bounded_limit_clamps_to_hard_limit() -> None:
    assert _bounded_limit(999, 100) == 100


def test_bounded_limit_minimum_one() -> None:
    assert _bounded_limit(0, 0) == 1


def test_bounded_limit_respects_max_results() -> None:
    assert _bounded_limit(20, 50) == 20


# ---------------------------------------------------------------------------
# query_opensearch_analytics — integration tests (ElasticsearchClient patched)
# ---------------------------------------------------------------------------

def test_run_returns_unavailable_when_url_missing() -> None:
    result = query_opensearch_analytics(url="")
    assert result["available"] is False
    assert "url" in result["error"].lower()


def test_run_happy_path() -> None:
    mock_client = MagicMock()
    mock_client.search_logs.return_value = {
        "success": True,
        "logs": [
            {"message": "disk full", "level": "error"},
            {"message": "service started", "level": "info"},
        ],
    }

    with patch(
        "app.tools.OpenSearchAnalyticsTool.ElasticsearchClient", return_value=mock_client
    ):
        result = query_opensearch_analytics(
            url="http://os.example.com",
            query="*",
            limit=50,
        )

    assert result["available"] is True
    assert result["total_returned"] == 2
    assert result["logs"][0]["message"] == "disk full"


def test_run_propagates_client_error() -> None:
    mock_client = MagicMock()
    mock_client.search_logs.return_value = {
        "success": False,
        "error": "index not found",
    }

    with patch(
        "app.tools.OpenSearchAnalyticsTool.ElasticsearchClient", return_value=mock_client
    ):
        result = query_opensearch_analytics(url="http://os.example.com")

    assert result["available"] is False
    assert "index not found" in result["error"]


def test_run_filters_non_dict_logs() -> None:
    mock_client = MagicMock()
    mock_client.search_logs.return_value = {
        "success": True,
        "logs": [{"msg": "ok"}, "not-a-dict", None],
    }

    with patch(
        "app.tools.OpenSearchAnalyticsTool.ElasticsearchClient", return_value=mock_client
    ):
        result = query_opensearch_analytics(url="http://os.example.com")

    assert result["total_returned"] == 1


def test_run_respects_hard_limit() -> None:
    logs = [{"level": "info"} for _ in range(300)]
    mock_client = MagicMock()
    mock_client.search_logs.return_value = {"success": True, "logs": logs}

    with patch(
        "app.tools.OpenSearchAnalyticsTool.ElasticsearchClient", return_value=mock_client
    ):
        result = query_opensearch_analytics(
            url="http://os.example.com",
            limit=200,
            max_results=200,
        )

    assert result["total_returned"] <= 200


def test_run_passes_config_to_client() -> None:
    captured_configs: list = []

    def fake_client(config):
        captured_configs.append(config)
        mock = MagicMock()
        mock.search_logs.return_value = {"success": True, "logs": []}
        return mock

    with patch(
        "app.tools.OpenSearchAnalyticsTool.ElasticsearchClient", side_effect=fake_client
    ):
        query_opensearch_analytics(
            url="http://os.example.com",
            api_key="key123",
            index_pattern="app-logs-*",
        )

    assert captured_configs[0].url == "http://os.example.com"
    assert captured_configs[0].api_key == "key123"
    assert captured_configs[0].index_pattern == "app-logs-*"
