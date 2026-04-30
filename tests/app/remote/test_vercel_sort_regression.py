"""Regression tests for _sort_deployment_stubs_newest_first with bad timestamps.

Covers:
- Missing created_at field
- Empty string created_at
- Whitespace-only created_at
- Mix of valid and invalid entries in the same list
- Entries without IDs are filtered out
- Valid deployment IDs are preserved

See: https://github.com/Tracer-Cloud/opensre/issues/1121
"""

from __future__ import annotations

import pytest

from app.remote.vercel_poller import _sort_deployment_stubs_newest_first


def _stub(uid: str, created_at: str | None = "2024-01-15T10:00:00Z") -> dict:
    """Build a minimal deployment stub dict."""
    d: dict = {"uid": uid}
    if created_at is not None:
        d["created"] = created_at
    return d


class TestSortDeploymentStubsNewestFirst:
    """_sort_deployment_stubs_newest_first must not raise on malformed payloads."""

    def test_sorts_valid_entries_newest_first(self) -> None:
        stubs = [
            _stub("old", "2024-01-01T00:00:00Z"),
            _stub("new", "2024-06-01T00:00:00Z"),
            _stub("mid", "2024-03-01T00:00:00Z"),
        ]
        result = _sort_deployment_stubs_newest_first(stubs)
        ids = [s["uid"] for s in result]
        assert ids == ["new", "mid", "old"]

    def test_missing_created_at_does_not_raise(self) -> None:
        stubs = [
            _stub("valid", "2024-06-01T00:00:00Z"),
            _stub("no-date", created_at=None),  # key absent
        ]
        result = _sort_deployment_stubs_newest_first(stubs)
        # Valid entry should still appear
        valid_ids = [s.get("uid") for s in result if s.get("uid") == "valid"]
        assert valid_ids == ["valid"]

    def test_empty_created_at_does_not_raise(self) -> None:
        stubs = [
            _stub("valid", "2024-06-01T00:00:00Z"),
            _stub("empty-date", ""),
        ]
        result = _sort_deployment_stubs_newest_first(stubs)
        assert any(s.get("uid") == "valid" for s in result)

    def test_whitespace_only_created_at_does_not_raise(self) -> None:
        stubs = [
            _stub("valid", "2024-06-01T00:00:00Z"),
            _stub("whitespace-date", "   "),
        ]
        result = _sort_deployment_stubs_newest_first(stubs)
        assert any(s.get("uid") == "valid" for s in result)

    def test_mix_of_valid_and_invalid_entries(self) -> None:
        stubs = [
            _stub("a", "2024-01-01T00:00:00Z"),
            _stub("b", ""),             # empty
            _stub("c", "2024-12-01T00:00:00Z"),
            _stub("d", created_at=None),  # missing
            _stub("e", "   "),          # whitespace
        ]
        result = _sort_deployment_stubs_newest_first(stubs)
        # Valid entries with IDs must be preserved
        valid_ids = [s.get("uid") for s in result if s.get("uid") in ("a", "c")]
        assert set(valid_ids) == {"a", "c"}

    def test_entry_without_uid_is_filtered_out(self) -> None:
        stubs = [
            {"created": "2024-06-01T00:00:00Z"},   # no uid key
            _stub("valid", "2024-03-01T00:00:00Z"),
        ]
        result = _sort_deployment_stubs_newest_first(stubs)
        ids = [s.get("uid") for s in result]
        assert "valid" in ids
        assert None not in ids  # entry without uid should not appear

    def test_all_invalid_returns_empty_or_no_raise(self) -> None:
        stubs = [
            _stub("a", ""),
            _stub("b", "   "),
            _stub("c", created_at=None),
        ]
        # Should not raise regardless of output
        result = _sort_deployment_stubs_newest_first(stubs)
        assert isinstance(result, list)
