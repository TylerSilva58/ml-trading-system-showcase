"""
gate_optimizer.py — Adaptive entry threshold tuning

Part of the Overdrive adaptive feedback layer.

The GateOptimizer monitors rolling win rate and adjusts the minimum ML score
threshold required to enter a trade. When the bot is performing well, the gate
relaxes to capture more opportunities. When performance degrades, it tightens
to reduce exposure until conditions improve.

Proprietary signal logic and exact threshold curves are excluded from this file.
"""

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class GateOptimizerConfig:
    """Configuration for the adaptive gate optimizer."""

    # Rolling window size for win rate calculation
    window_size: int = 20

    # Min/max allowable gate thresholds
    gate_min: float = 0.60
    gate_max: float = 0.95

    # Starting threshold
    gate_initial: float = 0.70

    # Win rate targets that trigger gate adjustments
    target_win_rate: float = 0.50
    circuit_breaker_win_rate: float = 0.30  # Pause entries below this

    # How aggressively to adjust (0–1)
    adjustment_sensitivity: float = 0.05


@dataclass
class TradeOutcome:
    trade_id: str
    won: bool
    score: float
    timestamp: float = field(default_factory=time.time)


class GateOptimizer:
    """
    Maintains a rolling window of recent trade outcomes and adjusts
    the entry score threshold to target a stable win rate.

    Example usage:
        optimizer = GateOptimizer(GateOptimizerConfig())
        optimizer.record_outcome(trade_id="abc", won=True, score=0.87)
        gate = optimizer.current_gate
        if score >= gate:
            # proceed with trade
    """

    def __init__(self, config: Optional[GateOptimizerConfig] = None):
        self.config = config or GateOptimizerConfig()
        self._outcomes: deque[TradeOutcome] = deque(maxlen=self.config.window_size)
        self._gate = self.config.gate_initial
        self._circuit_broken = False

    @property
    def current_gate(self) -> float:
        return self._gate

    @property
    def circuit_broken(self) -> bool:
        return self._circuit_broken

    @property
    def rolling_win_rate(self) -> Optional[float]:
        if not self._outcomes:
            return None
        return sum(1 for o in self._outcomes if o.won) / len(self._outcomes)

    def record_outcome(self, trade_id: str, won: bool, score: float) -> None:
        """Record the result of a closed trade and update the gate."""
        self._outcomes.append(TradeOutcome(trade_id=trade_id, won=won, score=score))
        self._recompute()

    def _recompute(self) -> None:
        """Recompute gate threshold based on recent performance."""
        win_rate = self.rolling_win_rate
        if win_rate is None:
            return

        # Circuit breaker: pause all entries if win rate collapses
        self._circuit_broken = win_rate < self.config.circuit_breaker_win_rate

        # Adjust gate proportionally to deviation from target
        # (exact curve is proprietary — this shows the structure only)
        deviation = self.config.target_win_rate - win_rate
        adjustment = deviation * self.config.adjustment_sensitivity

        self._gate = max(
            self.config.gate_min,
            min(self.config.gate_max, self._gate + adjustment),
        )

    def status(self) -> dict:
        return {
            "gate": round(self._gate, 4),
            "win_rate": round(self.rolling_win_rate or 0, 4),
            "circuit_broken": self._circuit_broken,
            "sample_size": len(self._outcomes),
        }
