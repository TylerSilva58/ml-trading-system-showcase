"""
ab_engine.py — Live A/B experiment infrastructure

Part of the Overdrive adaptive feedback layer.

Runs controlled split experiments on real production trades. Each experiment
assigns incoming trades to a variant, tracks outcomes in SQLite, and supports
auto-promotion when a variant significantly outperforms control.

This file shows the infrastructure pattern. Proprietary variant logic is excluded.
"""

import sqlite3
import hashlib
import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class Experiment:
    name: str
    control_label: str
    variant_label: str
    traffic_split: float  # 0.0–1.0, fraction assigned to variant
    active: bool = True
    created_at: float = 0.0

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.time()


class ABEngine:
    """
    Lightweight A/B experiment engine backed by SQLite.

    Assignments are deterministic per trade_id (hash-based), so re-querying
    the same trade always returns the same variant — no state needed at runtime.

    Example:
        engine = ABEngine("analytics.sqlite")
        engine.create_experiment(Experiment(
            name="auto_tighter_gate",
            control_label="control",
            variant_label="tighter",
            traffic_split=0.5,
        ))

        variant = engine.assign("trade_abc123", "auto_tighter_gate")
        # → "tighter" or "control"

        engine.record_result("trade_abc123", "auto_tighter_gate", pnl=-0.002)
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS ab_experiments (
                    name TEXT PRIMARY KEY,
                    control_label TEXT NOT NULL,
                    variant_label TEXT NOT NULL,
                    traffic_split REAL NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS ab_assignments (
                    trade_id TEXT NOT NULL,
                    experiment TEXT NOT NULL,
                    variant TEXT NOT NULL,
                    assigned_at REAL NOT NULL,
                    pnl REAL,
                    won INTEGER,
                    PRIMARY KEY (trade_id, experiment)
                );
            """)

    def create_experiment(self, experiment: Experiment) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO ab_experiments
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    experiment.name,
                    experiment.control_label,
                    experiment.variant_label,
                    experiment.traffic_split,
                    int(experiment.active),
                    experiment.created_at,
                ),
            )

    def assign(self, trade_id: str, experiment_name: str) -> Optional[str]:
        """
        Deterministically assign a trade to a variant.
        Returns the variant label, or None if experiment is inactive.
        """
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT control_label, variant_label, traffic_split, active "
                "FROM ab_experiments WHERE name = ?",
                (experiment_name,),
            ).fetchone()

        if not row or not row[3]:
            return None

        control_label, variant_label, split, _ = row

        # Hash-based deterministic assignment
        digest = hashlib.md5(f"{trade_id}:{experiment_name}".encode()).hexdigest()
        bucket = int(digest[:8], 16) / 0xFFFFFFFF  # 0.0–1.0

        assigned = variant_label if bucket < split else control_label

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR IGNORE INTO ab_assignments
                   (trade_id, experiment, variant, assigned_at)
                   VALUES (?, ?, ?, ?)""",
                (trade_id, experiment_name, assigned, time.time()),
            )

        return assigned

    def record_result(
        self, trade_id: str, experiment_name: str, pnl: float
    ) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """UPDATE ab_assignments SET pnl = ?, won = ?
                   WHERE trade_id = ? AND experiment = ?""",
                (pnl, int(pnl > 0), trade_id, experiment_name),
            )

    def summary(self, experiment_name: str) -> dict:
        """Return per-variant performance summary for an experiment."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """SELECT variant,
                          COUNT(*) as trades,
                          AVG(CASE WHEN won = 1 THEN 1.0 ELSE 0.0 END) as win_rate,
                          SUM(pnl) as total_pnl,
                          AVG(pnl) as avg_pnl
                   FROM ab_assignments
                   WHERE experiment = ? AND pnl IS NOT NULL
                   GROUP BY variant""",
                (experiment_name,),
            ).fetchall()

        return {
            row[0]: {
                "trades": row[1],
                "win_rate": round(row[2] or 0, 4),
                "total_pnl": round(row[3] or 0, 6),
                "avg_pnl": round(row[4] or 0, 6),
            }
            for row in rows
        }
