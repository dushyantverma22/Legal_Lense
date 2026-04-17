# src/observability/metrics.py
import time
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional
import structlog

log = structlog.get_logger()


@dataclass
class LatencyStats:
    """
    Tracks latency samples and computes percentile approximations.
    
    WHY NOT USE statistics.quantiles?
    It requires the full list, which grows unbounded in production.
    This implementation keeps only the last N samples per endpoint —
    enough for meaningful percentiles without memory leaks.
    """
    samples: list[float] = field(default_factory=list)
    max_samples: int = 1000   # rolling window

    def record(self, ms: float) -> None:
        self.samples.append(ms)
        if len(self.samples) > self.max_samples:
            self.samples = self.samples[-self.max_samples:]

    def percentile(self, p: float) -> Optional[float]:
        if not self.samples:
            return None
        sorted_s = sorted(self.samples)
        idx = int(len(sorted_s) * p / 100)
        return round(sorted_s[min(idx, len(sorted_s) - 1)], 1)

    @property
    def p50(self) -> Optional[float]:
        return self.percentile(50)

    @property
    def p95(self) -> Optional[float]:
        return self.percentile(95)

    @property
    def p99(self) -> Optional[float]:
        return self.percentile(99)

    @property
    def count(self) -> int:
        return len(self.samples)


class MetricsCollector:
    """
    Thread-safe in-process metrics store.
    
    CONCEPT: Why in-process first?
    External metrics services (Prometheus, CloudWatch) add network latency
    to every request if you push synchronously. In-process collection is
    zero latency — you record to memory, then flush to external systems
    asynchronously (background thread or on-shutdown).
    
    This gives you the same data locally that you'll eventually see in
    CloudWatch, letting you debug without AWS credentials.
    
    THREAD SAFETY: A threading.Lock protects the shared dicts.
    FastAPI uses a thread pool for asyncio.to_thread() calls, so
    multiple threads can call record_* simultaneously.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._latencies: dict[str, LatencyStats] = defaultdict(LatencyStats)
        self._counters: dict[str, int] = defaultdict(int)
        self._errors: dict[str, int] = defaultdict(int)

    def record_latency(self, operation: str, latency_ms: float) -> None:
        """Record a latency sample for an operation."""
        with self._lock:
            self._latencies[operation].record(latency_ms)

    def increment(self, counter: str, amount: int = 1) -> None:
        """Increment a named counter."""
        with self._lock:
            self._counters[counter] += amount

    def record_error(self, operation: str, error_type: str) -> None:
        """Record an error occurrence."""
        with self._lock:
            key = f"{operation}.{error_type}"
            self._errors[key] += 1
        log.warning("error_recorded", operation=operation, error_type=error_type)

    def get_snapshot(self) -> dict:
        """
        Returns a point-in-time snapshot of all metrics.
        Used by GET /metrics endpoint and periodic CloudWatch flush.
        """
        with self._lock:
            latency_snapshot = {}
            for op, stats in self._latencies.items():
                latency_snapshot[op] = {
                    "p50_ms": stats.p50,
                    "p95_ms": stats.p95,
                    "p99_ms": stats.p99,
                    "count": stats.count,
                }

            return {
                "latencies": latency_snapshot,
                "counters": dict(self._counters),
                "errors": dict(self._errors),
            }

    def log_snapshot(self) -> None:
        """Emit the current snapshot as a structured log line."""
        snapshot = self.get_snapshot()
        log.info("metrics_snapshot", **snapshot)


# Module-level singleton — one collector for the whole process
metrics = MetricsCollector()