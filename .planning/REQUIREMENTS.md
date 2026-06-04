# Requirements: Berakah

**Defined:** 2026-06-04
**Core Value:** The research engine must produce trustworthy out-of-sample edge measurements — no leakage, no overfitting, no look-ahead.

## v1 Requirements

Ring 1 MVP scope. Each maps to exactly one roadmap phase (traceability table at the bottom).

### Data

- [ ] **DATA-01**: Engine ingests historical BTC/ETH OHLCV from Tier-1 exchanges (Binance, Coinbase, Kraken) at ≥5-minute resolution and stores it as Hive-partitioned Parquet
- [ ] **DATA-02**: Engine annotates the data record with the four macro-defined regime labels (Bull 2020–21, Bear 2022, Recovery 2023, ETF era 2024–) — labels are TOML-frozen, not algorithmically derived
- [ ] **DATA-03**: Engine performs data-integrity checks at ingest time — gap detection, UTC normalization, cross-exchange sanity, canonical pair naming (Binance:BTCUSDT, Coinbase:BTC-USD, Kraken:XBTUSD)

### Hypothesis & Strategy

- [ ] **HYP-01**: Operator authors a mean-reversion hypothesis as a vault Markdown note (`berakah_KB/hypotheses/HYP-{ID}-{slug}.md`) whose frontmatter links to an executable strategy module
- [ ] **HYP-02**: Strategy modules expose a compile-time-verifiable contract such that look-ahead bias is *unrepresentable* in the type system — `Strategy.on_bar(snap: BarSnapshot[NowTs]) -> tuple[OrderIntent, ...]` where `BarSnapshot[NowTs]` is a phantom-typed view that can only expose bars whose `close_ts <= now_ts`
- [ ] **HYP-03**: Hypothesis lifecycle is tracked via frontmatter status (`drafted | backtested | validated | invalidated`) and a per-hypothesis trial budget — required for the 6-month kill trigger accounting

### Backtest

- [ ] **BT-01**: Engine runs a backtest of any strategy module against the historical record with vol-targeted position sizing and a conservative fee model (10 bps + 2 bps slippage default)
- [ ] **BT-02**: Backtest output is a typed `BacktestArtifact` containing regime-stratified Sharpe, drawdown, win rate, equity curve, and trade-by-trade ledger — written to disk as parquet + JSON
- [ ] **BT-03**: Backtest produces a deterministic `run_id = hash(data_snapshot, code_sha, config_sha)` such that identical inputs produce byte-identical outputs (CI-asserted)

### Validation

- [ ] **VAL-01**: Engine performs out-of-sample validation with engine-enforced IS/OOS splits keyed off `frozen_ts` — splits are never picked post-hoc
- [ ] **VAL-02**: Engine flags strategies where in-sample Sharpe diverges from OOS Sharpe by more than a configurable threshold (overfitting detector via IS-vs-OOS t-test)
- [ ] **VAL-03**: Engine computes Deflated Sharpe Ratio (Bailey & López de Prado 2014) against pre-registered trial count; PROOF-01 threshold ≥ 0.95
- [ ] **VAL-04**: Engine computes Probability of Backtest Overfitting via CSCV (Bailey et al. 2015); PROOF-01 threshold ≤ 0.5
- [ ] **VAL-05**: Engine performs Combinatorial Purged Cross-Validation (CPCV) with purge + embargo on every backtest; path count capped at ~200 for single-laptop budget
- [ ] **VAL-06**: Engine maintains a never-touched final-validation slice locked at hypothesis-`frozen_ts` creation; operator can only access it once per strategy to confirm PROOF-01
- [ ] **VAL-07**: Engine uses the crypto-specific Sharpe annualization constant (`sqrt(365 × 24 × 12) = sqrt(105_120) ≈ 324.2`) as a project-pinned constant — not the equity-default `sqrt(252)`

### Vault & Reporting

- [ ] **REPORT-01**: Engine writes a Markdown validation report back to the vault (`berakah_KB/reports/{HYP-ID}/{run_ts}.md`), linked to the originating hypothesis note, summarizing regime-stratified results + PROOF-01 verdict
- [ ] **REPORT-02**: Hypothesis frontmatter pins `strategy_module`, `strategy_commit` (git SHA), `data_manifest`, `data_commit`, `frozen_ts` — vault/code drift defense
- [ ] **REPORT-03**: Vault `_index.md` records every run as an audit-log entry; supports the kill-trigger countdown
- [ ] **REPORT-04**: Pre-commit guard refuses to commit reports whose pinned commit SHA is not reachable from `HEAD`

### Configuration & Operations

- [ ] **CONFIG-01**: All configuration is a single frozen Pydantic Settings object (`BerakahConfig`) loaded once at CLI entry; `frozen=True, extra="forbid"`; no `os.getenv` scattered through the code
- [ ] **CONFIG-02**: `import-linter` contracts enforce module-boundary rules (strategy modules cannot import `data`/`vault`/`backtest`; reverse edges across the DAG are forbidden); CI-blocking
- [ ] **CONFIG-03**: `uv sync --frozen` enforces lockfile compliance in CI; `pyright --strict` + `ruff` run on every commit

### CLI

- [ ] **CLI-01**: `berakah ingest --exchange <name> --pair <symbol> --from <date>` fetches Tier-1 OHLCV and writes to the data store
- [ ] **CLI-02**: `berakah backtest <HYP-ID>` runs the linked strategy module against the data store
- [ ] **CLI-03**: `berakah validate <HYP-ID>` runs the full validation pipeline (IS/OOS, DSR, PBO, CPCV, final slice) and emits a validation artifact
- [ ] **CLI-04**: `berakah run <HYP-ID>` composes ingest → backtest → validate → write-report as the operator's daily loop

### Closing Bar

- [ ] **PROOF-01**: A mean-reversion strategy is found that holds **OOS Sharpe ≥ 1.0 over a rolling 3-month window** AND **regime-stratified Sharpe ≥ 0 across all four labeled regimes** AND **DSR ≥ 0.95** AND **PBO ≤ 0.5** AND **holds on the never-touched final-validation slice** — this multi-gate is the deliverable that closes Ring 1

## v2 Requirements

Acknowledged, deferred to a post-Ring-1 milestone. Tracked but not in current roadmap.

### Regime Overlay (Ring 1 → Ring 2 bridge)

- **HMM-01**: Hidden Markov Model regime classifier as an active position-size gate (currently regime labels are only used for stratified validation reporting)
- **HMM-02**: Regime-conditional Sharpe statistics with confidence intervals

### Parameter Search (after first PROOF-01 attempt)

- **SWEEP-01**: Parameter sweep + heatmap reporting for hyperparameter sensitivity analysis
- **SWEEP-02**: Trade-ledger Markdown excerpts in REPORT-01 (currently raw parquet only)

### Execution Layer (Ring 2)

- **EXEC-01**: Simulated execution with realistic slippage modeling
- **EXEC-02**: Paper-trading layer with order book modeling and partial fills
- **EXEC-03**: Position sizing optimization under realistic friction

### Live Trading (Ring 3)

- **LIVE-01**: Small-size live trading on validated edges
- **LIVE-02**: Six independent kill-switches operational before any live capital
- **LIVE-03**: Drawdown circuit breakers + manual intervention pathway

### Portfolio (Ring 4)

- **PORT-01**: Multi-niche strategy portfolio (multiple weak edges combined)
- **PORT-02**: Risk-budget allocation across uncorrelated edges
- **PORT-03**: Modular risk management as separable layer

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Real-time WebSocket feeds in Ring 1 | Ring 1 = historical research only; WebSocket arrives with Ring 2/3 |
| Live order execution | Ring 3 scope; cannot exist before validation infrastructure is trusted |
| LLM in the signal hot path | Non-deterministic, non-backtestable, opaque reasoning — violates determinism contract |
| Multi-asset universe beyond BTC + ETH | Concentric expansion: one niche first; broader universe is Ring 4 |
| Sub-5-minute timeframes | Institutional spoofing/layering dominates sub-minute; no defensible retail edge there |
| Non-Tier-1 exchanges | Wash-trade contamination on smaller venues compromises signal integrity |
| Momentum / trend-following strategy family in Ring 1 | Most-exposed niche to institutional manipulation; mean-reversion preferred for first edge |
| Funding-rate / basis niche | Requires perp instrument modeling; adds infra surface that competes with core validation |
| On-chain regime signal niche | Whale-wallet manipulation directly contaminates the data source |
| Alternative data / paid data feeds | Out of $0–25/mo budget |
| Margin / perp / leverage | Removes catastrophic loss modes from validation surface; spot-only |
| Auto strategy generation | Max overfit machine at MVP scale — every search inflates trial budget toward 1.0 PBO |
| Web UI / dashboard | CLI is sufficient for solo PM operator; UI is Ring 4+ |
| Multi-engine backtest parity (vectorbt reconciliation) | Out-of-scope hardening; would need a second engine which we explicitly rejected |
| Pandas as primary dataframe | Polars chosen; pandas only at library-compat shims if needed |
| `pyfolio`/`empyrical`/`quantstats` as metrics layer | Maintenance-dead or pandas-only — custom scipy+polars metrics chosen |

## Traceability

Mapping from REQ-ID → phase. The roadmapper will finalize phase numbering; phases below reflect the 6-phase decomposition recommended by SUMMARY.md ("Implications for Roadmap").

| Requirement | Phase | Status |
|-------------|-------|--------|
| HYP-02 | Phase 1 (Typed Foundation) | Pending |
| CONFIG-01 | Phase 1 | Pending |
| CONFIG-02 | Phase 1 | Pending |
| CONFIG-03 | Phase 1 | Pending |
| DATA-01 | Phase 2 (Data Layer) | Pending |
| DATA-02 | Phase 2 | Pending |
| DATA-03 | Phase 2 | Pending |
| HYP-01 | Phase 3 (Strategy + Backtest) | Pending |
| BT-01 | Phase 3 | Pending |
| BT-02 | Phase 3 | Pending |
| BT-03 | Phase 3 | Pending |
| VAL-01 | Phase 4 (Validation) | Pending |
| VAL-02 | Phase 4 | Pending |
| VAL-03 | Phase 4 | Pending |
| VAL-04 | Phase 4 | Pending |
| VAL-05 | Phase 4 | Pending |
| VAL-06 | Phase 4 | Pending |
| VAL-07 | Phase 4 | Pending |
| HYP-03 | Phase 5 (Vault Round-Trip) | Pending |
| REPORT-01 | Phase 5 | Pending |
| REPORT-02 | Phase 5 | Pending |
| REPORT-03 | Phase 5 | Pending |
| REPORT-04 | Phase 5 | Pending |
| CLI-01 | Phase 6 (CLI + First PROOF-01) | Pending |
| CLI-02 | Phase 6 | Pending |
| CLI-03 | Phase 6 | Pending |
| CLI-04 | Phase 6 | Pending |
| PROOF-01 | Phase 6 | Pending |

**Coverage:**
- v1 requirements: 28 total
- Mapped to phases: 28
- Unmapped: 0 ✓

---
*Requirements defined: 2026-06-04*
*Last updated: 2026-06-04 after initial definition*
