"""
performance_tracker.py — Rolling multi-window performance metrics

Tracks PnL, win rate, trade counts, and regime signals across
multiple rolling time windows: 1h, 6h, 24h, and 7d.

Used by the Overdrive layer to feed the GateOptimizer, RegimeDetector,
and dashboard visualisations.
"""

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional


WINDOWS = {
    "1h": 3600,
    "6h": 21600,
    "24h": 86400,
    "7d": 604800,
}


@dataclass
class ClosedTrade:
    trade_id: str
    pnl: float
    won: bool
    bucket: str
    score: float
    hold_seconds: float
    closed_at: float = field(default_factory=time.time)


class PerformanceTracker:
    """
    Maintains a time-ordered deque of closed trades and provides
    windowed performance snapshots on demand.

    Thread-safety: not thread-safe; use a single async task or add a lock.

    Example:
        tracker = PerformanceTracker()
        tracker.record(ClosedTrade("t1", pnl=0.002, won=True, bucket="TRENCH",
                                   score=0.88, hold_seconds=112))
        print(tracker.snapshot("1h"))
    """

    def __init__(self, max_history: int = 10_000):
        self._trades: deque[ClosedTrade] = deque(maxlen=max_history)

    def record(self, trade: ClosedTrade) -> None:
        self._trades.append(trade)

    def snapshot(self, window: str = "24h") -> dict:
        """
        Return performance metrics for the given rolling window.
        window: one of "1h", "6h", "24h", "7d"
        """
        if window not in WINDOWS:
            raise ValueError(f"Unknown window: {window}. Choose from {list(WINDOWS)}")

        cutoff = time.time() - WINDOWS[window]
        relevant = [t for t in self._trades if t.closed_at >= cutoff]

        if not relevant:
            return self._empty_snapshot(window)

        wins = [t for t in relevant if t.won]
        pnls = [t.pnl for t in relevant]
        scores = [t.score for t in relevant]

        return {
            "window": window,
            "trades": len(relevant),
            "wins": len(wins),
            "win_rate": round(len(wins) / len(relevant), 4),
            "total_pnl": round(sum(pnls), 6),
            "avg_pnl": round(sum(pnls) / len(pnls), 6),
            "avg_score": round(sum(scores) / len(scores), 4),
            "avg_hold_s": round(
                sum(t.hold_seconds for t in relevant) / len(relevant), 1
            ),
            "by_bucket": self._by_bucket(relevant),
        }

    def _by_bucket(self, trades: list[ClosedTrade]) -> dict:
        buckets: dict[str, list[ClosedTrade]] = {}
        for t in trades:
            buckets.setdefault(t.bucket, []).append(t)
        return {
            bucket: {
                "trades": len(ts),
                "win_rate": round(sum(1 for t in ts if t.won) / len(ts), 4),
                "total_pnl": round(sum(t.pnl for t in ts), 6),
            }
            for bucket, ts in buckets.items()
        }

    @staticmethod
    def _empty_snapshot(window: str) -> dict:
        return {
            "window": window,
            "trades": 0,
            "wins": 0,
            "win_rate": None,
            "total_pnl": 0.0,
            "avg_pnl": None,
            "avg_score": None,
            "avg_hold_s": None,
            "by_bucket": {},
        }

    def all_windows(self) -> dict[str, dict]:
        return {w: self.snapshot(w) for w in WINDOWS}
