# Pitfalls Research

**Domain:** Crypto-quant research engine (BTC/ETH spot, mean-reversion, Ring 1 — validation infra only)
**Researched:** 2026-06-04
**Confidence:** HIGH for statistical and validation pitfalls (Bailey/Lopez de Prado canon, well-established); HIGH for engineering pitfalls (general Python/pandas/parquet); MEDIUM for the crypto-specific data quality details (wash-trade ratios vary across studies); HIGH for the vault/code drift section (project-specific, derived from PROJECT.md constraints, not external research).

> **Reading guide for the roadmapper:** every pitfall ends with a `Phase to address` line that the roadmap should fold into that phase's success criteria. The most load-bearing pitfalls — type-enforced no-look-ahead, OOS split immutability, multiple-testing accounting, and parquet write atomicity — must be solved in Phase 1 / Phase 2 or `PROOF-01` cannot be trusted.

---

## Critical Pitfalls

These are the failure modes that destroy the project's core value (trustworthy OOS edge measurement). If any one of them lands undetected, Berakah is producing scientific fraud at itself and the 6-month kill trigger will fire on a false negative or, worse, the operator will trust a phantom edge.

### Pitfall 1: Look-Ahead Bias via Indicator Calculation (`rolling`, `ewm`, `expanding` on un-shifted series)

**What goes wrong:**
A feature computed as `df['sma_20'] = df['close'].rolling(20).mean()` at bar `t` includes the close of bar `t` itself. If the strategy uses `sma_20` at bar `t` to make a decision *executed at bar `t`*, the decision peeks at the very bar it is deciding on. Backtest Sharpe goes up; OOS Sharpe collapses; operator chases noise for months.

**Why it happens:**
The pandas API makes the bug invisible. `rolling().mean()` is right-aligned by default — at index `t` the window is `[t-19 .. t]` inclusive. The "decision" and the "data the decision is built from" share index `t`, which feels intuitively fine but is wrong: at the *moment of decision* on bar `t`, the bar is not yet closed.

**How to avoid:**
1. **Type-level contract (HYP-02 enforcement).** Every strategy module exposes a single function with a signature shaped like `def signal(history: ClosedBars, now_ts: Timestamp) -> Position`. `ClosedBars` is a frozen view restricted to bars with `close_ts < now_ts`. There is *no constructor* that returns a `ClosedBars` containing a bar at or after `now_ts`. The strategy literally cannot index into the future because the index doesn't exist in the type.
2. **Canonical shift rule.** Any rolling feature must be `.shift(1)` after computation before it is fed to a decision: `df['sma_20'] = df['close'].rolling(20).mean().shift(1)`. Lint this as a project convention — a regex test rejects PRs containing `.rolling(` without an adjacent `.shift(`.
3. **Synthetic leakage probe.** Run every strategy against a corrupted dataset where future returns have been overwritten with random noise. A leak-free strategy's PnL must collapse to noise on this dataset. If it doesn't, it's reading data that hasn't been corrupted — i.e., the future.

**Warning signs:**
- Equity curve too smooth (Sharpe > 3 in-sample).
- Trade markers landing exactly on local extrema.
- IS Sharpe vs OOS Sharpe ratio > 2 (VAL-02 already flags this).
- A strategy whose returns are *uncorrelated* across regimes (sign of fitting noise the strategy can see).

**Phase to address:** **Phase 1** (data + type contract design). Cannot defer — every strategy in every later phase inherits this guarantee.

---

### Pitfall 2: Look-Ahead Bias via Resampling Including the Current Incomplete Bar

**What goes wrong:**
A 1-minute feed is resampled to 5-minute bars while the engine is still partway through a 5-minute window. The "current" 5m bar contains only partial information *plus* its label is the bar's open timestamp. A strategy queries this bar believing it's closed; it is not. In a research engine, this manifests as feeding an aggregated bar to the strategy at `now_ts` when that bar's true close is at `now_ts + 4 minutes 59 seconds`.

**Why it happens:**
`df.resample('5T').agg({...})` happily emits the current incomplete bin. Pandas does not distinguish "closed bar" from "in-progress bar" — that's a domain concept the user must enforce.

**How to avoid:**
1. **Closed-bar guarantee in the data layer (DATA-01).** The historical ingestion pipeline writes only fully-closed bars to parquet. There is a separate `bar_close_ts` column and the loader filters `bar_close_ts <= now_ts`.
2. **Resample with `closed='right', label='right'` and drop the last incomplete bin** explicitly. Better, do resampling once at ingestion (offline) and never at strategy time.
3. **Single source of truth for bar boundaries.** All strategies pull from the same `ClosedBars` view (Pitfall 1's type). The view enforces both the no-future-bar rule *and* the closed-bar rule simultaneously.

**Warning signs:**
- Strategy PnL changes when the engine reruns over the same historical window (non-determinism is the smell).
- The number of bars in a backtest is off-by-one from the expected count.

**Phase to address:** **Phase 1** (data ingestion). Same phase as Pitfall 1 — they share the type contract.

---

### Pitfall 3: Train/Test Split Leakage Across the Boundary

**What goes wrong:**
A feature uses a lookback window of 200 bars. The OOS period starts at `2024-01-01`. The first OOS bar at `2024-01-01 00:00` uses a 200-bar window that *includes 199 bars from the training period*. If feature engineering (e.g., z-score normalization, scaler fitting) was done on the full dataset before the split, the OOS evaluation is contaminated.

A subtler version: regime labels (DATA-02) are computed using a regime classifier that was fit on the entire dataset. Even though the labels themselves are not the signal, they have *seen* the OOS period during fitting and any conditioning on them leaks information.

**How to avoid:**
1. **Purging** (Lopez de Prado, *Advances in Financial Machine Learning*, 2018). Drop any training bars whose feature-construction window overlaps the OOS period. For lookback `L`, drop the last `L` bars of training.
2. **Embargo.** After the OOS period boundary, drop the first `L` bars of OOS too, to prevent the strategy from making a decision on a feature whose tail just barely peeked into training data via overlap.
3. **Stateless feature functions only.** Any feature that requires fitting (scaler, normalizer, regime classifier) must fit on training-window-only data, and fit must be re-run on each walk-forward step. No global pre-computation of fitted artifacts on the full dataset.
4. **Regime labels are *labels, not features* in Ring 1.** Per PROJECT.md, regime labels are used for stratified *reporting* (REPORT-01) and not as a live signal modulator. This sidesteps the regime-classifier-leakage problem entirely until the post-Ring-1 HMM phase.

**Warning signs:**
- OOS Sharpe is consistently higher than IS Sharpe in the *first* OOS window but reverts to noise in subsequent windows (classic boundary-leak signature).
- Removing the embargo *changes* OOS Sharpe materially (proves the embargo was masking a leak).

**Phase to address:** **Phase 2** (backtest + validation engine). VAL-01 must implement purge + embargo as a non-optional default.

---

### Pitfall 4: Test-Set Snooping via Iterative Re-Runs ("Researcher's Multiple Testing")

**What goes wrong:**
The operator runs strategy v1 against OOS, sees Sharpe = 0.6, tweaks a parameter, reruns, sees Sharpe = 0.9, tweaks again, sees Sharpe = 1.2 — and declares `PROOF-01` met. But each rerun used the same OOS data as feedback to the next iteration. The OOS data was effectively used for training, just slowly, and the reported 1.2 is in-sample-by-stealth. The strategy will collapse on truly new data.

This is the most dangerous failure mode in a one-person research project because there is no peer reviewer to catch it.

**Why it happens:**
There is no procedural friction between "look at OOS results" and "go modify the strategy." Karpathy-style vault workflows make the loop even tighter — read result, edit hypothesis, rerun.

**How to avoid:**
1. **Multiple-testing budget.** Every hypothesis note (HYP-01) declares how many trials (parameter combinations × variations) it will explore *before* the first OOS run. The validation engine tracks the cumulative count. The Deflated Sharpe Ratio (Bailey & Lopez de Prado, 2014) is computed against that count, not against 1. A strategy that needed 50 trials to find Sharpe 1.0 has a Deflated Sharpe far below 1.0 and does not clear `PROOF-01`.
2. **Held-out final-validation set.** Carve out a *separate* slice (e.g., the last 6 months of available data) as a "vault" the operator can touch exactly once per strategy. `PROOF-01` is only awarded when the strategy clears both rolling-3-month OOS Sharpe ≥ 1.0 on the walk-forward set *and* Sharpe ≥ 1.0 on the never-touched final-validation set.
3. **Probability of Backtest Overfitting (PBO)** via Combinatorially Symmetric Cross-Validation (CSCV). Bailey, Borwein, Lopez de Prado, Zhu (2015). The engine computes PBO as part of REPORT-01. A PBO > 0.5 means the "best" in-sample strategy is more likely than not to underperform the median OOS — flag it and refuse `PROOF-01`.
4. **Haircut rule.** Apply a 50% haircut to in-sample Sharpe by default (industry rule of thumb cited in Bailey et al.) when communicating the strategy's expected forward performance in the vault report. This sets the operator's expectations correctly even before formal DSR / PBO numbers land.

**Warning signs:**
- A strategy whose OOS Sharpe improved monotonically over several iterations *of edits*. (Suspect every step after the first.)
- A vault report that doesn't disclose how many variations were tried.
- IS-to-OOS Sharpe divergence is small for the *current* run but the report doesn't say what happened in the previous runs.

**Phase to address:** **Phase 2** (validation engine) for the DSR/PBO computation; **Phase 2** for the held-out final-validation slice carve-out; **Phase 3** (reporting) for ensuring REPORT-01 always emits the trial count and PBO.

---

### Pitfall 5: Overfitting via Parameter Search Without Multiple-Testing Correction

**What goes wrong:**
A grid search over (lookback ∈ {10, 20, 50, 100}, threshold ∈ {1.5σ, 2σ, 2.5σ, 3σ}, hold period ∈ {6 bars, 12 bars, 24 bars}) explores 48 combinations. The winner has Sharpe 1.4. The operator reports Sharpe 1.4. The expected maximum Sharpe under the *null hypothesis of no edge* across 48 trials is non-trivially positive; 1.4 may not be statistically significant after correction.

**How to avoid:**
1. **Deflated Sharpe Ratio (DSR)** (Bailey & Lopez de Prado, 2014). DSR deflates the observed Sharpe by the number of trials, the variance of trial Sharpes, the skew and kurtosis of returns, and the sample length. Formally:

    DSR = Probability that the true Sharpe > 0, given the observed maximum Sharpe across N trials.

   Engine must compute DSR for every reported Sharpe in REPORT-01. A strategy with DSR < 0.95 does not clear `PROOF-01`.
2. **Combinatorial Purged Cross-Validation (CPCV)** instead of single walk-forward when grid-searching. CPCV generates thousands of train/test path combinations and gives a distribution of OOS Sharpes; the best-in-sample on the *mean* of this distribution is much harder to game than best-in-sample on a single walk-forward.
3. **Pre-register the search grid.** The hypothesis note (HYP-01) declares the grid before the first run. Adding parameters mid-search invalidates the test and resets the counter.

**Warning signs:**
- A report showing "best parameters" without showing the *distribution* of all parameters tried.
- Sharpe ratio reported as a single number rather than `(observed, deflated)`.
- The "best" parameter set is on the *edge* of the search grid (suggests the grid was sized to find a winner, not to bound the search).

**Phase to address:** **Phase 2**. DSR and the trial-counting infrastructure must land before any strategy is grid-searched.

---

### Pitfall 6: Walk-Forward Windows Too Small or Too Few

**What goes wrong:**
A walk-forward analysis uses a 30-day training window and a 7-day OOS window, rolled across 1 year. There are ~50 OOS windows of 7 days each. A single 7-day window contains only ~2,000 5-minute bars — too few for a Sharpe estimate to converge. The walk-forward "passes" but the per-window Sharpes have a standard error so wide they could be anything.

A different version: walk-forward with 3 OOS windows (e.g., 9 months train, 1 month OOS, 3 rolls). The strategy "validated on OOS" — but on a sample of 3.

**How to avoid:**
1. **Per-window minimum trade count.** Refuse to compute a per-window Sharpe when N_trades < 30. The engine emits a warning and aggregates that window into a wider one.
2. **CPCV by default.** The CPCV method (Lopez de Prado) generates hundreds of train/test paths rather than a single linear walk-forward, drastically improving statistical power per unit of data.
3. **Minimum total OOS span.** Require ≥ 12 rolling-3-month OOS windows for `PROOF-01`. This forces the total OOS span to be substantial (~3 years), which on 5-minute bars is ~315k bars — enough that within-window Sharpe estimates are not noise.
4. **Regime stratification gates this too.** The `PROOF-01` bar requires non-negative Sharpe across all 4 regimes (Bull 2020–21, Bear 2022, Recovery 2023, ETF 2024–). Sample-size-too-small windows fail this automatically because regimes can't be evaluated on 2,000 bars.

**Warning signs:**
- Walk-forward report shows < 10 OOS windows.
- Per-window Sharpe has standard error wider than the reported mean.
- Confidence interval of OOS Sharpe straddles zero.

**Phase to address:** **Phase 2**. Window-sizing constraints are part of the validation engine, not a per-strategy choice.

---

### Pitfall 7: Regime-Specific Overfit (Strategy Works in One Regime, Fails in Another)

**What goes wrong:**
A mean-reversion strategy designed and validated against 2020–2021 data shows Sharpe 1.5. Same strategy run against 2022 (the Luna / FTX bear) shows Sharpe -0.8. Buying every dip in a violent sustained-downtrend regime is catastrophic — the very assumption mean-reversion makes (that prices revert) is violated by ETF/whale-driven sustained directional flows.

This is the *specific* failure mode mean-reversion is exposed to per PROJECT.md's manipulation analysis. It is the residual risk the deferred HMM phase is meant to address.

**Why it happens:**
Mean-reversion's edge depends on stop-hunt overshoots; in a sustained-downtrend regime, stops cluster *with* the trend and there are no overshoots to fade.

**How to avoid:**
1. **Regime-stratified Sharpe is the proof bar, not just a report column.** PROJECT.md already enforces this — `PROOF-01` requires non-negative Sharpe in all 4 regimes. Reject the strategy if any regime is negative, even if aggregate Sharpe is high.
2. **No regime cherry-picking.** The 4 regime labels (DATA-02) are project-canonical and frozen *before* any strategy work begins. Hypothesis notes cannot redefine regime boundaries.
3. **Use exogenous regime boundaries, not data-fit ones, in Ring 1.** The 4 named regimes are macro-defined (bull, bear, recovery, ETF era) — they are not the output of an HMM fit on returns. Using HMM-fit boundaries in Ring 1 is forbidden because the HMM itself would overfit.
4. **Stratified bootstrap.** When computing OOS Sharpe confidence intervals, bootstrap *within* each regime separately, then aggregate. This prevents one strong regime from masking a fragile one.

**Warning signs:**
- One regime carrying the aggregate Sharpe (e.g., regime A Sharpe 2.5, regimes B/C/D Sharpe 0.1 each, aggregate looks fine).
- Drawdowns clustered in a single regime.
- Strategy logic that includes a parameter named "regime" or "mode" — suspect *fit* regime detection.

**Phase to address:** **Phase 1** (regime labels frozen as macro definitions in DATA-02); **Phase 2** (stratified reporting in BT-02 and `PROOF-01` enforcement).

---

### Pitfall 8: Survivorship Bias (Implicit) and Pair-Convention Drift

**What goes wrong:**
Even with the BTC/ETH-spot-only constraint, two sub-pitfalls live here:
1. **Pair convention drift.** Binance uses `BTCUSDT`, Coinbase historically used `BTC-USD`, Kraken uses `XBTUSD` or `XXBTZUSD`. Naively concatenating volume across these without verifying they reference the same instrument (USDT-margined vs USD-margined) produces a frankenstein price series.
2. **Implicit survivorship.** While BTC/ETH themselves have survived, the *exchanges* may not have. Liquidity that existed on Bittrex (delisted), FTX (collapsed), or BitMEX (regulatory restrictions) is unrecoverable in a backtest that uses a current-exchange-only feed. This biases the backtest toward whatever liquidity profile *currently* exists.

**How to avoid:**
1. **One canonical pair per (asset, exchange).** Document in the data manifest: BTC = `Binance:BTCUSDT, Coinbase:BTC-USD, Kraken:XBTUSD`. Loader normalizes to a canonical `(asset, exchange, quote)` tuple. Verify USDT-quote vs USD-quote are *not* mixed.
2. **Per-exchange backtesting first, then sanity-check cross-exchange.** Run the strategy on each Tier-1 exchange in isolation. If Sharpe varies wildly across exchanges, the strategy is exploiting an exchange-specific microstructure quirk, not a real edge.
3. **Document the survivorship boundary.** The vault report (REPORT-01) must state: "This backtest used liquidity from {Binance, Coinbase, Kraken} as they existed in {time range}. Liquidity on delisted venues is not represented." This is honest framing; it does not fix the bias, but it stops the operator from believing the bias is absent.
4. **Note the timezone trap.** All timestamps converted to UTC at ingestion. Period. Any timestamp arithmetic on local-time data is a source of off-by-one bugs that compound.

**Warning signs:**
- Volume series with sudden steps (one exchange's pair was renamed; the loader silently inserted a gap or duplicated bars).
- Sharpe materially better on one exchange than another (microstructure edge, not real alpha).
- Backtest results that change when re-ingesting (timestamp ambiguity).

**Phase to address:** **Phase 1** (DATA-01 canonical pair manifest); **Phase 3** (REPORT-01 survivorship disclosure).

---

### Pitfall 9: Crypto-Specific Data Quality Issues (Wash Trading, Downtime, Anomalies)

**What goes wrong:**
Even on Tier-1 exchanges, wash trading is non-zero. Blockchain Transparency Institute and the NBER 2022 wash-trading study found Binance and Coinbase ~90% clean, Kraken >99% clean. The contaminating 10% on Binance is concentrated in specific time windows (e.g., listing periods, low-volume hours) — exactly the periods where mean-reversion features (volume z-scores, volume spike detectors) can be fooled.

Additionally: exchange downtime (Binance has had ~50 incidents documented), API rate-limit gaps producing silent missing bars, and post-incident price reconciliations producing "ghost" prints.

**How to avoid:**
1. **Tier-1 only is already in scope** — PROJECT.md enforces this. Berakah does not see the 80%+ wash-traded smaller venues.
2. **Sanity bands on volume.** For each (exchange, asset, hour-of-day), compute a long-window volume distribution. Flag bars where volume is > 10× or < 0.1× the typical for that slot. These bars feed strategies but are *also* logged in the data manifest for post-hoc forensics.
3. **Gap detection at ingestion (DATA-01).** Missing bars are explicitly marked, not silently filled. The strategy contract receives a `bar_present: bool` field or equivalent; mean-reversion logic refuses to enter on a bar adjacent to a gap.
4. **Cross-exchange price sanity check.** If BTC on Binance prints $50,000 and Coinbase prints $50,500 at the same UTC second, the spread is normal. If one prints $50,000 and the other prints $48,000, one feed is corrupted; reject the bar from the canonical price.
5. **No funding rates, no contract roll. BTC/ETH spot only.** Per PROJECT.md, spot-only excludes the perp-specific data pitfalls (funding rate, basis, contract roll). Note this in the vault: the spot-only constraint is not just risk management, it is also a *data quality simplification*.
6. **Confirm no split-adjustment problem.** Crypto has no stock-split equivalent. Token reissuance / chain splits exist (BCH from BTC, ETC from ETH) but BTC/ETH spot in the project's time range (2020–) has no chain split that affects price continuity. Document this assumption explicitly.

**Warning signs:**
- A strategy whose edge concentrates on low-volume hours (suspect wash-trade artifacts).
- Backtest performance changes materially when filtering volume outliers.
- The same minute-bar timestamp has wildly different volumes on Binance vs Coinbase.

**Phase to address:** **Phase 1** (DATA-01 ingestion: gap detection, volume sanity, cross-exchange sanity).

---

### Pitfall 10: Transaction Cost / Slippage Under-Modeling (Ring 1 → Ring 2 Trust Bridge)

**What goes wrong:**
Ring 1 has no execution layer. A naive backtest uses mid-price fills with zero cost. A strategy "validates" at Sharpe 1.2. When Ring 2 layers in realistic fees and slippage, the same strategy comes out at Sharpe -0.3 because the edge was smaller than the round-trip cost. Six weeks of Ring 1 work was building on sand.

**Why it happens:**
Operator wants the cleanest possible measurement in Ring 1 and excludes "execution noise." But execution friction is not noise; it is a real component of the edge, and zero is the wrong default.

**How to avoid:**
1. **Conservative-fee floor in BT-01.** Default fees: 10 bps round-trip (5 bps each side). This is *worse* than current Tier-1 taker fees (Binance ~7.5 bps round-trip at base tier; Coinbase Advanced ~12 bps; Kraken Pro ~5 bps), which biases Ring 1 against finding a phantom edge.
2. **Slippage placeholder.** Assume the entry is filled at the *next bar's open* (not the signal-bar's close), and add a small fixed adverse slippage (e.g., 2 bps) per fill. This is Ring 1's stand-in for the Ring 2 slippage model — pessimistic enough that an edge surviving Ring 1 has headroom for Ring 2's real model.
3. **Maker-vs-taker accounting.** PROJECT.md is spot-only; mean-reversion is typically taker (cross the book to enter the overshoot fade). Default to taker fees; do not assume maker rebates exist in Ring 1.
4. **Edge headroom rule.** A strategy that *barely* clears Sharpe 1.0 with conservative-fee Ring 1 settings is not a Ring 2 candidate. The vault report must state the headroom: "Sharpe 1.0 at 10 bps + 2 bps slippage; Sharpe falls to 0.4 at 20 bps + 5 bps slippage." If the second number is negative, the edge is too thin to survive Ring 2.

**Warning signs:**
- A strategy with high turnover (> 50 trades/day on 5-minute bars) and Sharpe barely > 1.0 — the edge is being arbitraged by the cost assumption.
- The vault report does not state the fee/slippage assumption.
- The strategy's win rate is > 60% but average win < average loss (typical of mean-reversion *being eaten by costs*).

**Phase to address:** **Phase 2** (BT-01 cost model defaults); **Phase 3** (REPORT-01 must always emit a fee-sensitivity table).

---

### Pitfall 11: Sharpe Annualization Done Wrong on 5-Minute Crypto Bars

**What goes wrong:**
Operator multiplies a 5-minute-period Sharpe by `sqrt(252)` (the equity-market convention). Crypto trades 24/7/365; the correct annualization factor is `sqrt(365 × 24 × 12) = sqrt(105,120) ≈ 324.2`. Off by a factor of ~2.1×. A strategy reporting Sharpe 1.0 in equity-convention is actually Sharpe ~2.1 in crypto-convention, or vice versa — completely changes `PROOF-01` qualification.

**Why it happens:**
Most quant tutorials, books, and code snippets assume equity markets. `sqrt(252)` is the default in QuantStats, Empyrical, and most backtest libraries. The operator inherits the wrong constant by importing the library.

**How to avoid:**
1. **Single project constant.** Define `ANNUALIZATION_FACTOR_5MIN_CRYPTO = sqrt(365 * 24 * 12) ≈ 324.2` in a single module. Every Sharpe computation reads from there. No magic numbers in strategy code.
2. **Round-trip test.** A synthetic strategy with known Sharpe (e.g., daily Gaussian returns with mean = σ implies annual Sharpe 1.0 by construction) is included in the test suite. The Sharpe computation must reproduce this value. Catches both the annualization factor and the underlying formula.
3. **Report the factor in REPORT-01.** Every vault report states the annualization constant used. Future-Ronald reading a 2026 report in 2028 can verify the math.
4. **Don't import equity-default libraries blindly.** QuantStats `sharpe()` defaults to 252. Either override the periods parameter or compute Sharpe manually.

**Warning signs:**
- A strategy's reported Sharpe is ~2× or ~0.5× of what it "feels like" from the equity curve.
- Two different reports in the vault disagree on Sharpe for the same strategy (different annualization conventions used).
- The reported Sharpe does not change when the bar interval is changed (a sign that the factor isn't being applied at all).

**Phase to address:** **Phase 2** (validation engine — single source of truth for the constant).

---

## Moderate Pitfalls

### Pitfall 12: Statistical Significance Confusion — Edge vs Noise vs Costs

**What goes wrong:**
A strategy's "edge" turns out to be (a) within the standard error of zero (sample size too small), (b) a fee-rebate artifact (the strategy is harvesting maker rebates, not directional edge), or (c) clustered around a small number of high-volatility events (e.g., 80% of PnL comes from 5 trading days — the "edge" is a few lucky regimes).

**How to avoid:**
- **Bootstrap confidence intervals on Sharpe.** Report `Sharpe = 1.1 ± 0.4 (95% CI)`. If the lower bound straddles zero, no edge.
- **PnL concentration test.** If > 50% of PnL comes from < 5% of trading days, flag the strategy as event-driven, not edge-driven. Mean-reversion harvesting overshoots should produce a more uniform PnL distribution.
- **Strip rebates.** Always backtest at taker fees (no maker rebate assumption) for Ring 1. If the edge dies, it was a fee artifact.

**Warning signs:**
- Tight equity curve with two enormous up-days.
- Sharpe goes from 1.2 to -0.3 when one month is excluded.

**Phase to address:** **Phase 2** (validation engine).

---

### Pitfall 13: Variance Non-Stationarity (Sharpe Lies Under Vol Clustering)

**What goes wrong:**
Sharpe ratio assumes IID returns. Crypto returns exhibit strong volatility clustering — calm regime, then a 30% week, then calm again. Aggregate Sharpe across the whole sample understates risk in the calm sub-periods and overstates risk in the volatile ones.

**How to avoid:**
- **Vol-targeted position sizing** is in scope (BT-01) — already addresses this at the strategy level by scaling positions down in high-vol regimes.
- **Report rolling Sharpe**, not just aggregate. PROJECT.md's `PROOF-01` bar uses rolling-3-month — this is exactly the right framing.
- **Use Sortino ratio as a sanity-check second metric.** Sortino downside-only denominator is less misled by occasional volatility spikes.

**Phase to address:** **Phase 2** (BT-02 includes rolling Sharpe in the standard report; vol-targeting per BT-01).

---

### Pitfall 14: Hyperparameter Tuning on OOS Data

**What goes wrong:**
A specific sub-case of Pitfall 4: the operator notices OOS Sharpe is 0.8 (below `PROOF-01` bar), checks which parameter set produced it, sees that a slightly different parameter set would have produced Sharpe 1.1, "decides" the original parameter choice was wrong, and reruns with the better one. OOS is now being used for hyperparameter selection — i.e., it has become training data.

**How to avoid:**
- **Engine-enforced split immutability.** VAL-01 already says splits are "enforced by the engine, never picked post-hoc." Concretely: the train/OOS boundary is a function of the *hypothesis note's commit SHA + creation timestamp* (frontmatter-pinned). Modifying it requires creating a new hypothesis note.
- **Configuration hash in every report.** REPORT-01 emits a hash of (strategy code, parameter set, data range, OOS split). Two reports with the same hash should have identical Sharpes (reproducibility). Two reports with different hashes are different experiments — count them in the multiple-testing budget.

**Phase to address:** **Phase 2** (VAL-01 immutable splits); **Phase 3** (REPORT-01 config hash).

---

### Pitfall 15: Engineering Non-Determinism (Mutable State, Unpinned Random Seeds)

**What goes wrong:**
Backtest run on Tuesday produces Sharpe 1.0. Same code, same data, same parameters re-run on Wednesday produces Sharpe 0.85. The 15-point discrepancy is process noise from (a) an unpinned random seed in a bootstrap step, (b) shared mutable state in a strategy module that the previous run polluted, (c) Python dict iteration order leaking into a feature ordering. Operator doesn't know which run to trust; trust in the engine collapses.

**How to avoid:**
- **Pin every seed.** A single project seed constant; every numpy/pytorch/random/scikit-learn call uses it. Add a CI test that runs the same backtest twice and asserts byte-equal results.
- **No module-level state in strategy modules.** Strategies are functions, not classes with attributes. State that *must* persist (e.g., a fitted scaler) is passed in as an argument from the caller.
- **Determinism test in the validation pipeline.** Every strategy must pass a "run twice, identical output" check before Sharpe is reported.

**Warning signs:**
- Two runs of the same configuration produce different Sharpes (even by 0.01).
- Test suite has flaky tests.
- Strategy module has class-level or module-level variables that aren't constants.

**Phase to address:** **Phase 1** (engine architecture — declarative/functional strategy modules); **Phase 2** (CI determinism test).

---

### Pitfall 16: Parquet Concurrent-Write Corruption

**What goes wrong:**
Two backtests run in parallel, both writing trade ledgers to `backtests/ledger.parquet`. Parquet is not transactional. One write half-completes; the other appends. The file is now corrupted; reading it back fails or, worse, returns truncated data. A vault report references this corrupted file as "the validation record" — the validation record is silently wrong.

**How to avoid:**
- **Per-backtest unique output paths.** Each backtest writes to `backtests/{strategy_id}/{run_id}/ledger.parquet`. No two backtests ever target the same file. `run_id` is a UUID or hash.
- **Write-temp-then-rename pattern.** Write to `ledger.parquet.tmp`, fsync, atomic rename to `ledger.parquet`. POSIX rename is atomic on the same filesystem.
- **No streaming writes to parquet.** Parquet writes are append-by-rewrite. Build the dataframe in memory, write once, end of story.
- **If multiple-runs-to-same-store is unavoidable later (Ring 2+), use Delta Lake or Iceberg** — they add ACID on top of parquet. For Ring 1, the simpler rule above suffices.

**Warning signs:**
- `pyarrow.lib.ArrowInvalid: Could not open Parquet input source ... metadata not found` errors.
- Two backtests producing fewer total trades than expected (one overwrote the other).
- File size suddenly shrinking on disk.

**Phase to address:** **Phase 1** (output directory convention in BT-02 design).

---

### Pitfall 17: Off-by-One on `iloc` vs `loc` (Time-Series Indexing Bugs)

**What goes wrong:**
`df.iloc[i]` is positional. `df.loc[t]` is label-based. Mixing them when a timestamp is also coincidentally a small integer (e.g., epoch hour, or a contiguous integer index that *looks* like a timestamp) silently selects the wrong row. The strategy makes a decision on the wrong bar. Backtest still "works." Sharpe is junk.

**How to avoid:**
- **Always-typed indices.** The bar DataFrame's index is `pd.DatetimeIndex` (UTC, nanosecond resolution). Never reset to integer index inside engine code.
- **No mixed access.** Linter rule: a single function uses either `.iloc` or `.loc`, not both, unless explicitly justified in a comment.
- **Test on a year-spanning fixture.** Pure unit tests on a 100-bar fixture won't catch indexing bugs that emerge from cross-month boundaries, DST (irrelevant in UTC, but), or timestamp wraparound. The integration test uses ≥ 1 year of data.

**Phase to address:** **Phase 1** (engine architecture); **Phase 2** (test fixtures).

---

### Pitfall 18: Float Comparison Errors in PnL Accounting

**What goes wrong:**
`if pnl == 0:` fails because `pnl` is `1.4e-17` (float arithmetic residue). The "flat" position is treated as not flat. Fee accounting double-counts. PnL drifts by sub-penny amounts that aggregate over millions of bars into meaningful Sharpe distortion.

**How to avoid:**
- **Use `Decimal` for cash-side accounting.** Position quantities can stay float; cash, fees, and PnL accumulate in `decimal.Decimal` with explicit precision.
- **Or use `math.isclose(pnl, 0, abs_tol=1e-9)`** for comparisons. Never `==` on floats in domain logic.
- **PnL invariant test.** At the end of every backtest, sum of (entry PnL contributions) + (exit PnL contributions) + (cumulative fees) must equal final equity − initial equity, to within `1e-6`. If not, the accounting has a leak.

**Phase to address:** **Phase 2** (BT-01).

---

### Pitfall 19: Test That "Passes" Because It Trains on Test Data

**What goes wrong:**
An integration test asserts "strategy Sharpe > 1.0 on test data" — but the test data *is* the data the strategy was tuned on. The test passes; the strategy is broken on truly new data. The CI is rubber-stamping the bug.

**How to avoid:**
- **Test fixtures are synthetic and known-truth.** Integration tests use *generated* return series with known properties (e.g., a mean-reverting AR(1) process where the true OOS Sharpe is analytically computable). The test asserts "engine recovers the true Sharpe within tolerance" — not "engine produces a high Sharpe on real data."
- **Real-data tests are characterization tests, not assertions.** They store the Sharpe for a fixed reference strategy on a fixed data slice and compare to the stored value (detect regressions in the engine, not strategy quality).

**Phase to address:** **Phase 2** (test architecture).

---

### Pitfall 20: Vault / Code Drift (Hypothesis Note Diverges from Linked Strategy Module)

**What goes wrong:**
Hypothesis note `H-003 - z-score reversion` describes a strategy that buys at z < -2.0 and exits at z > 0. The linked code module evolved over time; it now exits at z > 0.5. The vault report references the old hypothesis but is computed from the new code. Reader concludes the hypothesis-as-described works; in reality the hypothesis-as-described was never tested.

This is a *first-class* concern per the project framing — the vault is the research record. If the record is inconsistent with the experiment, the research is fiction.

**How to avoid:**
1. **Frontmatter binding.** Every hypothesis note's YAML frontmatter contains:
   ```yaml
   strategy_module: src/berakah/strategies/zscore_reversion.py
   strategy_commit: a3f1c0d  # pinned to a specific git SHA
   data_manifest: data/manifests/2020-2024.toml
   data_commit: 8b2e4f1
   ```
2. **Reproducibility hash in every report.** REPORT-01 emits a hash of (strategy file content at the pinned SHA, parameter set, data manifest). The hash is in the vault report. Two reports with the same hash are identical experiments; different hash = different experiment (must be re-counted in multiple-testing budget).
3. **Pre-commit hook.** Before the engine writes a report to the vault, it verifies: (a) git working tree is clean, (b) the pinned commit SHA matches the current HEAD or is an ancestor, (c) the strategy file at that SHA exists. Refuse to write if any check fails.
4. **One-way coupling.** Hypothesis notes reference strategy modules and commits. Strategy modules do not reference hypothesis notes. Avoids circular drift: the strategy module is the engine; the hypothesis is its interpretation.
5. **Vault report is generated, not edited.** REPORT-01 outputs are generated files at fixed paths. The operator does not hand-edit them. Adding commentary goes into a *sibling* note (e.g., `H-003 - postmortem.md`), not into the report itself.

**Warning signs:**
- A vault report whose frontmatter SHA doesn't appear in `git log`.
- The strategy module's current behavior contradicts the natural-language description in the linked hypothesis note.
- The vault has a report but `git status` shows uncommitted changes to the strategy module.

**Phase to address:** **Phase 1** (frontmatter schema for hypothesis notes — HYP-01); **Phase 3** (REPORT-01 reproducibility hash, pre-commit guard).

---

### Pitfall 21: Vault / Repo Out of Sync (Code Committed, Report Not — or Vice Versa)

**What goes wrong:**
Operator runs a backtest, gets a great report, commits the strategy code, *forgets to commit the vault*. Months later they re-run, get a different result (data has grown, or a bug was fixed), the vault still shows the old report, and the operator believes the old result is valid because the code is "the same."

**How to avoid:**
- **Single commit boundary.** A successful backtest writes (a) the report to `berakah_KB/`, (b) the parquet outputs to `backtests/`, (c) a manifest entry. A single git commit captures all three. The engine emits a suggested commit message and prompts the operator (or in headless mode, refuses to proceed without `--commit` flag).
- **`git status` clean assertion** before any report is treated as canonical.
- **Vault index.** A vault file `berakah_KB/_index.md` lists every report with `(hypothesis_id, strategy_commit, report_commit, timestamp)`. New reports must add an entry to the index in the same commit. The index is the audit log.

**Phase to address:** **Phase 3** (REPORT-01 commit-coupling guard).

---

### Pitfall 22: Process Pitfall — Operator Falls in Love With One Hypothesis

**What goes wrong:**
Hypothesis H-007 looked promising at iteration 3. Iterations 4 through 12 fail. Operator interprets each failure as "almost there, just need to tweak X" rather than "this hypothesis is false." Six weeks pass; the 6-month kill window approaches with no real progress because all of it went into one dead idea.

**How to avoid:**
- **Per-hypothesis trial budget declared in the note.** If the budget is 20 grid-search points and the hypothesis hasn't cleared `PROOF-01` after 20, the note is closed and a postmortem note is written. New ideas go in new notes.
- **Hypothesis cooling-off.** After a hypothesis is closed without proof, no new variant of the same hypothesis may be opened for 14 days. Forces the operator to explore the search space before doubling down.
- **Visible kill-window countdown.** The vault `_index.md` shows the remaining time against the 6-month trigger. Concrete deadline pressure prevents indefinite chase.

**Phase to address:** **Phase 3** (vault-level workflow / process documentation). Not engine-enforced — this is a discipline aid.

---

### Pitfall 23: Process Pitfall — Building Infrastructure Before Finding an Edge

**What goes wrong:**
Operator (or Claude) spends week 1 building a sophisticated event-driven event-loop architecture, week 2 building a multi-asset framework, week 3 building a plugin system for indicators — and arrives at week 6 with zero strategies tested. The 6-week MVP target slips because the infrastructure was built for hypothetical Ring 4 needs, not for the single Ring 1 deliverable.

This violates PROJECT.md's MVP discipline ("build the smallest research machine that proves one real edge before broadening").

**How to avoid:**
- **Smallest engine first.** Ring 1's engine handles exactly: BTC/ETH spot, 5-minute bars, single strategy at a time, single OOS validation window per strategy. No multi-asset abstractions. No strategy plugin registry. No event-loop. Pure batch.
- **Vertical slice through `PROOF-01` first.** Week 1: get one toy strategy (e.g., naive 1σ z-score reversion) running end-to-end through data → backtest → report → vault, even if every component is a 50-line script. Weeks 2–6: harden each component while iterating on real strategies.
- **Refactor on the second use, not the first.** Don't generalize until at least two real strategies share the same need.

**Phase to address:** **Phase 1** (scope discipline at the engine architecture stage).

---

## Minor Pitfalls

### Pitfall 24: Forgetting That UTC Is Canonical

Document and lint: every timestamp in the system is UTC. Local-time-zone math is forbidden. **Phase 1.**

### Pitfall 25: Logging Strategy Returns Without Position Sizing Detail

The trade ledger (BT-02) must include both the raw signal return and the *vol-targeted* position-adjusted return. Reports that conflate the two are misleading. **Phase 2.**

### Pitfall 26: Forgetting to Test on Data the Engine Has Never Seen

Reserve the most recent 3 months of available data as a hard-locked "never look at this until `PROOF-01`" set, separate from the walk-forward OOS set used during development. This is the final-validation slice from Pitfall 4. **Phase 2.**

### Pitfall 27: Reporting OOS Sharpe Without Confidence Intervals

Single-number Sharpes lie about precision. Every Sharpe in every report includes a bootstrap 95% CI. **Phase 2.**

### Pitfall 28: Letting the Hypothesis Note's Author-Date Be the Single Source of Truth

The hypothesis note's frontmatter has both `created_ts` (when the operator wrote the idea) and `frozen_ts` (when the strategy code and OOS boundary were finalized). The `frozen_ts` is what governs the OOS split, not the `created_ts`. Without this distinction, editing the note after running the backtest silently moves the OOS boundary. **Phase 1.**

### Pitfall 29: Annualization Drift in Reports Across Phases

When Ring 2 lands and reports include realized live-paper PnL, the Sharpe computation must use the *same* annualization constant as Ring 1 reports for the comparison to be valid. Pin the constant in a shared module imported by both. **Phase 2** (forward-looking — pin the constant location so Ring 2 inherits it).

### Pitfall 30: Assuming Mean-Reversion Is Symmetric

Crypto's overshoots downward (panic) and upward (FOMO) are not statistically identical. A mean-reversion strategy with a single `|z| > 2` threshold treats them symmetrically; reality is asymmetric. This is *not* a Ring 1 critical issue but a flag for the strategy author to consider separating long-side and short-side thresholds. **Phase 2** (strategy design guidance, not engine constraint).

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|---|---|---|
| Data ingestion (DATA-01) | Pitfalls 2, 8, 9, 16, 24, 28 — timestamp drift, pair conventions, gaps, wash-trade artifacts, parquet writes, UTC discipline, frontmatter timestamp pinning | One-shot ingestion script with explicit UTC normalization, gap markers, per-pair canonical naming, atomic parquet writes, deterministic output paths |
| Regime labels (DATA-02) | Pitfalls 7, 3 — regime overfit if labels are HMM-derived; leak if labels were computed using OOS data | Use macro-defined frozen regime boundaries (the 4 named regimes); document the dates in a TOML manifest; no data-fit regime detection in Ring 1 |
| Type contract (HYP-02) | Pitfalls 1, 2 — the entire load-bearing guarantee against look-ahead | `ClosedBars` type with no future-bar constructor; lint rule against raw `df.iloc` outside the data layer |
| Hypothesis note schema (HYP-01) | Pitfalls 20, 21, 22, 28 — vault/code drift, hypothesis-author lock-in, frozen vs created timestamps | YAML frontmatter binding to strategy file + commit SHA + data manifest + frozen_ts + trial budget |
| Backtest engine (BT-01) | Pitfalls 10, 15, 17, 18 — fee modeling, determinism, indexing, float math | Conservative fee floor (10 bps + 2 bps slippage), pinned seeds, typed DatetimeIndex everywhere, Decimal cash accounting |
| Validation engine (VAL-01, VAL-02) | Pitfalls 3, 4, 5, 6, 11, 14 — split leakage, snooping, multi-testing, window sizing, Sharpe annualization, OOS split immutability | Purge + embargo by default; held-out final-validation slice; DSR + PBO + CPCV in REPORT-01; minimum trade-count gates; engine-pinned splits keyed off hypothesis frozen_ts |
| Backtest output (BT-02) | Pitfalls 13, 25, 27 — non-stationarity, position sizing transparency, CI reporting | Rolling Sharpe + Sortino; raw vs position-adjusted PnL columns; bootstrap CI on every Sharpe |
| Vault report (REPORT-01) | Pitfalls 4, 8, 14, 20, 21, 22 — N-trials disclosure, survivorship disclosure, config-hash, vault/repo sync, kill-window countdown | Mandatory report sections: trial count, DSR, PBO, fee sensitivity, regime breakdown, survivorship caveat, config hash, vault-index entry |
| `PROOF-01` qualification | Pitfalls 4, 5, 7 — phantom edge passes the bar | Multi-gate: rolling-3m OOS Sharpe ≥ 1.0 AND non-negative per-regime Sharpe AND DSR ≥ 0.95 AND PBO ≤ 0.5 AND holds on never-touched final-validation slice |

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|---|---|---|---|
| Skip the type-level `ClosedBars` contract; rely on convention + tests | Saves 1–2 days of design work | Look-ahead bugs become possible per strategy, not eliminated by construction; trust in the engine erodes the first time one is found | **Never.** This is the load-bearing guarantee for Ring 1's core value |
| Hardcode `sqrt(252)` from a copy-pasted equity backtest template | Familiar number; matches industry tutorials | Every Sharpe in the project is wrong by ~2.1×; every report has to be regenerated | **Never** — Ring 1 is crypto-specific from day 1 |
| Single linear walk-forward instead of CPCV | Simpler to implement (~50 LOC vs 200) | Lower statistical power, higher PBO, easier to overfit | Acceptable for the *first* working end-to-end vertical slice (week 1). Must be replaced by CPCV before any `PROOF-01` claim |
| No DSR / PBO computation; just report raw OOS Sharpe | Faster reports | Operator cannot tell phantom edges from real ones; `PROOF-01` becomes unreliable | Acceptable on the vertical-slice toy strategy only; required before the second hypothesis is tested |
| No final-validation slice; use rolling OOS as the single OOS | Saves data | OOS becomes contaminated within a few iterations | **Never.** The held-out slice is the firewall against Pitfall 4 |
| Skip vol-targeting in BT-01 | Simpler PnL math | Sharpe non-stationarity makes the 4-regime stratified Sharpe noisier; harder to clear `PROOF-01` | **Never** — BT-01 explicitly requires vol-targeting |
| Skip cost modeling in BT-01 (zero fees) | Cleanest "raw alpha" measurement | Strategies that pass Ring 1 die in Ring 2; six weeks of work lost | **Never** — use conservative defaults |
| Manual hypothesis-to-strategy-to-report cross-referencing | No frontmatter schema work | Vault drift within 2–3 hypotheses; operator cannot trust the historical record | Acceptable for the very first toy hypothesis; required before the second |
| Concurrent backtest runs to the same parquet file | Faster iteration | Silent data corruption | **Never.** Per-run unique output paths from day 1 |

---

## Integration Gotchas

Common mistakes when connecting to external services. Berakah's external surface is small (Tier-1 exchange historical data APIs, Obsidian vault filesystem, Git), so this list is short.

| Integration | Common Mistake | Correct Approach |
|---|---|---|
| Binance historical API | Treating klines `[open_time, ..., close_time, ...]` as inclusive of close_time | `close_time` is the *last millisecond* of the bar; treat the bar as closed at `close_time + 1ms` for safety |
| Coinbase historical API | Pagination quietly drops the boundary bar; rate limits trigger silent empty responses | Verify bar count == expected from the requested time range; retry with backoff; fail loudly on empty |
| Kraken historical API | XBT vs BTC naming inconsistency; trades-vs-OHLC endpoint shape mismatch | Canonicalize at ingestion to `BTC`; document the endpoint used in the data manifest |
| Obsidian vault | Treating it as a database with concurrent writes | It is a Git-backed Markdown filesystem; one writer at a time, atomic file-level operations, never edit while Obsidian app has a file open |
| Git | Forgetting the vault is in the same repo (or in a separate one); inconsistent staging | Single-repo monorepo with `berakah_KB/` and code; one commit per validation event spans both |
| Parquet via pyarrow / fastparquet | Mixing engines across reads/writes of the same dataset | Pin one engine project-wide; document in the data layer |

---

## Performance Traps

Berakah's Ring 1 scale is small (BTC + ETH × 3 exchanges × ~6 years × 5-minute bars ≈ 6M bars per asset-exchange, ~36M bars total). Performance traps mostly don't apply; the few that do:

| Trap | Symptoms | Prevention | When It Breaks |
|---|---|---|---|
| Loading the entire parquet into memory per backtest | RAM pressure on a laptop with 16GB; swap thrashing | Per-strategy iterator pattern: stream bars in chunks, hold only the active window | Above ~50M bars or in Ring 4 multi-asset (defer) |
| Re-computing features per backtest | Backtest takes minutes instead of seconds; iteration loop is slow → operator cuts corners | Cache features in parquet at ingestion; backtest reads pre-computed features | When iteration time exceeds ~30 seconds, operator stops experimenting |
| CPCV with too many splits | Memory explosion (number of paths grows combinatorially); backtest time becomes prohibitive | Cap CPCV at ~100–200 paths; this is sufficient for PBO estimation per Bailey et al. | When path count > 1000 |
| Bootstrap CI with 10,000 resamples per Sharpe | Report generation takes minutes | Default to 1,000 resamples; this is statistically sufficient for 95% CI on Sharpe | Never breaks at MVP scale |

---

## Security Mistakes

Ring 1 has *no live capital* and *no API keys for trading*. Read-only historical-data API access is the only external auth. Even so:

| Mistake | Risk | Prevention |
|---|---|---|
| Committing exchange API keys (even read-only) to the repo | Key gets scraped; rate-limited or abused; data quality suffers | `.gitignore` keys; load from environment; pre-commit hook scans for secret patterns |
| Hardcoding the `berakah_KB/` absolute path | Code breaks on a fresh clone; vault data not portable | Use a `BERAKAH_VAULT_PATH` env var with a sensible default relative to the repo |
| Trusting downloaded historical data without integrity checks | A corrupted download silently poisons every subsequent backtest | Checksum manifests in the data directory; ingestion fails loudly on hash mismatch |
| Running the engine as a privileged user | Misbehaving backtest could write to system paths | Run as the operator's normal user; engine writes only within the repo and a configured cache dir |

---

## UX Pitfalls (Operator Experience)

This is a single-operator research engine. "UX" means the operator's cognitive ergonomics.

| Pitfall | Operator Impact | Better Approach |
|---|---|---|
| Engine prints raw Sharpe with no context | Operator can't tell if it's good, bad, or significant | Report card format: `Sharpe 1.04 (CI: 0.81–1.27), DSR 0.97, PBO 0.18 — PASS` |
| Long backtest with no progress indication | Operator alt-tabs, forgets, returns confused | tqdm progress bar with ETA; structured log line every 10% |
| Vault report buried in a deep folder | Operator can't find the latest result | Top-level `berakah_KB/_index.md` lists most recent reports, sorted by date |
| Failure modes that print stack traces instead of plain English | Operator (PM mode) cannot triage without Claude | Engine error messages name the pitfall by number: `ERR-LOOKAHEAD-01: feature 'sma_20' depends on bar t at decision time t. See PITFALLS.md#pitfall-1.` |
| Reports written in code-tone, not narrative | Operator can't share findings or reason about them | Vault reports are Markdown with a narrative summary section followed by tables, not a JSON dump |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces. Run through this before declaring any phase done.

- [ ] **Data ingestion (DATA-01):** Often missing gap markers; downstream code silently treats gaps as zero-return bars — verify a synthetic-gap test produces a `bar_present=False` row and the strategy refuses to trade adjacent
- [ ] **Data ingestion (DATA-01):** Often missing UTC enforcement; one exchange's timestamps end up local — verify all three exchanges' timestamps for the same wall-clock moment agree to within 1 second
- [ ] **Type contract (HYP-02):** Often missing the constructor restriction; the type exists but accepts any DataFrame — verify there is *no* code path that constructs a `ClosedBars` containing a future bar, by attempting it in a test and asserting compilation/runtime failure
- [ ] **Backtest engine (BT-01):** Often missing the determinism guarantee; runs twice with different Sharpes — verify by running the test suite twice and diff'ing the report bytes
- [ ] **Validation engine (VAL-01):** Often missing the purge+embargo; splits are clean by hypothesis but features leak across — verify by computing the first OOS bar's feature window and confirming no training-period bars are in it
- [ ] **Validation engine (VAL-02):** Often missing the IS-OOS divergence threshold as a *hard refusal*; it logs but doesn't block — verify VAL-02 prevents the engine from emitting a `PROOF-01` claim when divergence > threshold
- [ ] **Report (REPORT-01):** Often missing the trial count and DSR; report has only raw OOS Sharpe — verify every report includes (raw Sharpe, deflated Sharpe, trial count, PBO, regime breakdown, fee sensitivity)
- [ ] **Report (REPORT-01):** Often missing the configuration hash; two structurally-different runs produce identical-looking reports — verify the hash changes when any of (code SHA, parameters, data manifest, split boundaries) change
- [ ] **Vault sync:** Often missing the commit-coupling; report exists in vault but corresponding strategy commit doesn't exist in git — verify the pre-commit guard refuses to write a report when the strategy SHA isn't reachable in `git log`
- [ ] **`PROOF-01` gate:** Often missing the per-regime check; aggregate Sharpe passes but one regime is -0.5 — verify the engine refuses to award `PROOF-01` if any per-regime Sharpe is negative
- [ ] **`PROOF-01` gate:** Often missing the final-validation slice check; rolling OOS passes but the locked-away slice was never tested — verify the engine requires *both* checks to pass before the badge is issued

---

## Recovery Strategies

When pitfalls occur despite prevention, here's the recovery cost and steps.

| Pitfall | Recovery Cost | Recovery Steps |
|---|---|---|
| Look-ahead bias discovered in a strategy mid-research (Pitfalls 1, 2) | MEDIUM | (1) Identify which strategies are affected by the leaky feature. (2) Mark their existing reports as invalidated in the vault index. (3) Fix the type contract or feature pipeline. (4) Re-run affected strategies. (5) Add a regression test reproducing the original leak. |
| OOS split was leaked via iterative tweaks (Pitfall 4) | HIGH | (1) Mark the strategy as invalidated. (2) Acquire genuinely new data (extend the time range forward by at least 3 months). (3) Re-run the strategy on the new slice as the *true* OOS. (4) If it survives, the original work was lucky; if it doesn't, abandon and learn. |
| Regime-specific failure discovered after `PROOF-01` was tentatively claimed (Pitfall 7) | LOW | (1) Withdraw the `PROOF-01` claim from the vault index. (2) Document the failing regime in a postmortem note. (3) Either accept the strategy as regime-conditional (deferred to post-Ring-1 HMM phase) or close the hypothesis. |
| Parquet file corruption (Pitfall 16) | LOW | (1) Re-run the backtest with unique output paths. (2) Add the missing path-uniqueness convention to the engine. (3) Verify no vault report references the corrupted file. |
| Vault/code drift (Pitfalls 20, 21) | MEDIUM | (1) Walk back through `git log` to find the last point where vault and code were consistent. (2) Re-run from that point with the now-pinned frontmatter. (3) Reconcile any vault reports written in between as "speculative — pre-pinning era." |
| Wrong Sharpe annualization in shipped reports (Pitfall 11) | LOW | (1) Fix the constant. (2) Re-generate every report (cheap: backtest outputs are cached). (3) Issue a vault note explaining the correction. |
| Non-deterministic backtest results (Pitfall 15) | LOW–MEDIUM | (1) Add the determinism CI test. (2) Run it; identify the unpinned source. (3) Fix; verify byte-equal reproduction. (4) Re-run any reports whose hash changes. |
| Operator falls in love with a dead hypothesis (Pitfall 22) | LOW (process) | (1) Close the hypothesis note with a postmortem. (2) Enforce the cooling-off period. (3) Move on to a structurally different hypothesis (e.g., different feature family, not just different parameters). |

---

## Pitfall-to-Phase Mapping (Summary)

The roadmapper folds these into phase success criteria. Each pitfall maps to the *earliest* phase that can prevent it; some span multiple phases (prevention + verification).

| Pitfall | Prevention Phase | Verification |
|---|---|---|
| 1. Look-ahead via rolling/ewm | Phase 1 | `ClosedBars` type compiles; synthetic-noise probe test passes; lint rule blocks raw `.rolling().mean()` |
| 2. Look-ahead via resampling | Phase 1 | Ingestion test asserts no incomplete bars in stored parquet; resample-at-strategy-time is forbidden by convention |
| 3. Train/test boundary leakage | Phase 2 | Purge+embargo on by default; test asserts first OOS bar's feature window excludes training bars |
| 4. Test-set snooping | Phase 2, 3 | Multiple-testing budget tracked; DSR / PBO in REPORT-01; final-validation slice locked at hypothesis creation |
| 5. Parameter-search overfit | Phase 2 | DSR computed for every grid-searched strategy; PBO ≤ 0.5 required for `PROOF-01` |
| 6. WF windows too small | Phase 2 | Engine refuses per-window Sharpe with < 30 trades; CPCV default; minimum 12 rolling-3m windows for `PROOF-01` |
| 7. Regime-specific overfit | Phase 1, 2 | Frozen macro regime labels; per-regime Sharpe gate on `PROOF-01` |
| 8. Survivorship / pair drift | Phase 1, 3 | Canonical pair manifest; per-exchange isolation backtests; survivorship caveat in every REPORT-01 |
| 9. Crypto data quality | Phase 1 | Tier-1-only enforced; gap detection; cross-exchange sanity; volume outlier flagging |
| 10. Cost/slippage under-modeling | Phase 2, 3 | Conservative fee floor (10 bps + 2 bps); fee-sensitivity table in REPORT-01 |
| 11. Wrong Sharpe annualization | Phase 2 | Single project constant; round-trip test on known-Sharpe synthetic data |
| 12. Significance vs noise vs costs | Phase 2 | Bootstrap CI on every Sharpe; PnL concentration test; taker-fee default |
| 13. Variance non-stationarity | Phase 2 | Rolling Sharpe + Sortino; vol-targeting in BT-01 |
| 14. Hyperparam tuning on OOS | Phase 2, 3 | Engine-pinned splits keyed off `frozen_ts`; config hash in REPORT-01 |
| 15. Non-determinism | Phase 1, 2 | Pinned seeds; declarative strategy modules; CI run-twice-byte-equal test |
| 16. Parquet concurrent writes | Phase 1 | Per-run unique output paths; atomic temp-and-rename |
| 17. iloc/loc off-by-one | Phase 1, 2 | DatetimeIndex enforced; lint rule; year-spanning integration test |
| 18. Float comparison in PnL | Phase 2 | Decimal for cash accounting; PnL invariant test at end of every backtest |
| 19. Tests train on test data | Phase 2 | Synthetic known-truth fixtures; characterization tests on real data |
| 20. Vault/code drift | Phase 1, 3 | Hypothesis frontmatter schema; reproducibility hash; pre-commit guard |
| 21. Vault/repo out of sync | Phase 3 | Single-commit boundary; vault `_index.md` audit log |
| 22. Operator falls in love | Phase 3 | Per-hypothesis trial budget; cooling-off; visible kill-window countdown |
| 23. Infra-before-edge | Phase 1 | Smallest engine first; vertical-slice-through-`PROOF-01` discipline; refactor-on-second-use rule |
| 24. UTC discipline | Phase 1 | Ingestion converts to UTC; lint rule against `tz_localize` of non-UTC |
| 25. Position-sizing transparency | Phase 2 | Trade ledger has both raw and vol-targeted PnL columns |
| 26. Locked final-validation slice | Phase 2 | Engine-pinned final slice; one-touch-per-strategy guard |
| 27. CI-less Sharpe reports | Phase 2 | Bootstrap CI on every Sharpe in REPORT-01 |
| 28. Frozen vs created timestamps | Phase 1 | Hypothesis frontmatter has both; OOS split keyed off `frozen_ts` |
| 29. Annualization drift across rings | Phase 2 (forward) | Constant lives in a shared module that future Ring 2 imports |
| 30. Mean-reversion symmetry | Phase 2 | Documentation in strategy author guide; not engine-enforced |

---

## Sources

- Bailey, D. H., & Lopez de Prado, M. (2014). *The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality.* [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551). [Full PDF](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf). Canonical source for DSR formula and the multiple-testing problem in backtesting.
- Bailey, D. H., Borwein, J. M., Lopez de Prado, M., & Zhu, Q. J. (2015). *The Probability of Backtest Overfitting.* [Davidhbailey.com PDF](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf). Source for PBO and CSCV.
- [Deflated Sharpe Ratio — Wikipedia](https://en.wikipedia.org/wiki/Deflated_Sharpe_ratio). Verified summary of DSR / PBO / haircut concepts.
- [Probability of Backtest Overfitting (CRAN pbo package)](https://cran.r-project.org/web/packages/pbo/vignettes/pbo.html). Implementation reference for CSCV.
- Lopez de Prado, M. (2018). *Advances in Financial Machine Learning.* [Reading notes summary](https://reasonabledeviations.com/notes/adv_fin_ml/). Source for purged cross-validation, embargo, CPCV, and the 10-reasons-ML-funds-fail material.
- [GARP — 10 Reasons Most ML Funds Fail (Lopez de Prado)](https://www.garp.org/hubfs/Whitepapers/a1Z1W0000054x6lUAA.pdf). Source for the systematic-strategy failure-mode taxonomy.
- [Combinatorial Purged CV — Towards AI](https://towardsai.net/p/l/the-combinatorial-purged-cross-validation-method). Confirms CPCV vs walk-forward tradeoffs.
- Cong, L. W., Li, X., Tang, K. (2022). *Crypto Wash Trading.* [NBER Working Paper](https://www.nber.org/system/files/working_papers/w30783/w30783.pdf). Empirical basis for the wash-trade claims and Tier-1 exchange ranking.
- [Blockchain Transparency Institute — Wash Trading on Binance](https://www.financemagnates.com/cryptocurrency/news/blockchain-transparency-institute-finds-wash-trading-on-binance/). Source for the "~90% clean" estimate on Tier-1 venues.
- [Crypto Bot Backtesting 2026 — Bitsgap](https://bitsgap.com/blog/crypto-bot-backtesting-in-2026-what-it-shows-and-what-it-cannot-predict). Source for the look-ahead and timestamp-misalignment patterns and the "profit factor > 3 = suspect" heuristic.
- [Backtesting AI Crypto Trading Strategies — Blockchain Council](https://www.blockchain-council.org/cryptocurrency/backtesting-ai-crypto-trading-strategies-avoiding-overfitting-lookahead-bias-data-leakage/). Confirms data leakage broader than look-ahead bias.
- [Sharpe Ratio for Crypto Traders — Walletfinder](https://www.walletfinder.ai/blog/sharpe-ratio-for-crypto-traders). Confirms 365-day convention for crypto Sharpe annualization.
- [Sharpe Ratio for Algorithmic Trading — QuantStart](https://www.quantstart.com/articles/Sharpe-Ratio-for-Algorithmic-Trading-Performance-Measurement/). Background on the `sqrt(periods)` annualization general formula.
- [Parquet Pitfalls — Puneet Agarwal / Medium](https://medium.com/@puneetagarwal1985/parquet-pitfalls-how-to-avoid-common-problems-in-data-lakes-016f26f38f20). Source for non-transactional parquet warning.
- [Apache Arrow / Parquet docs](https://arrow.apache.org/docs/python/parquet.html). Confirms parquet has no built-in transactionality.
- [Polars deadlock issue #19380](https://github.com/pola-rs/polars/issues/19380). Concrete evidence of parquet write-read race issues in modern stacks.
- [Pandas time series user guide](https://pandas.pydata.org/docs/user_guide/timeseries.html). Reference for `closed`, `label`, and resampling semantics.
- [Look-Ahead Bias — StratBase.ai](https://stratbase.ai/en/blog/look-ahead-bias-hidden-killer). Reinforces the "use closes from previous bar, not current bar" rule.
- [QuantPedia — Revisiting Trend-following and Mean-reversion in Bitcoin](https://quantpedia.com/revisiting-trend-following-and-mean-reversion-strategies-in-bitcoin/). Source for regime-specific performance of mean-reversion across BTC market eras.
- [Shen Crypto Research — Why Strategy-Hopping Fails](https://medium.com/@cryptoshenshen/why-traders-shouldnt-strategy-hopping-first-principle-thinking-402f9225a595). Confirms the 2022 bear-market failure mode for naive mean-reversion ("buying every dip in a violent downtrend").

Confidence-level notes:
- **HIGH** for all statistical pitfalls (Bailey & Lopez de Prado are the canonical references; the math is published and verifiable).
- **HIGH** for the 5-minute annualization arithmetic (`sqrt(365 × 24 × 12) = sqrt(105,120)` is a direct calculation, not a claim).
- **HIGH** for the project-specific vault-drift design (derived from PROJECT.md's constraints, not external research — the prescription matches the project's stated boundaries).
- **MEDIUM** for the exact wash-trade percentages on Binance/Coinbase/Kraken (different studies give somewhat different numbers; the *ranking* is robust, the *exact* percentages vary by methodology and date).
- **MEDIUM** for the conservative fee defaults (current Tier-1 fee tiers fluctuate; the 10 bps + 2 bps figure is a defensive choice, not a market quote).

---
*Pitfalls research for: crypto-quant research engine, Berakah Ring 1 (BTC/ETH spot mean-reversion validation)*
*Researched: 2026-06-04*
