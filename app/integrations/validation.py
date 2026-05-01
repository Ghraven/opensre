"""Early-exit validation helpers for integration and LLM provider availability.

Guards added at the integration resolution boundary so the investigation
pipeline fails fast when a required vendor integration or LLM provider is
absent, rather than propagating the missing-credential error deep into the
planning or evidence-collection stages.
"""

from __future__ import annotations

import os
from typing import Any

# Sources that map 1:1 to an integration key in resolved_integrations.
# Internal / canonical sources (opensre_dataset, openrca_dataset, opensre) are
# NOT listed here — they never require a vendor integration.
_ALERT_SOURCE_TO_INTEGRATION: dict[str, str] = {
    "datadog": "datadog",
    "grafana": "grafana",
    "cloudwatch": "aws",
    "aws": "aws",
    "sentry": "sentry",
    "betterstack": "betterstack",
    "honeycomb": "honeycomb",
    "coralogix": "coralogix",
    "alertmanager": "alertmanager",
    "splunk": "splunk",
    "openobserve": "openobserve",
    "opensearch": "opensearch",
    "clickhouse": "clickhouse",
    "kafka": "kafka",
    "argocd": "argocd",
    "vercel": "vercel",
    "prefect": "prefect",
    "airflow": "airflow",
    "prometheus": "grafana",
}

# LLM provider API key environment variable names.
_LLM_API_KEY_ENV_VARS: tuple[str, ...] = (
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
    "GEMINI_API_KEY",
    "NVIDIA_API_KEY",
    "MINIMAX_API_KEY",
)

# Providers that don't require an API key (credentials come from the env or
# from the system keychain via resolve_llm_api_key; Bedrock uses AWS creds).
_KEYLESS_LLM_PROVIDERS: frozenset[str] = frozenset({"ollama", "bedrock"})


def missing_required_integration(
    alert_source: str,
    resolved_integrations: dict[str, Any],
) -> str | None:
    """Return an error message when *alert_source* maps to an unconfigured integration.

    Returns ``None`` when:
    - the alert source is unknown or internal (no vendor integration required), or
    - the required integration is present in *resolved_integrations*.
    """
    source = (alert_source or "").strip().lower()
    required = _ALERT_SOURCE_TO_INTEGRATION.get(source)
    if required is None:
        return None
    if resolved_integrations.get(required):
        return None
    return (
        f"Alert source '{source}' requires the '{required}' integration, "
        f"but it is not configured. Run 'opensre integrations setup' to connect it."
    )


def is_llm_provider_configured() -> bool:
    """Return True when at least one LLM provider credential is available.

    Checks environment variables for API-key-based providers and also accepts
    keyless providers (Ollama, Bedrock) when explicitly selected via
    ``LLM_PROVIDER``.
    """
    provider = os.getenv("LLM_PROVIDER", "anthropic").strip().lower() or "anthropic"
    if provider in _KEYLESS_LLM_PROVIDERS:
        return True
    for env_var in _LLM_API_KEY_ENV_VARS:
        if os.getenv(env_var, "").strip():
            return True
    return False
