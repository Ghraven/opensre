"""Shutdown and post-shutdown safety tests for Analytics.

Covers:
- shutdown() is idempotent (safe to call twice)
- capture() after shutdown is a silent no-op — no exception, no queue work
- shutdown_analytics() when singleton was never initialized is safe

See: https://github.com/Tracer-Cloud/opensre/issues/1120
"""

from __future__ import annotations

import threading
from unittest.mock import patch

import pytest

from app.analytics.provider import Analytics, shutdown_analytics
from app.analytics.events import Event


class TestAnalyticsShutdownIdempotent:
    """shutdown() must be safe to call multiple times."""

    def test_double_shutdown_does_not_raise(self) -> None:
        analytics = Analytics()
        analytics.shutdown(flush=False)
        analytics.shutdown(flush=False)  # second call must not raise

    def test_shutdown_sets_shutdown_flag(self) -> None:
        analytics = Analytics()
        analytics.shutdown(flush=False)
        assert analytics._shutdown is True

    def test_triple_shutdown_still_safe(self) -> None:
        analytics = Analytics()
        for _ in range(3):
            analytics.shutdown(flush=False)


class TestCaptureAfterShutdown:
    """capture() after shutdown must be a silent no-op."""

    def test_capture_after_shutdown_does_not_raise(self) -> None:
        analytics = Analytics()
        analytics.shutdown(flush=False)
        # Must not raise
        analytics.capture(Event.INSTALL_DETECTED)

    def test_capture_after_shutdown_does_not_queue_work(self) -> None:
        analytics = Analytics()
        analytics.shutdown(flush=False)
        size_before = analytics._queue.qsize()
        analytics.capture(Event.INSTALL_DETECTED)
        assert analytics._queue.qsize() == size_before, (
            "capture() after shutdown should not add items to the queue"
        )

    def test_capture_after_shutdown_does_not_start_worker(self) -> None:
        analytics = Analytics()
        analytics.shutdown(flush=False)
        worker_before = analytics._worker
        analytics.capture(Event.INSTALL_DETECTED)
        assert analytics._worker is worker_before, (
            "capture() after shutdown should not spawn a new worker thread"
        )

    def test_multiple_captures_after_shutdown_all_no_ops(self) -> None:
        analytics = Analytics()
        analytics.shutdown(flush=False)
        for _ in range(5):
            analytics.capture(Event.INSTALL_DETECTED)


class TestShutdownAnalyticsSingleton:
    """shutdown_analytics() must be safe even when singleton is uninitialised."""

    def test_shutdown_analytics_when_never_initialized_does_not_raise(self) -> None:
        import app.analytics.provider as prov
        original = prov._ANALYTICS
        try:
            prov._ANALYTICS = None  # simulate un-initialized singleton
            shutdown_analytics(flush=False)  # must not raise
        finally:
            prov._ANALYTICS = original

    def test_shutdown_analytics_called_twice_does_not_raise(self) -> None:
        analytics = Analytics()
        import app.analytics.provider as prov
        original = prov._ANALYTICS
        try:
            prov._ANALYTICS = analytics
            shutdown_analytics(flush=False)
            shutdown_analytics(flush=False)
        finally:
            prov._ANALYTICS = original
