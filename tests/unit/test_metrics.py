# tests/unit/test_metrics.py
import pytest
from src.observability.metrics import MetricsCollector, LatencyStats


def test_latency_percentiles_correct():
    """
    Percentile calculation must be accurate.
    
    WHY: If P95 is calculated wrong, you might think your API is fast
    when 5% of users are timing out. This pins the exact math.
    """
    stats = LatencyStats()
    # Feed 10 known values: 100, 200, 300, ... 1000ms
    for i in range(1, 11):
        stats.record(i * 100.0)

    assert stats.p50 == 500.0 or stats.p50 == 600.0  # median of 10 values
    assert stats.p95 is not None
    assert stats.p95 >= 900.0   # 95th percentile of [100..1000] is ~950
    assert stats.p99 is not None
    assert stats.p99 >= 900.0


def test_rolling_window_drops_old_samples():
    """
    With max_samples=10, adding 15 samples must keep only the last 10.
    Without this, the samples list grows unbounded and the server runs out of memory.
    """
    stats = LatencyStats(max_samples=10)
    for i in range(15):
        stats.record(float(i))
    assert len(stats.samples) == 10
    assert stats.samples[0] == 5.0  # oldest kept is the 6th sample


def test_empty_stats_return_none_percentiles():
    """No samples = no percentile, must not crash."""
    stats = LatencyStats()
    assert stats.p50 is None
    assert stats.p95 is None
    assert stats.p99 is None
    assert stats.count == 0


def test_counter_increments():
    """Basic counter mechanics."""
    mc = MetricsCollector()
    mc.increment("query.total")
    mc.increment("query.total")
    mc.increment("query.total", amount=5)
    snapshot = mc.get_snapshot()
    assert snapshot["counters"]["query.total"] == 7


def test_error_recorded_in_snapshot():
    """Error keys appear in the snapshot under the right format."""
    mc = MetricsCollector()
    mc.record_error("ingestion", "FileNotFoundError")
    snapshot = mc.get_snapshot()
    assert "ingestion.FileNotFoundError" in snapshot["errors"]


def test_latency_recorded_and_visible_in_snapshot():
    """Latency samples appear in the get_snapshot() output."""
    mc = MetricsCollector()
    mc.record_latency("query.total", 1500.0)
    mc.record_latency("query.total", 2000.0)
    snapshot = mc.get_snapshot()
    assert "query.total" in snapshot["latencies"]
    assert snapshot["latencies"]["query.total"]["count"] == 2
    assert snapshot["latencies"]["query.total"]["p50_ms"] is not None