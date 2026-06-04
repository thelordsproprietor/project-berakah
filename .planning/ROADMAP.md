# Roadmap: Berakah Ring 1

**Created:** 2026-06-04
**Granularity:** coarse (6 phases — bottom of range; further compression violates DAG + Pitfall 23)
**Total v1 requirements:** 28
**Coverage:** 28/28 mapped (100%)

## Core Value Reminder

The research engine must produce **trustworthy out-of-sample edge measurements** — no leakage, no overfitting, no look-ahead. If validation infrastructure is broken, nothing downstream matters.

## Closing Bar (PROOF-01)

Ring 1 closes when a mean-reversion strategy holds all of:
- OOS Sharpe ≥ 1.0 over a rolling 3-month window
- Regime-stratified Sharpe ≥ 0 across all 4 labeled regimes (Bull 2020–21, Bear 2022, Recovery 2023, ETF era 2024–)
- Deflated Sharpe Ratio ≥ 0.95 against pre-registered trial count
- Probability of Backtest Overfitting ≤ 0.5
- Holds on the never-touched final-validation slice

## Phase Ordering Constraint

The module DAG (per ARCHITECTURE.md §1.3) is the only legal acyclic build order:

```
types → (data, strategy, config) parallel → backtest → validation → vault → cli
```

Reverse edges are forbidden and CI-enforced by `import-linter`. Phase boundaries follow this DAG; collapsing them either breaks the type-contract-first rule (Phase 1) or merges "engine works" with "research succeeds" (Pitfall 23).

## Phases

- [ ] **Phase 1: Typed Foundation + Look-Ahead Contract** — Engineering scaffold, type system, config, lint contracts; `BarSnapshot[NowTs]` makes look-ahead unrepresentable
- [ ] **Phase 2: Data Layer + Regime Labels** — Tier-1 OHLCV ingested to Hive-Parquet; DuckDB views; canonical pair manifest; 4 macro-frozen regime labels
- [ ] **Phase 3: Strategy Contract + Backtest Engine** — `Strategy` Protocol + first toy strategy; pure-reducer event loop; vol-targeted sizing; conservative fees; deterministic `run_id`
- [ ] **Phase 4: Validation Discipline** — IS/OOS splits, DSR, PBO via CSCV, CPCV, locked final-validation slice, crypto Sharpe constant; `PROOF-01` multi-gate evaluator
- [ ] **Phase 5: Vault Round-Trip + Report Layer** — Hypothesis frontmatter binding, Markdown report generation, backlink injection, `_index.md` audit log, pre-commit guard
- [ ] **Phase 6: CLI Wiring + First PROOF-01 Attempt** — Typer subcommands compose the pipeline; first real hypothesis authored as vault note; first end-to-end PROOF-01 evaluation

## Phase Details

### Phase 1: Typed Foundation + Look-Ahead Contract
**Goal**: A typed Python scaffold where look-ahead bias is structurally unrepresentable, lint contracts forbid reverse-DAG imports, and the engineering principles are enforced at the compiler level before any logic exists.
**Depends on**: Nothing (first phase)
**Requirements**: HYP-02, CONFIG-01, CONFIG-02, CONFIG-03
**Success Criteria** (what must be TRUE):
  1. `uv sync --frozen` produces a deterministic environment; `pyright --strict` and `ruff` both pass clean on the empty `berakah/` package scaffold
  2. A test attempting to construct a `BarSnapshot[NowTs]` containing a bar whose `close_ts > now_ts` fails to type-check (pyright error) and fails at runtime (`Phantom.parse` predicate raises); a `hypothesis` adversarial test confirms no input can produce a leaky snapshot
  3. `import-linter` CI step rejects any commit that introduces a forbidden edge (e.g., `berakah.strategy` importing `berakah.data`, `berakah.vault`, or `berakah.backtest`); a deliberately-broken test commit demonstrates the block
  4. A single `BerakahConfig` (Pydantic Settings) loads with `frozen=True, extra="forbid"`; an attempt to set an unknown env var raises at startup, and an attempt to mutate any config field at runtime raises
  5. The repo skeleton (`berakah/types/`, `berakah/config.py`, `tests/` mirroring 1:1, `pyproject.toml`, `uv.lock`, `importlinter.cfg`, `pyrightconfig.json`, `ruff.toml`, `pre-commit` config) exists and CI runs all checks on every push
**Plans**: 3 plans in 2 waves (Plans 02 and 03 run parallel in Wave 2 after Plan 01)
  - [x] 01-01-PLAN.md - Toolchain + project skeleton + CI workflow (CONFIG-03)
  - [x] 01-02-PLAN.md - berakah/types/ + BarSnapshot[NowTs] phantom contract (HYP-02)
  - [x] 01-03-PLAN.md - BerakahConfig (frozen Pydantic Settings) + importlinter.cfg DAG contracts (CONFIG-01, CONFIG-02)
**UI hint**: no

### Phase 2: Data Layer + Regime Labels
**Goal**: Historical BTC/ETH OHLCV from all three Tier-1 venues is queryable as a typed `Bars` view with canonical pair naming, UTC normalization, gap detection, and macro-frozen regime labels — the substrate every backtest reads from.
**Depends on**: Phase 1 (types must exist; `BerakahConfig.data_root` resolved)
**Requirements**: DATA-01, DATA-02, DATA-03
**Success Criteria** (what must be TRUE):
  1. `berakah ingest --exchange kraken --pair BTC/USDT --from 2020-01-01` (invoked through the data API directly in Phase 2; the CLI wrapper lands Phase 6) writes Hive-partitioned Parquet at `data/{exchange}/{pair}/{tf}/{YYYY-MM}.parquet`; re-running the same command is idempotent
  2. A `bars_for(pair, tf, start, end)` query returns a typed `Bars` view via DuckDB; all timestamps are tz-aware UTC; canonical pair names resolve (`Binance:BTCUSDT`, `Coinbase:BTC-USD`, `Kraken:XBTUSD` all return the same `Bars` shape for "BTC")
  3. Gap detection produces an explicit `bar_present=False` row at every detected missing bar; a synthetic-gap integration test confirms the loader does not silently zero-fill
  4. Cross-exchange sanity check flags any minute where Binance and Coinbase BTC mid-prices disagree by > 1%; a synthetic-divergence test triggers the flag
  5. The four regime labels (Bull 2020-03-13 to 2021-11-10; Bear 2021-11-11 to 2022-12-31; Recovery 2023-01-01 to 2023-12-31; ETF era 2024-01-01 onward) are TOML-frozen, attached to every bar via the loader, and verifiable by re-reading the TOML — no algorithmic regime detection exists in the codebase
**Plans**: TBD
**UI hint**: no

### Phase 3: Strategy Contract + Backtest Engine
**Goal**: A single toy mean-reversion strategy runs end-to-end against the data layer through a pure-reducer event loop, producing a deterministic `BacktestArtifact` (parquet + JSON) with vol-targeted sizing, conservative fees, and a trade-by-trade ledger.
**Depends on**: Phase 1 (types + lint contracts), Phase 2 (data layer)
**Requirements**: HYP-01, BT-01, BT-02, BT-03
**Success Criteria** (what must be TRUE):
  1. A toy `berakah/strategy/mr_zscore_v1.py` exposes `STRATEGY: Strategy` conforming to the Protocol; calling it directly from Python with a `BarSnapshot[NowTs]` returns `tuple[OrderIntent, ...]` and import-linter confirms it imports nothing from `data`/`vault`/`backtest`
  2. `engine.run(strategy, bars, cfg)` produces a `BacktestArtifact` containing equity curve, trade ledger, regime-stratified Sharpe/drawdown/win-rate, written to `artifacts/runs/{run_id}/{ledger.parquet, equity.parquet, summary.json}`
  3. Vol-targeted position sizing (10% annualized vol target by default) caps individual position fractions; the trade ledger contains both raw-signal PnL and vol-targeted PnL columns; a 10 bps round-trip fee + 2 bps slippage is applied at every fill, fills execute at next-bar-open
  4. `run_id = hash(data_snapshot_sha, code_sha, config_sha)` is deterministic; a CI test runs the same `(strategy, bars, cfg)` twice and asserts byte-identical parquet outputs and identical `run_id`
  5. A PnL invariant test confirms `sum(per_trade_pnl) + sum(fees) = final_equity - initial_equity` to within `1e-6` using `decimal.Decimal` for cash accounting; a synthetic known-truth fixture (mean-reverting AR(1) process with analytically computable Sharpe) confirms the engine recovers the expected Sharpe
**Plans**: TBD
**UI hint**: no

### Phase 4: Validation Discipline
**Goal**: Backtest artifacts are evaluated by an engine that enforces IS/OOS splits, computes statistically defensible metrics (DSR, PBO, CPCV, bootstrap CI on every Sharpe) with the crypto-correct annualization constant, and locks a never-touched final-validation slice — the multi-gate PROOF-01 evaluator lives here.
**Depends on**: Phase 1 (types), Phase 3 (consumes `BacktestArtifact` from disk via artifact-as-handoff)
**Requirements**: VAL-01, VAL-02, VAL-03, VAL-04, VAL-05, VAL-06, VAL-07
**Success Criteria** (what must be TRUE):
  1. The IS/OOS split is computed from a hypothesis's `frozen_ts` (a frontmatter field, not a CLI flag); calling `validate` twice on the same hypothesis produces identical splits; an attempt to override the split post-hoc raises an `ImmutableSplitError`
  2. The annualization constant `ANNUALIZATION_FACTOR_5MIN_CRYPTO = sqrt(365 * 24 * 12) ≈ 324.2` lives in a single module; a synthetic-known-Sharpe round-trip test (Gaussian returns with mean = σ → analytical Sharpe = 1.0 after annualization) confirms the formula; every Sharpe in every output ships with a bootstrap 95% CI
  3. VAL-02 overfitting detector emits a hard refusal (not a warning) when `|IS_Sharpe - OOS_Sharpe| > threshold`; VAL-03 computes Deflated Sharpe Ratio (Bailey & López de Prado 2014) against the hypothesis's pre-registered trial count; VAL-04 computes PBO via CSCV; VAL-05 runs CPCV with purge + embargo capped at ≤200 paths
  4. The final-validation slice (last 3 months of available data by default) is locked at hypothesis `frozen_ts` creation; an attempt to access it twice for the same hypothesis raises `FinalSliceAlreadyConsumedError`; the lock is persisted on disk under `artifacts/locks/{hyp_id}.lock`
  5. The `PROOF-01` evaluator returns `PASS` if and only if all five gates hold (rolling-3m OOS Sharpe ≥ 1.0, per-regime Sharpe ≥ 0 across all 4 regimes, DSR ≥ 0.95, PBO ≤ 0.5, final-slice Sharpe ≥ 1.0); a synthetic mean-reverting fixture with known passing characteristics returns `PASS`; a synthetic noise fixture returns `FAIL` with the failing gate(s) named
**Plans**: TBD
**UI hint**: no

### Phase 5: Vault Round-Trip + Report Layer
**Goal**: A `ValidationReport` is rendered as a Markdown note written into `berakah_KB/reports/{HYP-ID}/{run_ts}.md` with frontmatter binding the run to its strategy commit + data manifest + frozen_ts, backlinked from the originating hypothesis note, audit-logged in `_index.md`, and refused on commit if the pinned SHA isn't reachable — closing the Karpathy-style vault loop.
**Depends on**: Phase 1 (types), Phase 4 (consumes `ValidationReport`)
**Requirements**: HYP-03, REPORT-01, REPORT-02, REPORT-03, REPORT-04
**Success Criteria** (what must be TRUE):
  1. The 5-function `berakah.vault.api` (read_hypothesis, list_hypotheses, write_report, append_report_backlink, update_hypothesis_run_metadata) is the only legal touchpoint into `berakah_KB/`; `import-linter` rejects any other module importing path operations targeting the vault root
  2. A hypothesis note's frontmatter Pydantic schema enforces `strategy_module`, `strategy_commit` (git SHA), `data_manifest`, `data_commit`, `frozen_ts`, `created_ts`, `trial_budget`, and `status` ∈ {drafted, backtested, validated, invalidated}; the engine refuses to run a hypothesis whose `strategy_module` cannot be imported or whose `strategy_commit` is not reachable from `HEAD`
  3. A report is written as Markdown with flat YAML frontmatter (Obsidian Properties-compatible) containing the reproducibility hash (`run_id`), all PROOF-01 gate verdicts, regime-stratified Sharpe table, fee-sensitivity table, trial count, DSR, PBO; the originating hypothesis note has the new report backlink appended under its `## Reports` section
  4. `berakah_KB/_index.md` records every run as an audit-log row `(hyp_id, strategy_commit, report_commit, run_ts, proof_01_verdict, remaining_kill_window_days)`; a single git commit captures (a) the report, (b) the artifact parquet under `artifacts/runs/{run_id}/`, (c) the updated `_index.md`, (d) the updated hypothesis frontmatter — no run produces a split commit
  5. A pre-commit guard refuses to commit a report file whose pinned `strategy_commit` SHA is not reachable from `HEAD`; a deliberately-broken test commit (point report at an orphan SHA) is rejected by the guard
**Plans**: TBD
**UI hint**: no

### Phase 6: CLI Wiring + First PROOF-01 Attempt
**Goal**: The operator's daily loop — `berakah run HYP-001` — composes ingest → backtest → validate → write-report end-to-end through a Typer CLI, executed against the first real mean-reversion hypothesis authored as a vault note, producing the project's first PROOF-01 verdict (pass or fail).
**Depends on**: Phases 1–5 (every subsystem must be standing; this phase only composes them)
**Requirements**: CLI-01, CLI-02, CLI-03, CLI-04, PROOF-01
**Success Criteria** (what must be TRUE):
  1. The four CLI subcommands work end-to-end: `berakah ingest --exchange <name> --pair <symbol> --from <date>` populates the data store; `berakah backtest <HYP-ID>` produces a `BacktestArtifact`; `berakah validate <HYP-ID>` produces a `ValidationReport`; `berakah run <HYP-ID>` chains all four
  2. `berakah_KB/hypotheses/HYP-001-btc-zscore-mr.md` exists as the first operator-authored hypothesis note, with valid frontmatter binding it to `berakah.strategy.mr_zscore_v1`, a pre-registered trial budget, a `frozen_ts`, and a narrative description of the edge mechanism
  3. `berakah run HYP-001` executes without error against the full historical BTC and ETH datasets from all three Tier-1 exchanges, writes a complete validation report into the vault, and updates `_index.md` with the run's outcome
  4. The report's frontmatter contains a non-null `proof_01_verdict` ∈ {PASS, FAIL}; if FAIL, every failing gate is explicitly named (e.g., `failed_gates: [regime_sharpe_bear_2022, deflated_sharpe]`); if PASS, all five PROOF-01 gates carried independent evidence in the report body
  5. CLI exit codes are predictable: 0 on success regardless of PROOF-01 verdict (a clean FAIL is a successful run); non-zero only for engine errors (data missing, type contract violation, frontmatter invalid); typed error messages name the offending pitfall (e.g., `ERR-LOOKAHEAD-01`, `ERR-VAULT-DRIFT-20`) per UX Pitfalls convention
**Plans**: TBD
**UI hint**: no

## Phase Dependencies

```
Phase 1 (Foundation)
    │
    ├─→ Phase 2 (Data) ──────┐
    │                         │
    └─→ Phase 3 (Strategy + Backtest) ←──┘
                │
                └─→ Phase 4 (Validation)
                            │
                            └─→ Phase 5 (Vault)
                                        │
                                        └─→ Phase 6 (CLI + PROOF-01)
```

- Phases 2 and 3 are technically parallelizable after Phase 1 (data is `data → backtest`; strategy is `strategy → backtest`), but the v1 requirements assign HYP-01 (operator-authored hypothesis note linking to a module) to Phase 3, which requires the toy module to actually run against real data. Phase 3 is gated on Phase 2 in practice.
- Phase 4 reads `BacktestArtifact` from disk (artifact-as-handoff pattern); it does not import `berakah.backtest`. This is the firewall that lets validation be re-run on yesterday's artifact without re-running the backtest.
- Phase 6 imports every other subsystem at the CLI edge; it is the only place imperative composition is permitted.

## Coverage Validation

All 28 v1 requirements mapped:

| Phase | Requirements | Count |
|-------|--------------|-------|
| 1 | HYP-02, CONFIG-01, CONFIG-02, CONFIG-03 | 4 |
| 2 | DATA-01, DATA-02, DATA-03 | 3 |
| 3 | HYP-01, BT-01, BT-02, BT-03 | 4 |
| 4 | VAL-01, VAL-02, VAL-03, VAL-04, VAL-05, VAL-06, VAL-07 | 7 |
| 5 | HYP-03, REPORT-01, REPORT-02, REPORT-03, REPORT-04 | 5 |
| 6 | CLI-01, CLI-02, CLI-03, CLI-04, PROOF-01 | 5 |
| **Total** | | **28 / 28** |

No orphaned requirements. No requirement assigned to multiple phases.

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Typed Foundation + Look-Ahead Contract | 0/3 | Not started | - |
| 2. Data Layer + Regime Labels | 0/0 | Not started | - |
| 3. Strategy Contract + Backtest Engine | 0/0 | Not started | - |
| 4. Validation Discipline | 0/0 | Not started | - |
| 5. Vault Round-Trip + Report Layer | 0/0 | Not started | - |
| 6. CLI Wiring + First PROOF-01 Attempt | 0/0 | Not started | - |

## Research Flags (carried from research/SUMMARY.md)

Phases likely needing `/gsd:plan-phase` deep research:
- **Phase 4**: CPCV path-count default for single-laptop budget (50 / 100 / 200); final-validation slice shape (contiguous last-3-months vs non-contiguous regime samples)
- **Phase 5**: Vault directory conventions and `_index.md` structure; `obsidiantools` Python 3.12 compatibility smoke test
- **Phase 6**: Quick literature sweep on z-score mean-reversion variants tested on BTC/ETH 5-min bars

Phases with standard patterns (skip phase-research):
- **Phase 1**: Patterns fully sketched in STACK.md + ARCHITECTURE.md
- **Phase 2**: ccxt + Hive-Parquet + DuckDB views well-documented in STACK.md
- **Phase 3**: Event-driven pure-reducer pattern is literal pseudocode in ARCHITECTURE.md §4.1

## Out-of-Scope Reminder (Ring 1)

No live data, no execution layer, no paper trading, no LLM in signal path, no HMM live classifier, no multi-asset beyond BTC/ETH, no sub-5-min bars, no paid feeds, no momentum, no margin/perp, no non-Tier-1 venues, no funding-rate/on-chain, no auto-generation, no web UI, no multi-engine parity. Frontend / UI work: **zero** in Ring 1.

---
*Roadmap created: 2026-06-04*
*Coverage: 28/28 v1 requirements mapped*
