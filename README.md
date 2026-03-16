# PumpBot — Solana Meme Coin Trading Bot

> A production-grade algorithmic trading system built for Pump.fun's meme coin markets on Solana. This repo showcases the system architecture, engineering decisions, and performance analytics — proprietary signal logic is excluded.

---

## Performance Snapshot (March 9–16, 2026)

| Metric | Value |
|---|---|
| Total trades executed | **2,067** |
| Overall win rate | **44.5%** (50% day 1 → adaptive tuning in progress) |
| Avg hold time | **107.8 seconds** |
| Best single trade | **+0.435 SOL** |
| Market | Solana meme coins — 2 market buckets |
| Circuit breaker | Fires at <30% win rate over last 20 trades |
| A/B experiment result | `auto_tighter_gate` variant cut avg loss **8×** vs control |

> Note: The bot is actively learning. The gate optimizer raised the entry threshold from 0.665 → 0.830 during this period in response to declining win rate. A retrain on 264 newly closed trades is queued.

---

## System Architecture

The bot is structured as **7 independently evolvable layers**, each with a clearly defined interface:

```
┌─────────────────────────────────────────────────────┐
│  DATA LAYER                                         │
│  PumpPortal WebSocket · Solana RPC · Jupiter API    │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│  SIGNAL PIPELINE                                    │
│  39 features: market/flow, social/sentiment,        │
│  on-chain quality, wallet fingerprinting            │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│  ML SCORING — FlameLearner                          │
│  Two XGBoost classifiers (one per market bucket)    │
│  Calibrated probability scores 0 → 1               │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│  RISK ENGINE                                        │
│  Rug shield · Dev wallet registry                   │
│  Adaptive gate · Dual circuit breakers              │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│  POSITION MANAGER                                   │
│  TP ladder · Trailing stop · Time stop              │
│  Signal decay · Dynamic position sizing             │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│  EXECUTION — Jupiter Aggregator                     │
│  Live swap · Dry-run mode · TX state tracking       │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│  OVERDRIVE — Adaptive Feedback Loop                 │
│  Regime detector · Gate optimizer · A/B engine      │
│  Auto-retrain scheduler · 3.8M event journal        │
└─────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Category | Tools |
|---|---|
| **Language** | Python 3.11 — fully async (`asyncio`) |
| **ML** | XGBoost 2.0, scikit-learn 1.3 (calibration, pipelines) |
| **Data** | pandas 2.0, numpy 1.24 |
| **Blockchain** | solders 0.20, solana-py 0.34 |
| **DEX execution** | Jupiter Aggregator API |
| **Realtime data** | PumpPortal WebSocket, Solana RPC WebSocket |
| **Networking** | aiohttp 3.9, websockets 12 |
| **Storage** | SQLite (WAL mode) — trade journal + analytics DB |
| **Config** | python-dotenv, PyYAML, runtime YAML overrides |
| **Frontend** | Vanilla HTML/JS dashboard + Vite mobile client |
| **Deployment** | systemd (2 services), nginx reverse proxy, UFW firewall |
| **Infra** | Ubuntu 24.04 LTS (DigitalOcean) |
| **Testing** | Python `unittest` — 10 test files, temp SQLite fixtures |

---

## What Makes This Technically Interesting

### 1. Full ML lifecycle in production
Not just "runs a model." The bot collects data from live trade outcomes, builds a labeled dataset, trains XGBoost classifiers, runs offline eval, deploys, and **auto-retrains on a schedule** — all self-contained.

### 2. Bucket-specific feature engineering
The market is split into two segments with different risk/reward profiles:

- **TRENCH** — tokens under $10k mcap, age < 45 minutes. Features include `trench_bounce_strength`, `trench_reversal_confirmation`, and early wallet clustering.
- **MIGRATED_NEW** — tokens that graduated to Raydium, mcap < $750k, age < 168h. Features include `migrated_freshness` and `migrated_holder_growth`.

Each bucket has its own XGBoost classifier, separate score threshold, and independent circuit breaker logic.

### 3. Adaptive feedback loops (Overdrive)
The bot tunes itself at runtime without redeployment:
- `GateOptimizer` raises/lowers the minimum ML score threshold based on rolling win rate
- `PositionSizer` adjusts trade size based on detected market regime
- Win-rate circuit breaker pauses entries if last-20-trades win rate drops below 30%
- Drawdown circuit breaker fires if 2-hour PnL drops below -0.50 SOL

### 4. Live A/B infrastructure
Real split experiments run on production trades. Assignment is tracked in SQLite. Auto-promotion logic and a CLI manage the experiment lifecycle — the same pattern used at large ML companies, applied here at meme coin scale. In the first week, the `auto_tighter_gate` variant reduced average loss per trade from -0.0156 SOL to -0.0019 SOL (8× improvement on a 102-trade sample).

### 5. Multi-signal score fusion
Every entry decision combines:
- XGBoost ML score (primary)
- Momentum scorer
- Narrative scorer (social velocity from X/Telegram)
- On-chain features
- Wallet quality fingerprint

These are fused into a single `signal_alignment_score` before hitting the risk engine.

### 6. Sub-2-minute median hold with partial exits
The position manager coordinates TP ladders with partial closes, trailing stops that activate after a threshold gain, time stops, and signal decay — all in real time on Solana mainnet with median trade duration of **107.8 seconds**.

### 7. Event journal at scale
3.8 million structured events captured in 7 days from a single async Python process — `entry_decision`, `trade_open`, `trade_partial`, `trade_close` — stored efficiently in SQLite WAL mode (~542k events/day).

---

## Repository Structure

```
pumpbot-showcase/
├── README.md
├── architecture/
│   └── system_diagram.svg          # Full pipeline diagram
├── signal_pipeline/
│   ├── pipeline.py                 # SignalFrame construction (sanitized)
│   └── feature_reference.md        # All 39 features documented
├── model/
│   ├── flame_learner.py            # XGBoost wrapper — train/predict/reload
│   └── dataset_builder.py          # Label generation from trade journal
├── engine/
│   ├── risk_engine.py              # BUY/SELL/HOLD/SKIP decision logic (stub)
│   └── position_manager.py         # Exit ladder logic (stub)
├── overdrive/
│   ├── gate_optimizer.py           # Adaptive threshold tuning
│   ├── regime_detector.py          # Market regime classification
│   ├── ab_engine.py                # A/B experiment infrastructure
│   └── retrain_scheduler.py        # Auto-retrain on new closed trades
├── analytics/
│   └── performance_tracker.py      # Rolling 1h/6h/24h/7d metrics
├── tests/
│   ├── test_overdrive.py
│   ├── test_flame_learner.py
│   ├── test_flame_dataset.py
│   └── test_offline_eval.py
└── deploy/
    ├── deploy.sh                   # One-command Ubuntu 24.04 setup
    └── pumpbot.service             # systemd unit file (example)
```

---

## Testing Approach

Tests use **real SQLite databases** (not mocks) and `unittest.mock.patch` for external dependencies, making them integration-style rather than purely unit tests.

| Test file | Coverage |
|---|---|
| `test_overdrive.py` | PerformanceTracker, RegimeDetector, GateOptimizer, PositionSizer, A/B engine |
| `test_flame_learner.py` | XGBoost train/predict/reload lifecycle |
| `test_flame_dataset.py` | Feature pipeline and dataset builder |
| `test_flame_acceptance.py` | End-to-end model acceptance gates |
| `test_offline_eval.py` | Offline evaluation metrics |
| `test_executor.py` | Jupiter execution layer |
| `test_action_priority.py` | Risk engine action priority |

---

## Deployment

A single command provisions a fresh Ubuntu 24.04 server:

```bash
sudo bash deploy.sh
```

This creates an isolated `pumpbot` system user, sets up a Python 3.11 venv, installs two systemd services (bot + data collector), configures nginx as reverse proxy, and sets UFW firewall rules. A `.env` placeholder is generated with `chmod 600` permissions.

---

## Disclaimer

This project is for educational and portfolio purposes. Nothing here constitutes financial advice. Trading meme coins carries significant risk of total loss.
