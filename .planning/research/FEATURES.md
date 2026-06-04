# Feature Research

**Domain:** Systematic crypto BTC/ETH mean-reversion research engine fused with an Obsidian (Karpathy-style) knowledge vault
**Researched:** 2026-06-04
**Confidence:** HIGH (table stakes), HIGH (differentiators), HIGH (anti-features)

## Scope Note

This FEATURES.md is scoped to **Ring 1 of the Concentric Monopoly Stack** — the research engine ONLY. Execution, paper-trading, and live capital management are deliberately out of scope (see Anti-Features). The closing deliverable is `PROOF-01`: a single mean-reversion strategy with **OOS Sharpe >= 1.0 over a rolling 3-month window AND regime-stratified Sharpe >= 0 across all 4 labeled regimes** (Bull 2020–21, Bear 2022, Recovery 2023, ETF era 2024–).

Each feature is mapped to one or more REQ-IDs from `PROJECT.md` so this document feeds `REQUIREMENTS.md` directly.

Complexity scale: **S** (≤1 day), **M** (2–5 days), **L** (1–2 weeks), **XL** (>2 weeks).

---

## Feature Landscape

### Table Stakes (Non-Negotiable for a Credible Research Engine)

Features any credible quant research engine MUST have. Missing these = the engine cannot produce trustworthy OOS edge measurements, which is the Core Value (per PROJECT.md).

| # | Feature | REQ-ID | Why Expected | Complexity | Notes |
|---|---------|--------|--------------|------------|-------|
| TS-1 | **Historical OHLCV ingestion from Tier-1 exchanges** (Binance, Coinbase, Kraken) at 5-min, 15-min, 1h, 1d | DATA-01 | No data, no backtest. Tier-1 only to control wash-trade contamination. | M | CCXT covers all three; spot only; rate-limit-aware; resumable. |
| TS-2 | **Queryable analytical storage** (Parquet partitioned by symbol + year) | DATA-01 | Industry standard for tabular time-series. Cheap, columnar, pandas/polars-native. | S | Single `data/raw/{exchange}/{symbol}/{tf}/{year}.parquet` layout; partition keys must include exchange to enable Tier-1 cross-checks later. |
| TS-3 | **Data integrity checks** (gap detection, duplicate timestamps, monotonic time index, OHLC sanity) | DATA-01 | Garbage in, garbage edge. Crypto venues drop bars during outages; uncaught gaps = silent leakage when you forward-fill. | M | Hard-fail on gaps > 1 bar; log gap report into vault. |
| TS-4 | **Regime label annotation** for the 4 named regimes (Bull 2020–21, Bear 2022, Recovery 2023, ETF era 2024–) | DATA-02 | The `PROOF-01` bar is regime-stratified. Without labels, the closing criterion cannot be evaluated. | S | Static date-range labels in a YAML/TOML config; not an HMM (see AF-4). |
| TS-5 | **Strategy module abstraction** (single interface: `(state, bar) -> signal`) | HYP-01, HYP-02 | The unit of research is the strategy. A clean interface lets the engine swap strategies and isolate them from data/sizing/reporting concerns. | M | Protocol/ABC; pure function preferred (functional discipline). |
| TS-6 | **Event-driven backtest loop with explicit `now_ts` semantics** | HYP-02, BT-01 | Vectorized backtests hide look-ahead bias; the explicit `now_ts` event loop makes it structurally impossible to read future bars. Search results confirm this is THE consensus pattern for bias-free backtesting. | L | Strategy receives a bar-windowed view that ends at `now_ts`; future bars are unreachable in the type. |
| TS-7 | **Look-ahead prevention as a type-level contract** (treated as a feature, NOT an implementation detail) | HYP-02 | Per Engineering Principle 5 ("hard constraints over loose logic"), the type system must make look-ahead unrepresentable. This is the load-bearing safety asset. | L | `Bar` wraps `ts`; data view is `HistoricalView(up_to=now_ts)` with no method that returns `ts > now_ts`. mypy/pyright `strict` mode required. |
| TS-8 | **Vol-targeted position sizing** | BT-01 | Per the PROJECT.md manipulation-risk discussion, vol-target sizing is one of the two residual-risk mitigations for mean-reversion (the other being drawdown caps). Required at MVP. | M | Rolling realized-vol estimator; target annualized vol per position (e.g., 20%); cap leverage at 1.0 since spot only. |
| TS-9 | **Transaction cost modeling — fees** (maker/taker, per exchange) | BT-01 | Crypto fees (~5–10 bps round-trip) are large enough to flip a marginal mean-reversion edge to negative. Cannot defer. | S | Static per-exchange fee table; charged at fill ts; explicitly NO slippage in Ring 1 (out of scope — Ring 2). |
| TS-10 | **Engine-enforced in-sample / out-of-sample split** | VAL-01 | Per-post-hoc splits are the #1 source of overfitting per López de Prado. The engine must own the boundary so the operator cannot move it after seeing results. | M | IS/OOS dates locked in a config-as-code file, committed before the strategy is run; engine refuses to report combined metrics. |
| TS-11 | **Performance metrics** (Sharpe, Sortino, max drawdown, win rate, profit factor, total return, time in market, turnover) | BT-02 | Industry-standard metric set. Sharpe alone is misleading (heavy-tailed crypto); Sortino + DD are needed companions. | S | Pure functions over the equity curve; no in-place state. |
| TS-12 | **Trade-by-trade ledger output** (entry ts, exit ts, side, size, entry/exit price, fees, PnL, holding period, regime label, strategy id, data hash) | BT-02 | Aggregate metrics lie. The ledger lets the operator audit individual trades for sanity-check failures (entries on bad bars, exits before fees clear, etc.). | M | Parquet ledger per backtest run; one row per closed trade. |
| TS-13 | **Equity curve + position time series** (per-bar mark-to-market output) | BT-02 | Required to compute rolling Sharpe, drawdown curves, and the rolling 3-month Sharpe gate of `PROOF-01`. | S | Parquet; one row per bar. |
| TS-14 | **Regime-stratified validation report** (Sharpe / Sortino / DD / win rate broken out per regime) | BT-02, PROOF-01 | This IS the closing criterion. Not optional, not bolt-on. | M | First-class output of every backtest, not a post-processing script. |
| TS-15 | **Markdown validation report written back to the vault**, linked to the originating hypothesis note | REPORT-01 | The Karpathy-style round-trip is the differentiator. The Markdown report is the deliverable artifact. | M | Templated report; auto-linked via wikilink; written to `berakah_KB/03_hypotheses/{hyp_id}/reports/`. |
| TS-16 | **CLI / scriptable entrypoint** to run a backtest by hypothesis ID | (cross-cutting) | The operator is PM, not engineer. One command per backtest run. | S | `berakah run <hyp_id>` calling a thin wrapper over the engine. |
| TS-17 | **Structured logging** (one structured log line per event) | (cross-cutting) | Audit trail. Cheap to add at the start, expensive to retrofit. | S | `structlog` or stdlib `logging` with a JSON formatter. |

**Table stakes complexity total:** ~6–7 weeks of focused work for a single-operator (PM + Claude) team — matches the PROJECT.md 6-week MVP target.

---

### Differentiators (Karpathy-Style Vault Roundtrip + Validation Discipline)

These are where Berakah competes against off-the-shelf backtesters (vectorbt, backtrader, Zipline). They align with the Core Value: **trustworthy out-of-sample edge measurements**.

| # | Feature | REQ-ID | Value Proposition | Complexity | Notes |
|---|---------|--------|-------------------|------------|-------|
| D-1 | **Vault round-trip** (hypothesis note → executable strategy module → backtest → Markdown report linked back into the vault) | HYP-01, REPORT-01 | This is THE Karpathy-wiki differentiator. No off-the-shelf backtester writes results back to a wiki linked to the hypothesis spec. Compounds knowledge across runs. | L | Hypothesis note has front-matter `hyp_id`, `strategy_module`, `is_window`, `oos_window`; report has back-link. |
| D-2 | **Hypothesis-as-code-contract** — the vault note IS the spec; the module satisfies it; CI rejects drift | HYP-01, HYP-02 | Renders the vault load-bearing instead of decorative. The note declares the strategy's parameters, regimes, and metric thresholds; the engine validates the module obeys the spec. | L | Front-matter schema validation; pre-commit hook flags mismatches. |
| D-3 | **Hypothesis lifecycle tracking** (state: `proposed` → `coded` → `backtested` → `oos-passed` / `oos-failed` / `retired`) | HYP-01, REPORT-01 | Without lifecycle state, hypotheses pile up as zombies. Tracks the research funnel and makes the kill trigger measurable. | S | Front-matter state field; CLI `berakah hyp list --state=...`. |
| D-4 | **Overfitting detector** — IS Sharpe vs OOS Sharpe divergence flag with configurable threshold | VAL-02 | López de Prado's deflated Sharpe ratio and PBO insight, simplified. If IS Sharpe far exceeds OOS Sharpe, flag as overfit; this kills the most common failure mode in retail quant. | S | One ratio + one threshold + a hard-fail flag in the report. |
| D-5 | **Regime-stratified validation as a first-class output**, not a post-hoc script | BT-02, PROOF-01 | Most engines treat regime analysis as bolt-on; making it first-class lines up directly with the closing criterion and prevents "oh I forgot to check regime X" failure mode. | M | (Subsumes TS-14; counted here because the first-class-ness is the differentiator, not the existence.) |
| D-6 | **Reproducibility hash** (data snapshot SHA + code commit SHA + config SHA -> single `run_id`; same `run_id` -> bit-identical outputs) | (cross-cutting) | Industry survey results show implementation risk is a quantified, unsolved problem. A deterministic hash means any report can be reproduced exactly N months later. | M | Hash all inputs; assert determinism in CI via a smoke backtest. Seed all stochastic ops. |
| D-7 | **Automated parameter-sensitivity sweep + heatmap reporting** | (extends BT-01) | Robust strategies show wide parameter plateaus; brittle ones show sharp peaks. Heatmaps make this visible at a glance and prevent narrow-peak overfit. | M | Grid sweep; heatmap PNG embedded in the Markdown report; "robustness score" = stdev across neighborhood. |
| D-8 | **Look-ahead prevention as a type-level contract** | HYP-02 | (Subsumes TS-7; counted here because while many engines event-loop their backtests, very few enforce look-ahead-impossibility in the type system. This IS the Berakah-specific edge.) | L | `HistoricalView` type; pyright strict; CI gate that rejects code that pattern-matches future-bar access. |
| D-9 | **Deflated Sharpe Ratio (DSR)** computed and reported when N strategies/parameter sets have been evaluated | VAL-02 | Plain Sharpe over-rewards the lucky best of N trials; DSR corrects for it. Cheap to add given a sweep already runs. | S | Standard formula from Bailey & López de Prado (2014); applied across the parameter sweep results. |
| D-10 | **Trade ledger linked back into the vault as a Markdown table excerpt + parquet artifact** | REPORT-01 | The vault becomes the index, the parquet is the source of truth. Operator can grep the wiki for "stop hunt false positive" and find the originating trade. | S | Top-N losers and top-N winners excerpted to Markdown; full parquet attached as a relative link. |
| D-11 | **Data snapshot pinning** (every run pins the exact data version it used; data updates create a new snapshot, never overwrite) | (cross-cutting) | Same code on different data = different results. The hash (D-6) only works if data is versioned. | M | `data/snapshots/{snapshot_id}/...` directory; symlink `latest`; backtest runs record the snapshot_id used. |
| D-12 | **Configuration-as-code with schema validation** for backtest runs (IS/OOS windows, fee table, vol-target, regime ranges) | VAL-01 | Stops "I changed the OOS window after seeing results" — the #1 self-deception in quant. Config diffs in git history are auditable. | S | Pydantic models; YAML/TOML config files committed before the run. |

---

### Anti-Features (Deliberately NOT Built — Each With a WHY)

The Engineering Principle "negative-space coding" applies here: clearly stating what the engine MUST NOT do is as load-bearing as stating what it must do. Each anti-feature corresponds to a real temptation that, if pursued in Ring 1, would compromise the validation discipline.

| # | Anti-Feature | Why It's Tempting | Why It's Wrong for Ring 1 | What to Do Instead |
|---|--------------|-------------------|---------------------------|--------------------|
| AF-1 | **Real-time WebSocket feeds / live data ingestion** | "We'll need it eventually for Ring 3, may as well wire it now." | Drags in connection state, reconnect logic, and asynchronous concerns that contaminate the deterministic backtest loop. Adds zero validation value. | Defer to Ring 2/3. Ring 1 is historical-only by design. |
| AF-2 | **Order execution layer** (broker abstractions, order types, fills, fill queues) | Most off-the-shelf frameworks have it, feels "professional" to include. | Ring 1's purpose is to PROVE the edge exists. Execution friction is a SEPARATE proof (Ring 2). Mixing them lets execution bugs masquerade as edge failures. | Defer to Ring 2. The "trade" abstraction in Ring 1 = (entry_bar, exit_bar, instantaneous fill at close, fee-only). |
| AF-3 | **Live capital / portfolio management / risk-limit kill-switches in the runtime sense** | "Safety first." | There is no live capital in Ring 1 (per PROJECT.md "No live capital at risk during Ring 1"). Runtime risk controls without live capital = code without purpose. | Encode max drawdown as a backtest *evaluation* metric (hard-fail in report), not a runtime guard. |
| AF-4 | **HMM regime classifier as an active signal modulator** (live regime detection that gates positions) | "Renaissance does it; we should too." | Per PROJECT.md decision log, HMM overlay adds significant validation complexity (regime-conditional statistics, double-leakage risk: the classifier itself can leak future regime information). Deferred explicitly. | Regime LABELS (date-range tags) for stratified VALIDATION reporting in Ring 1 (see TS-4). No live classifier. |
| AF-5 | **LLM in the signal hot path** (LLM generates trade signals or modifies positions in the backtest loop) | "It's the AI era." | LLM outputs are non-deterministic, version-drift-prone, and break reproducibility (D-6). They cannot be backtested with statistical validity. | Use LLM (Claude Code) for code GENERATION and research SYNTHESIS in the vault, never as a runtime signal source. |
| AF-6 | **Multi-exchange arbitrage** (cross-exchange spread strategies) | Mean-reversion at the cross-venue spread level looks attractive. | Ring 1 is single-strategy / single-instrument-class. Arbitrage requires synchronized order books, latency modeling, and execution venue routing — none of which the validation infra is built for. | Defer indefinitely. If pursued, it lives in a separate concentric ring. |
| AF-7 | **Complex execution simulators** (queue-position modeling, partial fills, market-impact models, slippage curves) | "Realism." | This is Ring 2 work by definition. In Ring 1, including these adds tuning knobs (= more overfitting surface area) without changing the edge-existence question. | Defer to Ring 2. Ring 1 uses instantaneous fill at bar close + fee only. |
| AF-8 | **Multi-asset universe beyond BTC + ETH** (top-100 alts, sector baskets) | More tickers = more "data" = more "edges." | Altcoin data is contaminated by wash trades, survivorship bias, and listing/delisting events. Ring 1 universe is locked to BTC + ETH per PROJECT.md. | Defer to Ring 4 only after Ring 1–3 are stable. |
| AF-9 | **Sub-5-minute timeframes** (1-min, tick, sub-second) | Higher frequency feels "more sophisticated." | Per PROJECT.md, institutional spoofing / layering dominates at sub-minute scales — no defensible retail edge there, and infra cost is disproportionate. | Floor at 5-minute bars. Reconsider only if a defensible thesis emerges for the floor's removal. |
| AF-10 | **Paid data feeds / alternative data** (sentiment, on-chain, social, paid APIs) | Differentiated data feels like differentiated edge. | Out of the $0–25/month budget. Alt data introduces non-stationary signal-source risk (e.g., the API changes its method, the edge dies invisibly). | Free Tier-1 exchange data only. Reconsider only after `PROOF-01` is closed. |
| AF-11 | **Momentum / trend-following strategy family** | Trend-following has a long academic pedigree. | Per PROJECT.md, momentum is the MOST exposed niche to institutional flow distortion. It's the wrong first niche. | Locked to mean-reversion in Ring 1. Revisit only after mean-reversion is proven. |
| AF-12 | **Web UI / dashboard** (interactive equity curve viewer, strategy lab, etc.) | Pretty plots feel productive. | The operator is a PM directing Claude; the deliverable is the Markdown report in the vault. A web UI is operator-time tax without validation value. | Markdown + embedded PNGs in the vault. Use Obsidian's built-in renderer. |
| AF-13 | **Margin / perp / leverage modeling** | "More edges available with leverage." | Per PROJECT.md, spot only — leverage removes catastrophic loss modes from the validation surface. Adding it back contaminates the validation discipline. | Spot only in Ring 1. |
| AF-14 | **Non-Tier-1 exchanges as data source** (KuCoin, OKX, alt venues) | More volume sources = larger sample. | Wash trade and fake volume contaminate the signal. Per PROJECT.md, exchange whitelist is locked. | Binance, Coinbase, Kraken only. |
| AF-15 | **Funding-rate / basis strategies** (perpetual swap funding arbitrage, basis trades) | Recognized as a profitable niche. | Requires perp instrument modeling — adds infrastructure surface that competes with the core validation work. Deferred per PROJECT.md. | Defer indefinitely from Ring 1; revisit as a separate niche after Ring 1 closes. |
| AF-16 | **On-chain / whale-wallet signal niche** | "Crypto-native edge." | Whale-wallet manipulation directly contaminates the data source (the "whales" know who's watching). Deferred per PROJECT.md. | Defer. |
| AF-17 | **Auto-strategy generation** (genetic search, neural-architecture search over strategy code) | "Renaissance generates strategies, we should too." | At Ring 1's scale this is the maximum-overfitting machine. Combinatorial generation + low signal-to-noise = guaranteed false-positive edges that look statistically valid. | Human-authored hypotheses (vault notes) only in Ring 1. Each hypothesis is a deliberate, justifiable bet. |
| AF-18 | **Multi-engine parity testing** (run the same strategy through vectorbt + backtrader to cross-check) | "Implementation-risk research says this matters." | True but expensive. The single engine's determinism (D-6) is the higher-leverage check at MVP scale. Cross-engine parity is a post-MVP hardening step. | Defer; consider after `PROOF-01` closes. |

---

## Feature Dependencies

```
DATA-01 (TS-1, TS-2, TS-3) — historical ingestion + storage
    |
    +--> DATA-02 (TS-4) — regime labels (needs the data to label)
    |       |
    |       v
    |     BT-02 (TS-14, D-5) — regime-stratified reporting (needs labels + backtest)
    |
    +--> HYP-01 (D-1, D-2, D-3) — vault round-trip / hypothesis-as-contract
    |       |
    |       v
    |     HYP-02 (TS-5, TS-6, TS-7, D-8) — strategy module + look-ahead-safe type contract
    |       |
    |       v
    |     BT-01 (TS-8, TS-9) — backtest with vol-target + fees
    |       |
    |       +--> BT-02 (TS-11, TS-12, TS-13) — metrics, ledger, equity curve
    |       |       |
    |       |       v
    |       |     VAL-01 (TS-10, D-12) — engine-enforced IS/OOS boundary
    |       |       |
    |       |       v
    |       |     VAL-02 (D-4, D-9) — overfitting detector + Deflated Sharpe
    |       |       |
    |       |       v
    |       |     REPORT-01 (TS-15, D-10) — Markdown report back into the vault
    |       |
    |       +--> D-7 (parameter sweep) — needs a working backtest to sweep over
    |
    +--> D-6 (reproducibility hash) — needs D-11 (snapshot pinning) and a configured backtest

CROSS-CUTTING: TS-16 (CLI), TS-17 (logging), D-11 (snapshot pinning), D-6 (run_id hash), D-12 (config-as-code)
```

### Dependency Notes

- **DATA-01 (TS-1) → DATA-02 (TS-4):** Cannot label regimes without bars to label. Regime labels are date-range static config; data ingestion does not depend on them.
- **HYP-02 (TS-7) → BT-01 (TS-6, TS-8):** The look-ahead-safe type contract IS the precondition for trusting the backtest loop. Build the type before the loop.
- **VAL-01 (TS-10) → BT-02 (TS-11):** The engine must enforce the IS/OOS split BEFORE metrics are aggregated, or the operator can post-hoc move the split.
- **VAL-02 (D-4) requires BOTH IS metrics AND OOS metrics:** The overfitting detector compares the two; both must exist as first-class engine outputs.
- **REPORT-01 (TS-15) → D-1 (vault round-trip):** The report's wikilink back to the hypothesis note IS the round-trip. They cannot be separated.
- **D-6 (reproducibility hash) → D-11 (data snapshot pinning):** Same code on un-pinned (mutating) data ≠ reproducible. Snapshot pinning is the data half of the determinism guarantee.
- **D-7 (parameter sweep) ENHANCES D-4 (overfitting detector) and D-9 (DSR):** The sweep produces the N-trial corpus that DSR and the overfit ratio operate on. Without a sweep, DSR is unmotivated.
- **AF-4 (HMM live classifier) CONFLICTS WITH VAL-01:** A live regime classifier in the signal loop introduces leakage risk that the IS/OOS boundary cannot cleanly guard against. The PROJECT.md decision to defer HMM is structural, not just temporal.
- **AF-5 (LLM in hot path) CONFLICTS WITH D-6 (reproducibility hash):** LLM stochasticity defeats determinism by construction.

---

## MVP Definition

### Launch With (PROOF-01 close = Ring 1 MVP exit)

Every item in **Table Stakes** (TS-1 through TS-17) plus the load-bearing differentiators. These are essential because they map directly to the REQ-IDs already validated in PROJECT.md:

- [ ] **All 17 Table Stakes** — these collectively realize DATA-01, DATA-02, HYP-01, HYP-02, BT-01, BT-02, VAL-01, VAL-02, REPORT-01.
- [ ] **D-1 (Vault round-trip)** — the Karpathy-style differentiator. Without it, Berakah is just another backtester.
- [ ] **D-2 (Hypothesis-as-code-contract)** — without it, the vault drifts and stops being the spec.
- [ ] **D-3 (Hypothesis lifecycle tracking)** — required to count strategies attempted against the 6-month kill trigger.
- [ ] **D-4 (Overfitting detector)** — directly realizes VAL-02; cheap; load-bearing for trust.
- [ ] **D-6 (Reproducibility hash)** — without it, no past report can be re-verified, which means none can be trusted.
- [ ] **D-8 (Look-ahead prevention as a type-level contract)** — directly realizes HYP-02; this is the Engineering Principle 5 application.
- [ ] **D-11 (Data snapshot pinning)** — required for D-6 to function.
- [ ] **D-12 (Configuration-as-code)** — required for VAL-01 enforcement and audit trail.

### Add After PROOF-01 Closes (Ring 1 Polish, Pre–Ring 2)

- [ ] **D-7 (Parameter sweep + heatmaps)** — required for D-9 (DSR) to be meaningful; possibly required for `PROOF-01` if the first hand-tuned strategy fails to clear the bar.
- [ ] **D-9 (Deflated Sharpe Ratio)** — adds an extra rigor layer once a parameter sweep exists.
- [ ] **D-10 (Trade ledger excerpt in Markdown)** — improves vault discoverability; not strictly required for PROOF-01.
- [ ] **D-5 (Regime-stratified as first-class output)** — already present as TS-14; the "first-class" elevation is differentiation polish.

### Future Consideration (Ring 2+)

Deferred features that are valuable but outside the Ring 1 validation discipline. All listed as Anti-Features above:

- [ ] **Real-time data + execution layer** (AF-1, AF-2) → Ring 2 paper-trade ring.
- [ ] **Multi-engine parity testing** (AF-18) → Ring 1 hardening after PROOF-01.
- [ ] **HMM regime classifier as live signal modulator** (AF-4) → Post–Ring 1 phase per PROJECT.md.
- [ ] **Multi-asset universe** (AF-8) → Ring 4 portfolio expansion.

---

## Feature Prioritization Matrix

| Feature | User (Operator) Value | Implementation Cost | Priority | Rationale |
|---------|------------------------|---------------------|----------|-----------|
| TS-1 Historical OHLCV ingestion | HIGH | MEDIUM | P1 | No data, no engine. |
| TS-2 Parquet storage | HIGH | LOW | P1 | Standard, cheap, required by every downstream stage. |
| TS-3 Data integrity checks | HIGH | MEDIUM | P1 | Silent gaps = silent leakage = invalidates everything downstream. |
| TS-4 Regime labels | HIGH | LOW | P1 | Required for the PROOF-01 closing criterion. |
| TS-5 Strategy module abstraction | HIGH | MEDIUM | P1 | Without the interface, nothing else has a contract to satisfy. |
| TS-6 Event-driven backtest loop | HIGH | HIGH | P1 | Core of the engine. |
| TS-7 Look-ahead type contract | HIGH | HIGH | P1 | The load-bearing safety asset. |
| TS-8 Vol-target sizing | HIGH | MEDIUM | P1 | Manipulation-risk mitigation per PROJECT.md. |
| TS-9 Fees | HIGH | LOW | P1 | Cheap but mandatory. |
| TS-10 IS/OOS split enforcement | HIGH | MEDIUM | P1 | Directly realizes VAL-01. |
| TS-11 Performance metrics | HIGH | LOW | P1 | Standard set; cheap. |
| TS-12 Trade ledger | HIGH | MEDIUM | P1 | Auditability. |
| TS-13 Equity curve | HIGH | LOW | P1 | Cheap; required for rolling 3-month Sharpe of PROOF-01. |
| TS-14 Regime-stratified report | HIGH | MEDIUM | P1 | Realizes PROOF-01 closing criterion. |
| TS-15 Markdown report to vault | HIGH | MEDIUM | P1 | The deliverable artifact. |
| TS-16 CLI entrypoint | MEDIUM | LOW | P1 | One command per backtest; operator ergonomics. |
| TS-17 Structured logging | MEDIUM | LOW | P1 | Cheap to add, expensive to retrofit. |
| D-1 Vault round-trip | HIGH | HIGH | P1 | The Karpathy-wiki differentiator. |
| D-2 Hypothesis-as-code-contract | HIGH | HIGH | P1 | Makes the vault load-bearing. |
| D-3 Hypothesis lifecycle | MEDIUM | LOW | P1 | Required for 6-month kill trigger accounting. |
| D-4 Overfitting detector | HIGH | LOW | P1 | Directly realizes VAL-02. |
| D-6 Reproducibility hash | HIGH | MEDIUM | P1 | Without it, no past report can be re-trusted. |
| D-8 Look-ahead type contract (= D8 = TS-7) | HIGH | HIGH | P1 | (Same as TS-7, listed under differentiators for emphasis.) |
| D-11 Data snapshot pinning | HIGH | MEDIUM | P1 | Half of the determinism guarantee. |
| D-12 Configuration-as-code | HIGH | LOW | P1 | Required for VAL-01 enforcement. |
| D-7 Parameter sweep + heatmaps | MEDIUM | MEDIUM | P2 | Add if the first hand-tuned strategy doesn't clear PROOF-01. |
| D-9 Deflated Sharpe Ratio | MEDIUM | LOW | P2 | Needs D-7 to be meaningful. |
| D-10 Trade ledger Markdown excerpt | LOW | LOW | P2 | Vault discoverability polish. |
| D-5 Regime-stratified first-class elevation | MEDIUM | LOW | P2 | TS-14 already covers the substance. |

**Priority key:**
- **P1**: Required for Ring 1 MVP (PROOF-01 close).
- **P2**: Adds rigor / polish; add after P1 is shipped OR if PROOF-01 fails first attempt.
- **P3**: Out of Ring 1 scope (all P3 items are listed as Anti-Features above).

---

## Competitor Feature Analysis

The "competitors" here are open-source Python backtesters, since Berakah is not a commercial product. Comparison is on feature philosophy, not feature counts.

| Feature | vectorbt | backtrader | Zipline-reloaded | NautilusTrader | **Berakah Ring 1** |
|---------|----------|------------|------------------|----------------|--------------------|
| Backtest style | Vectorized | Event-driven | Event-driven (daily eq) | Event-driven (low-latency) | **Event-driven with type-level `now_ts` contract** |
| Look-ahead protection | Manual discipline | Manual discipline | Pipeline API (factor-level) | Manual discipline | **Type-system-enforced (D-8) — unrepresentable, not just unlikely** |
| OOS split enforcement | Operator-managed | Operator-managed | Operator-managed | Operator-managed | **Engine-enforced + config-as-code (TS-10, D-12)** |
| Overfit detection | Operator-built | Operator-built | Operator-built | Operator-built | **Built-in IS/OOS Sharpe-divergence flag (D-4) + DSR (D-9)** |
| Regime stratification | Operator post-processing | Operator post-processing | Operator post-processing | Operator post-processing | **First-class engine output (D-5)** |
| Reproducibility | Best-effort | Best-effort | Best-effort | Best-effort | **`run_id = hash(data_snap, code_sha, config_sha)` (D-6) — determinism asserted in CI** |
| Knowledge management | None | None | None | None | **Obsidian vault round-trip (D-1, D-2, D-3) — unique** |
| Parameter sweep | Built-in | Plugin | Built-in (research env) | Plugin | **Built-in + heatmap report (D-7), added at P2** |
| Asset coverage | Multi-asset | Multi-asset | Equities-first | Multi-asset, low-latency | **BTC + ETH spot only (deliberately narrow)** |
| Execution model | Vectorized fills | Realistic broker sim | Pipeline-based | Realistic + tick | **Instant fill @ close + fee only (Ring 2 scope for more)** |

**Why we are not just wrapping one of these:** Off-the-shelf backtesters optimize for STRATEGY VOLUME (run many strategies fast) or EXECUTION REALISM (live-trade-quality simulation). Berakah Ring 1 optimizes for VALIDATION TRUSTWORTHINESS for ONE strategy family. Type-level look-ahead prevention, engine-enforced IS/OOS, deterministic `run_id`, and the vault round-trip are the four differentiators. The first three could in principle be retrofitted onto vectorbt or backtrader, but the cost is comparable to writing the targeted engine, and the retrofit doesn't address the vault round-trip at all.

---

## Open Questions Routed to Phase-Specific Research

These do not block Ring 1 MVP but should be surfaced in later phases:

- **Q1:** What's the right Markdown report template structure (section order, embedded plot list, metric tables)? — Phase 4/5 research, lightweight.
- **Q2:** Pyright strict vs mypy strict — which catches more look-ahead-class violations in practice for this code pattern? — Phase 1 spike.
- **Q3:** Is the regime-label set (the 4 named regimes) granular enough, or do we need a finer-grained sub-regime layer? — Revisit after first PROOF-01 attempt produces regime-stratified results.
- **Q4:** Parquet partitioning strategy: by year only vs (exchange, year) vs (exchange, symbol, year)? — Phase 1; depends on query patterns we converge on.
- **Q5:** Logging format — does Obsidian render embedded JSON log excerpts usefully, or do we need a different post-mortem format? — Phase 5.

---

## Sources

- [Battle-Tested Backtesters: VectorBT, Zipline, and Backtrader](https://medium.com/@trading.dude/battle-tested-backtesters-comparing-vectorbt-zipline-and-backtrader-for-financial-strategy-dee33d33a9e0)
- [The Python Backtesting Landscape (2026)](https://python.financial/)
- [Backtrader vs NautilusTrader vs VectorBT vs Zipline-reloaded](https://autotradelab.com/blog/backtrader-vs-nautilusttrader-vs-vectorbt-vs-zipline-reloaded)
- [Backtrader vs VnPy vs Qlib: 2026 Deep Comparison](https://dev.to/linou518/backtrader-vs-vnpy-vs-qlib-a-deep-comparison-of-python-quant-backtesting-frameworks-2026-3gjl)
- [10 Best Backtesting Platforms for Quant Funds in 2026](https://www.zerve.ai/blog/backtesting-platforms-for-quant-funds)
- [QuantStart: Backtesting Systematic Trading Strategies in Python](https://www.quantstart.com/articles/backtesting-systematic-trading-strategies-in-python-considerations-and-open-source-frameworks/)
- [How I Built an Event-Driven Backtesting Engine in Python](https://timkimutai.medium.com/how-i-built-an-event-driven-backtesting-engine-in-python-25179a80cde0)
- [The Contrasting Worlds of Vectorized and Event-Based Backtesting](https://onepagecode.substack.com/p/the-contrasting-worlds-of-vectorized)
- [IBKR Quant: Vector-Based vs. Event-Based Backtesting](https://www.interactivebrokers.com/campus/ibkr-quant-news/a-practical-breakdown-of-vector-based-vs-event-based-backtesting/)
- [Bias-Free Backtesting: Point-in-Time Data (sharpely)](https://sharpely.in/blog/bias-free-backtesting-explained:-how-sharpely-uses-point-in-time-data-to-avoid-look-ahead-and-survivorship-bias)
- [Bailey & López de Prado: The Deflated Sharpe Ratio (PDF)](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf)
- [Deflated Sharpe Ratio — Wikipedia](https://en.wikipedia.org/wiki/Deflated_Sharpe_ratio)
- [Backtest Overfitting in the ML Era — ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0950705124011110)
- [AlgoXpert: A Rigorous IS WFA OOS Protocol](https://arxiv.org/pdf/2603.09219)
- [Purged Cross-Validation — Wikipedia](https://en.wikipedia.org/wiki/Purged_cross-validation)
- [Quantopian's IS vs OOS Performance Paper — Quantpedia](https://quantpedia.com/quantopians-academic-paper-about-in-vs-out-of-sample-performance-of-trading-alg/)
- [Implementation Risk in Portfolio Backtesting — arXiv 2603.20319](https://arxiv.org/html/2603.20319v1)
- [Crypto Backtesting Guide 2026 — Cointester](https://medium.com/@cointesterio/crypto-backtesting-in-2026-the-definitive-guide-to-building-profitable-strategies-9be131b38c31)
- [Mean Reversion Strategy in Crypto — Fensory](https://www.fensory.com/knowledge/mean-reversion-strategy)
- [Parameter Heatmap & Optimization — Backtesting.py](https://kernc.github.io/backtesting.py/doc/examples/Parameter%20Heatmap%20&%20Optimization.html)
- [Robustness Testing for Algo Trading Strategies — BuildAlpha](https://www.buildalpha.com/robustness-testing-guide/)

---
*Feature research for: Systematic crypto BTC/ETH mean-reversion research engine (Berakah Ring 1)*
*Researched: 2026-06-04*
