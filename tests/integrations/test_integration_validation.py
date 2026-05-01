"""Tests for app/integrations/validation.py."""

from __future__ import annotations

import os
from unittest.mock import patch

from app.integrations.validation import is_llm_provider_configured, missing_required_integration


# ---------------------------------------------------------------------------
# missing_required_integration
# ---------------------------------------------------------------------------

def test_returns_none_for_unknown_source() -> None:
    assert missing_required_integration("my_custom_source", {}) is None


def test_returns_none_for_empty_source() -> None:
    assert missing_required_integration("", {}) is None


def test_returns_none_for_internal_opensre_source() -> None:
    assert missing_required_integration("opensre_dataset", {}) is None
    assert missing_required_integration("openrca_dataset", {}) is None
    assert missing_required_integration("opensre", {}) is None


def test_returns_error_when_datadog_integration_absent() -> None:
    error = missing_required_integration("datadog", {})
    assert error is not None
    assert "datadog" in error.lower()


def test_returns_none_when_datadog_integration_present() -> None:
    resolved = {"datadog": {"connection_verified": True, "api_key": "dd-key"}}
    assert missing_required_integration("datadog", resolved) is None


def test_returns_error_when_grafana_absent() -> None:
    assert missing_required_integration("grafana", {}) is not None


def test_returns_none_when_grafana_present() -> None:
    assert missing_required_integration("grafana", {"grafana": {"url": "http://g.example.com"}}) is None


def test_cloudwatch_maps_to_aws_integration() -> None:
    error = missing_required_integration("cloudwatch", {})
    assert error is not None
    assert "aws" in error.lower()


def test_cloudwatch_satisfied_by_aws_key() -> None:
    assert missing_required_integration("cloudwatch", {"aws": {"region": "us-east-1"}}) is None


def test_case_insensitive_source_matching() -> None:
    assert missing_required_integration("Datadog", {}) is not None
    assert missing_required_integration("DATADOG", {}) is not None


def test_returns_none_for_all_known_vendor_sources_when_resolved() -> None:
    vendors = [
        ("sentry", "sentry"),
        ("betterstack", "betterstack"),
        ("honeycomb", "honeycomb"),
        ("coralogix", "coralogix"),
        ("alertmanager", "alertmanager"),
        ("splunk", "splunk"),
        ("openobserve", "openobserve"),
        ("opensearch", "opensearch"),
        ("clickhouse", "clickhouse"),
        ("kafka", "kafka"),
        ("argocd", "argocd"),
        ("vercel", "vercel"),
        ("prefect", "prefect"),
        ("airflow", "airflow"),
    ]
    for source, integration in vendors:
        resolved = {integration: {"connection_verified": True}}
        assert missing_required_integration(source, resolved) is None, source


# ---------------------------------------------------------------------------
# is_llm_provider_configured
# ---------------------------------------------------------------------------

def test_returns_true_when_anthropic_key_set() -> None:
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test", "LLM_PROVIDER": "anthropic"}):
        assert is_llm_provider_configured() is True


def test_returns_true_when_openai_key_set() -> None:
    env = {"OPENAI_API_KEY": "sk-test", "LLM_PROVIDER": "openai"}
    with patch.dict(os.environ, env, clear=False):
        assert is_llm_provider_configured() is True


def test_returns_false_when_no_key_and_api_provider() -> None:
    clean = {k: "" for k in (
        "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY",
        "GEMINI_API_KEY", "NVIDIA_API_KEY", "MINIMAX_API_KEY",
    )}
    clean["LLM_PROVIDER"] = "anthropic"
    with patch.dict(os.environ, clean, clear=False):
        assert is_llm_provider_configured() is False


def test_returns_true_for_ollama_provider_without_key() -> None:
    with patch.dict(os.environ, {"LLM_PROVIDER": "ollama"}, clear=False):
        assert is_llm_provider_configured() is True


def test_returns_true_for_bedrock_provider_without_key() -> None:
    with patch.dict(os.environ, {"LLM_PROVIDER": "bedrock"}, clear=False):
        assert is_llm_provider_configured() is True


def test_defaults_to_anthropic_when_llm_provider_unset() -> None:
    clean = {k: "" for k in (
        "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY",
        "GEMINI_API_KEY", "NVIDIA_API_KEY", "MINIMAX_API_KEY",
        "LLM_PROVIDER",
    )}
    with patch.dict(os.environ, clean, clear=False):
        assert is_llm_provider_configured() is False
