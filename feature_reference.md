# Feature Reference — Signal Pipeline

39 features used as input to the FlameLearner XGBoost classifiers.
Features are grouped into 4 categories. Exact computation logic and
weighting are proprietary and excluded from this reference.

---

## Category 1: Market & Flow Features (12)

| Feature | Description |
|---|---|
| `price_change_1m` | % price change in the last 60 seconds |
| `price_change_5m` | % price change in the last 5 minutes |
| `volume_1m` | SOL volume traded in last 60 seconds |
| `volume_ratio_5m_15m` | Short-term vs medium-term volume ratio |
| `vwap_deviation` | Current price deviation from VWAP |
| `buy_pressure` | Buy-side volume fraction (0–1) |
| `trade_count_1m` | Number of trades in last 60 seconds |
| `mcap_usd` | Current market cap in USD |
| `liquidity_depth` | Estimated available liquidity |
| `price_stability` | Inverse of short-term volatility |
| `momentum_score` | Output of momentum/scorer.py |
| `sol_price_usd` | Current SOL/USD rate (background feed) |

---

## Category 2: Social & Sentiment Features (8)

| Feature | Description |
|---|---|
| `x_mention_velocity` | Rate of new X/Twitter mentions |
| `telegram_velocity` | Rate of new Telegram channel messages |
| `narrative_score` | Output of narrative/scorer.py |
| `social_alignment` | Consistency across social channels |
| `mention_sentiment` | Aggregated sentiment score |
| `influencer_signal` | Weighted influencer activity score |
| `cross_platform_lag` | Time delta between platform signals |
| `viral_coefficient` | Estimated share/repost rate |

---

## Category 3: On-Chain Quality Features (10)

| Feature | Description |
|---|---|
| `holder_count` | Number of unique holders |
| `holder_concentration` | Top-10 holder concentration (%) |
| `holder_score` | Composite holder quality score |
| `wallet_quality_score` | Avg quality of recent buyer wallets |
| `dev_wallet_flag` | Known bad dev wallet detected (bool) |
| `fresh_wallet_ratio` | Fraction of buyers with new wallets |
| `sniper_ratio` | Estimated sniped supply fraction |
| `rug_risk_score` | Output of rug_shield.py |
| `token_age_minutes` | Age of token since creation |
| `bonding_curve_pct` | % progress along bonding curve |

---

## Category 4: Bucket-Specific Features (9)

### TRENCH bucket (mcap < $10k, age < 45 min)

| Feature | Description |
|---|---|
| `trench_bounce_strength` | Recovery signal after initial dump |
| `trench_reversal_confirmation` | Pattern confirmation score |
| `trench_entry_timing` | Position within typical trench lifecycle |
| `trench_volume_spike` | Relative volume vs trench baseline |
| `trench_holder_acceleration` | Rate of new holder acquisition |

### MIGRATED_NEW bucket (mcap < $750k, age < 168h)

| Feature | Description |
|---|---|
| `migrated_freshness` | Recency since Raydium migration |
| `migrated_holder_growth` | Post-migration holder growth rate |
| `migrated_liquidity_ratio` | Liquidity vs mcap ratio |
| `signal_alignment_score` | Cross-signal fusion score (all buckets) |

---

## Notes

- All features are computed in `signal_pipeline/pipeline.py` and assembled into a `SignalFrame` dataclass before scoring.
- Features are normalised and calibrated per-bucket before being passed to the classifier.
- `signal_alignment_score` is a meta-feature combining ML score + momentum score + narrative score, used as a final confirmation gate.
