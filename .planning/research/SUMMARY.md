# Project Research Summary

**Project:** Berakah (Ring 1)
**Domain:** Systematic crypto trading research engine (BTC/ETH spot mean-reversion, vault-integrated)
**Researched:** 2026-06-04
**Confidence:** HIGH

## Executive Summary

Berakah Ring 1 is a **backend-only research engine** whose single load-bearing guarantee is "out-of-sample edge measurement we can trust." All four research strands — stack, features, architecture, pitfalls — converged independently on the same conclusion: the project's core value (trustworthy OOS edge) is best served by building a **small, opinionated, type-driven event loop** rather than adopting an off-the-shelf backtester. The recommended approach is a Python 3.12 / `uv` / `polars` / `duckdb` / `ccxt` stack with a **custom event-driven engine (~800 LOC)** in which look-ahead bias is *unrepresentable at compile time* via a phantom-typed `BarSnapshot[NowTs]` pattern (per STACK.md, ARCHITECTURE.md §2). This is Engineering Principle 5 ("hard constraints over loose logic") applied surgically: rather than policing leakage in code review, leakage is made impossible to *write*.

The features research (FEATURES.md) catalogues **17 table stakes + 12 differentiators + 18 anti-features**, all REQ-ID-mapped to PROJECT.md's `DATA-01 → PROOF-01` chain. Off-the-shelf backtesters (vectorbt, backtrader, zipline, NautilusTrader) optimize for *strategy volume* or *execution realism*; Berakah optimizes for **validation trustworthiness for one strategy family**, and that optimization target dictates the four differentiators that justify a custom build: type-level look-ahead prevention, engine-enforced IS/OOS, deterministic `run_id` hash, and the Obsidian-vault round-trip (per FEATURES.md competitor table).

The pitfalls research (PITFALLS.md) identifies **30 failure modes**, with three load-bearing classes that must be defended on day 1: (1) **look-ahead bias** in all forms — defended by the `BarSnapshot[NowTs]` type contract; (2) **backtest overfitting** at the meta-level — defended by Deflated Sharpe Ratio + PBO + CPCV + a never-touched final-validation slice; (3) **vault/code drift** — defended by frontmatter binding (`strategy_module` + `strategy_commit` SHA + `data_manifest` + `frozen_ts`) plus a pre-commit guard. The single most consequential domain-specific pitfall is the **crypto Sharpe annualization constant** — `sqrt(365 × 24 × 12) = sqrt(105,120) ≈ 324.2`, not the equity-market `sqrt(252)`. Inheriting the wrong constant from a copy-pasted tutorial silently distorts every Sharpe in the project by ~2.1× and invalidates the `PROOF-01` bar.

## Key Findings

### Recommended Stack

A 2026-consensus Python data-quant stack with a deliberate departure on the backtest engine. Opinionated against dead-but-familiar libraries (`pandas` as primary, `pyfolio`, `empyrical`, `quantstats`, `vectorbt`, `backtrader`) in favor of younger but better-maintained alternatives. Every component must support the look-ahead type contract and the deterministic single-laptop scale.

**Core technologies** (per STACK.md):
- **Python 3.12 + `uv`** — language baseline and unified env/dep manager. `uv sync --frozen` enforces lockfile compliance in CI (Principle 5).
- **`polars` 1.41 + `pyarrow` 24 + `duckdb` 1.5** — analytical substrate. Polars dataframe layer (Rust core, ~10× pandas on time-series ops, real `Schema` type), DuckDB SQL engine over Hive-partitioned Parquet, pyarrow underneath both. Zero-copy interop.
- **`ccxt` 4.5** — only Python library with maintained unified adapters for Binance, Coinbase, *and* Kraken; rejects the 3×-per-exchange alternative.
- **`pydantic` v2.13 + `phantom-types` 3.0 + `typing.NewType` + `typing.Protocol`** — four-layer encoding of the look-ahead invariant. Pydantic at I/O boundaries; phantom-types + NewType for the compile-time `BarSnapshot[NowTs]` contract.
- **Custom event-driven backtest engine (~800 LOC)** — NOT vectorbt/backtrader/zipline. Vectorized engines admit look-ahead defense is procedural ("remember to `.shift(1)`") and cannot encode the invariant at the type level. Custom engine cost ≤ adoption cost at Ring 1 scope.
- **`pyright --strict` + `ruff` + `pytest` + `hypothesis`** — compile-time shield, linter/formatter, test runner, adversarial property-based testing for the temporal invariant. Pyright preferred over mypy (98% vs 58% spec conformance; 2–5× faster).
- **`scipy.stats` + ~80 LOC custom polars metrics** — Sharpe/Sortino/drawdown/DSR/PBO/CPCV. `pyfolio`/`empyrical` are dead; `quantstats` is pandas-only and assumes daily Series.
- **`structlog` 25 + `obsidiantools` + `python-frontmatter`** — queryable JSON event records; read/write of Obsidian Markdown with flat YAML frontmatter.

### Expected Features

**Must have (table stakes, all P1, all map to PROJECT.md REQ-IDs):**

Full set TS-1 through TS-17 from FEATURES.md collectively realize `DATA-01, DATA-02, HYP-01, HYP-02, BT-01, BT-02, VAL-01, VAL-02, REPORT-01`. The non-negotiable subset:
- Tier-1-only OHLCV at ≥5-min (TS-1, DATA-01); Hive-partitioned Parquet (TS-2); data integrity checks (TS-3); 4 macro-frozen regime labels (TS-4, DATA-02).
- Strategy Protocol with `on_bar(snap: BarSnapshot[NowTs]) -> tuple[OrderIntent, ...]` signature (TS-5, HYP-01); event-driven loop with explicit `now_ts` (TS-6, HYP-02, BT-01); **look-ahead prevention as type-level contract (TS-7 = D-8, HYP-02) — the load-bearing safety asset.**
- Vol-targeted position sizing (TS-8, BT-01); taker-fee model with conservative defaults (TS-9, BT-01); engine-enforced IS/OOS (TS-10, VAL-01); standard metric set (TS-11); trade-by-trade ledger (TS-12, BT-02); equity curve (TS-13); **regime-stratified report as first-class engine output (TS-14, PROOF-01).**
- Markdown validation report written to vault (TS-15, REPORT-01); Typer CLI (TS-16); `structlog` JSON logging (TS-17).

**Should have (Berakah-specific differentiators that justify the build):**
- **D-1 Vault round-trip** — hypothesis note → strategy module → backtest → report linked back. No off-the-shelf backtester does this.
- **D-2 Hypothesis-as-code-contract**; **D-3 Hypothesis lifecycle** (for kill-trigger accounting); **D-4 Overfitting detector (VAL-02)**; **D-6 Reproducibility hash** (`run_id = hash(data_snap, code_sha, config_sha)`); **D-9 Deflated Sharpe Ratio**; **D-11 Data snapshot pinning**; **D-12 Configuration-as-code.**

**Defer (P2):** D-7 parameter sweep + heatmaps; D-10 trade-ledger Markdown excerpt — add after PROOF-01 closes or if first hand-tuned strategy fails the bar.

**Defer (v2+ / Ring 2+; locked anti-features for Ring 1):** AF-1 through AF-18 — no live data, no execution layer, no LLM in signal path, no HMM live classifier, no multi-asset, no sub-5-min, no paid feeds, no momentum, no margin/perp, no non-Tier-1, no funding-rate/on-chain, no auto-generation, no web UI, no multi-engine parity.

### Architecture Approach

A **pipeline of pure transformations between immutable artifacts on disk**, with a thin imperative shell at the CLI edge. The vault is treated as *typed I/O*, not a database: Markdown notes with flat YAML frontmatter are the schema. Direct mechanical consequence of the five engineering principles applied to Ring 1.

**Major components** (per ARCHITECTURE.md §1.2, §1.3):
1. **`berakah.types`** — Layer 0. Owns every cross-boundary type (`Bars`, `BarSnapshot[NowTs]`, `OrderIntent`, `Fill`, `Trade`, `Position`, `Equity`, `MetricSet`, `RegimeLabel`, all IDs as `NewType`, `Strategy` Protocol). Imports nothing internal.
2. **`berakah.data`** — Layer 1. Ingestion (ccxt), canonicalization, Hive-Parquet write, DuckDB-view loading, regime labeling.
3. **`berakah.strategy`** — Layer 1. `Strategy` Protocol + one module per hypothesis. Pure functions of `BarSnapshot[NowTs]`. `import-linter` forbids imports of `data`, `vault`, `backtest`.
4. **`berakah.backtest`** — Layer 2. Event-driven pure reducer. Returns `BacktestArtifact` (parquet + JSON). Owns sizing, fees, fill simulation at next-bar-open.
5. **`berakah.validation`** — Layer 3. IS/OOS split enforcement, metrics, overfit detector, `PROOF-01` gate. Reads artifact from disk.
6. **`berakah.vault`** — Layer 4. Five-function public API; the only legal touchpoint into `berakah_KB/`.
7. **`berakah.config` + `berakah.cli`** — Pydantic Settings + Typer. Imperative composition only here.

**Build order (only legal acyclic graph):** `types → (data, strategy, config) in parallel → backtest → validation → vault → cli`. Reverse edges are CI-blocked by `importlinter.cfg`.

**Five patterns** (per ARCHITECTURE.md §9): phantom-typed snapshot, pure-reducer event loop, vault-as-typed-I/O, artifact-as-handoff, module-boundary contracts via `import-linter`.

### Critical Pitfalls

Top three load-bearing pitfalls that must be defended from day 1.

1. **Look-ahead bias** (Pitfalls 1, 2, 3 per PITFALLS.md) — `rolling`/`ewm`/`expanding` on un-shifted series, resampling that includes current incomplete bar, train/test boundary leakage. **Defense:** `BarSnapshot[NowTs]` phantom-typed contract (no constructor admits future bars), enforced by `pyright --strict` and `import-linter`, with `hypothesis` adversarial property tests for impure leakage; purge + embargo in validation; macro-defined frozen regime labels (no HMM-derived labels in Ring 1).

2. **Backtest overfitting at the meta-level** (Pitfalls 4, 5, 6) — researcher's multiple-testing via iterative OOS reruns, parameter-search ratchet, walk-forward windows too small/few. **Defense:** four statistical techniques in the validation engine — (a) **DSR** (Bailey & López de Prado 2014) against pre-registered trial count, threshold ≥ 0.95 for `PROOF-01`; (b) **PBO** via CSCV, threshold ≤ 0.5; (c) **CPCV** instead of single walk-forward; (d) **never-touched final-validation slice** the operator can only touch once per strategy.

3. **Vault/code drift** (Pitfalls 20, 21) — hypothesis note describes v1 but linked module evolved to v3; report frontmatter SHA doesn't appear in `git log`. **Defense:** hypothesis frontmatter binds `strategy_module` + `strategy_commit` (git SHA) + `data_manifest` + `data_commit` + `frozen_ts`; reproducibility hash in every REPORT-01; pre-commit guard verifies pinned SHA reachable from HEAD; single-commit boundary for code + vault + parquet; vault `_index.md` audit log.

Three additional crypto-specific pitfalls warrant day-1 attention: **Sharpe annualization `sqrt(105,120)` not `sqrt(252)`** (Pitfall 11) as a single project constant; **conservative fee floor 10 bps + 2 bps slippage** (Pitfall 10); **parquet write atomicity** (Pitfall 16) via per-run unique output paths + temp-then-rename.

## Implications for Roadmap

The four researchers independently converged on a **6-phase decomposition** consistent with the ARCHITECTURE.md DAG, the PROJECT.md REQ-ID chain, and the PITFALLS.md prevention mapping.

### Phase 1: Typed Foundation + Look-Ahead Contract

**Rationale:** Every downstream phase inherits the type contract. `BarSnapshot[NowTs]` must exist before any strategy or backtest. `types` is the only Layer 0 module per ARCHITECTURE.md §1.3. Pitfalls 1, 2, 15, 16, 17, 20, 23, 24, 28 require Phase 1 mitigation; FEATURES TS-5, TS-7, D-8 must land before BT-01 is trusted.

**Delivers:** `berakah.types/` package; `berakah.config` (Pydantic Settings, `frozen=True`, `extra="forbid"`); `importlinter.cfg`; full `pyright --strict` + `ruff` + `pytest` + `hypothesis` toolchain; `uv.lock` committed; project skeleton (`berakah/`, `berakah_KB/` as sibling, `tests/` mirroring `berakah/` 1:1).

**Addresses:** TS-5, TS-7, D-8, D-12, HYP-02.

**Avoids:** Pitfalls 1, 2, 23 (infra-before-edge scope discipline), 24 (UTC), 28 (`frozen_ts` vs `created_ts`).

### Phase 2: Data Layer + Regime Labels

**Rationale:** Types frozen → ingestion + storage + regime labeling can land. `data` is Layer 1 per the DAG. FEATURES dependency graph: `DATA-01 → DATA-02 → BT-02`. Pitfalls 7, 8, 9 require data-layer mitigation.

**Delivers:** `berakah.data/` package (`ingest.py`, `store.py`, `load.py`, `regime.py`); Tier-1 OHLCV via ccxt for BTC/ETH at 5-min; Hive-partitioned Parquet (`data/{exchange}/{pair}/{tf}/{YYYY-MM}.parquet`); DuckDB views returning `Bars`; canonical pair manifest (Binance:BTCUSDT, Coinbase:BTC-USD, Kraken:XBTUSD); gap detection + UTC + cross-exchange sanity; 4 macro-frozen regime labels (Bull 2020–21, Bear 2022, Recovery 2023, ETF era 2024–) in TOML.

**Uses:** `ccxt` 4.5, `polars` 1.41, `pyarrow` 24, `duckdb` 1.5, `tenacity`, `structlog`.

**Avoids:** Pitfalls 7 (regime overfit), 8 (survivorship / pair drift), 9 (crypto data quality), 16 (parquet writes).

### Phase 3: Strategy + Backtest Engine

**Rationale:** Types + data in place → vertical-slice-through-`PROOF-01` discipline (Pitfall 23). Get smallest possible end-to-end loop working before generalizing.

**Delivers:** `berakah.strategy/` (toy `mr_zscore_v1.py`); `berakah.backtest/` (`engine.py` pure reducer, `fees.py` 10 bps + 2 bps defaults, `sizing.py` vol-targeting, `fills.py` next-bar-open execution, `artifact.py` writing `BacktestArtifact`); deterministic `run_id`; CI test for byte-identical reproduction.

**Uses:** `polars`, `scipy.stats` primitives, `structlog`, `decimal.Decimal` for cash accounting.

**Avoids:** Pitfalls 10 (conservative fee), 13 (vol-targeting), 15 (determinism), 16 (per-run unique paths), 17 (DatetimeIndex), 18 (Decimal + PnL-invariant test), 25 (raw vs vol-targeted ledger columns).

### Phase 4: Validation Discipline

**Rationale:** Engine produces artifacts; validation gates `PROOF-01`. Load-bearing discipline phase. Pitfalls 3, 4, 5, 6, 11, 12, 13, 14, 19, 26, 27 require Phase 4 mitigation; the Sharpe annualization constant `sqrt(105,120)` lives here.

**Delivers:** `berakah.validation/` (`split.py` keyed off `frozen_ts`, `metrics.py` with crypto annualization, `regime.py`, `overfit.py`, `proof.py` multi-gate `PROOF-01` evaluator, `report.py`); CPCV capped at ~100–200 paths; purge + embargo on by default; bootstrap CI on every Sharpe; per-window N ≥ 30 gate; minimum 12 rolling-3m windows.

**`PROOF-01` multi-gate:** rolling-3m OOS Sharpe ≥ 1.0 AND non-negative per-regime Sharpe AND DSR ≥ 0.95 AND PBO ≤ 0.5 AND holds on never-touched final-validation slice.

**Uses:** `scipy.stats` for DSR / Welch's t / bootstrap; custom polars; pinned `ANNUALIZATION_FACTOR_5MIN_CRYPTO = sqrt(105_120) ≈ 324.2`.

**Avoids:** Pitfalls 3 (purge+embargo), 4 (DSR + PBO + final slice + trial budget), 5 (DSR for grid), 6 (CPCV + N≥30 + 12-window minimum), 11 (single constant + round-trip test), 12 (CI + concentration test), 13 (rolling Sharpe + Sortino), 14 (`frozen_ts` pinning), 19 (synthetic known-truth fixtures), 26 (locked final slice), 27 (CI on every Sharpe).

### Phase 5: Vault Round-Trip + Report Layer

**Rationale:** Validation produces `ValidationReport`; vault renders Markdown and writes back to `berakah_KB/`, linked to originating hypothesis. Karpathy-style differentiator closes the loop. `vault` is Layer 4 per the DAG. Pitfalls 20, 21, 22 require Phase 5 mitigation.

**Delivers:** `berakah.vault/` (5-function API per ARCHITECTURE.md §5.4); Jinja2 templates; hypothesis frontmatter Pydantic schema binding `strategy_module` + `strategy_commit` + `data_manifest` + `data_commit` + `frozen_ts` + `trial_budget`; report frontmatter with reproducibility hash + PROOF-01 verdict; backlink injection; vault `_index.md` audit log; pre-commit guard; single-commit boundary.

**Uses:** `python-frontmatter` (write), `obsidiantools` (read), `Jinja2`, `gitpython` or `subprocess` for SHA verification.

**Avoids:** Pitfalls 20 (frontmatter binding + reproducibility hash + pre-commit guard), 21 (single-commit + `_index.md`), 22 (trial budget + cooling-off + kill-window countdown).

### Phase 6: CLI Wiring + First `PROOF-01` Attempt

**Rationale:** All subsystems standing → CLI composes them. First real mean-reversion strategy authored as a vault note and run end-to-end. Per the 6-week MVP target, Phases 1–5 in weeks 1–4 leaves weeks 5–6 for strategy iteration.

**Delivers:** `berakah.cli/` (Typer app + 4 subcommands + `run.py` composite); first real `berakah_KB/hypotheses/HYP-001-btc-zscore-mr.md`; first end-to-end run; first `PROOF-01` attempt against the full multi-gate.

**Uses:** `typer`, `rich`.

### Phase Ordering Rationale

- **Types-first is forced by the DAG** (ARCHITECTURE.md §1.3). All four researchers arrived at this order independently.
- **Data and strategy stub parallel after Phase 1.** DAG shows them as siblings at Layer 1.
- **Validation split from backtest by design.** Engine produces `BacktestArtifact`; validation reads it from disk → "artifact-as-handoff" pattern makes Phase 4 independently re-runnable.
- **Vault round-trip is Phase 5, not Phase 1.** Per Pitfall 23, vertical slice through `data → backtest → validation` must work end-to-end before operator-facing vault layer is built.
- **First `PROOF-01` attempt is Phase 6.** Attempting before DSR/PBO/CPCV/final-slice are built guarantees a false-positive edge claim that has to be retracted.

### Research Flags

Phases likely needing `/gsd:plan-phase` deep research:
- **Phase 4 (Validation):** CPCV path-count default for single-laptop budget (50 / 100 / 200 / 500); final-validation slice shape (contiguous last-3-months vs non-contiguous regime samples).
- **Phase 5 (Vault):** Vault directory conventions and `_index.md` structure; `obsidiantools` Python 3.12 compatibility smoke test.
- **Phase 6 (CLI + first PROOF-01):** Quick literature sweep on z-score mean-reversion variants tested on BTC/ETH 5-min bars.

Phases with standard patterns (skip `/gsd:research-phase`):
- **Phase 1:** Patterns fully sketched in STACK.md + ARCHITECTURE.md.
- **Phase 2:** ccxt + Hive-Parquet + DuckDB views are well-documented in STACK.md.
- **Phase 3:** Event-driven pure-reducer pattern is literal pseudocode in ARCHITECTURE.md §4.1.

## Stack at a Glance (drop-in for ROADMAP.md context)

| Module (ARCHITECTURE.md) | Phase | Primary Stack (STACK.md) | Load-Bearing Pattern |
|---|---|---|---|
| `berakah.types` | 1 | `phantom-types` 3.0, `typing.NewType`, `typing.Protocol`, `pydantic` 2.13, `pyright --strict` | `BarSnapshot[NowTs]` phantom-typed snapshot (HYP-02) |
| `berakah.config` | 1 | `pydantic-settings`, `frozen=True`, `extra="forbid"` | Single immutable config object at CLI edge |
| `berakah.data` | 2 | `ccxt` 4.5, `polars` 1.41, `duckdb` 1.5, `pyarrow` 24, `tenacity`, `structlog` | Hive-partitioned Parquet + DuckDB views; macro-frozen regime labels |
| `berakah.strategy` | 3 | `polars`; no `pandas`/`pandas-ta`/`ta-lib` in hot path; `import-linter` forbids `data`/`vault`/`backtest` | One module per hypothesis; pure `on_bar(snap) -> intents` |
| `berakah.backtest` | 3 | `polars`, `decimal.Decimal` for cash, `structlog` | Pure reducer over immutable `EngineState`; next-bar-open fill; deterministic `run_id` |
| `berakah.validation` | 4 | `scipy.stats` + ~80 LOC custom polars; **NOT** `pyfolio`/`empyrical`/`quantstats` | DSR + PBO + CPCV + final-validation slice; `sqrt(105_120)` annualization |
| `berakah.vault` | 5 | `python-frontmatter`, `obsidiantools`, `Jinja2` | 5-function API; frontmatter binding (`strategy_module`+`strategy_commit`+`data_manifest`+`frozen_ts`); pre-commit guard |
| `berakah.cli` | 6 | `typer`, `rich` | Thin imperative shell; one subcommand per subsystem + `berakah run HYP-XXX` |
| Dev toolchain | all | `uv` 0.11, `ruff` 0.15, `pyright` 1.1.410, `pytest` 9.0, `hypothesis` 6.155, `pre-commit` | `uv sync --frozen` in CI; `pyright --strict` on `berakah/strategy/**`; `import-linter` contracts |

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Versions verified on PyPI June 2026 (per STACK.md). 2026-consensus picks. Custom-engine call is MEDIUM-HIGH (sound reasoning; operator should sanity-check). |
| Features | HIGH | 17 + 12 + 18 all REQ-ID-mapped. Competitor analysis verified against 4 named OSS backtesters. |
| Architecture | HIGH | DAG forced by principles + REQ-IDs. `BarSnapshot[NowTs]` sketched concretely (ARCHITECTURE.md §2). Module boundaries `import-linter`-enforceable. |
| Pitfalls | HIGH | Statistical pitfalls draw on Bailey/López de Prado canonical references. Crypto-specific pitfalls verified against NBER 2022 and direct arithmetic. Vault-drift defense derived from PROJECT.md. |

**Overall confidence:** HIGH.

### Gaps to Address (do not block roadmap)

- **CPCV path-count default for single-laptop budget** — decide during Phase 4 planning; cap at ~200 per Bailey et al.
- **Final-validation slice shape** (contiguous "last 3 months" vs non-contiguous regime samples) — decide Phase 4; contiguous default unless regime distribution argues otherwise.
- **Exact vault directory conventions** — hypotheses in `berakah_KB/hypotheses/`, reports in `berakah_KB/reports/{hyp_id}/` per ARCHITECTURE.md §5.1; `_index.md` structure flagged Phase 5.
- **Regime label source** — confirmed macro-defined operator-provided dates (PROJECT.md + Pitfall 7); no algorithmic derivation. Operator should sanity-check the date boundaries in ARCHITECTURE.md §7's `RegimeConfig` defaults.
- **`obsidiantools` Python 3.12 compatibility** — yellow flag in STACK.md; Phase 1 smoke test; fallback `python-frontmatter` + `markdown-it-py`.
- **First strategy parameterization** — z-score lookback / entry threshold / exit threshold / hold-bar grid operator-defined per hypothesis note; FEATURES Q3 flags regime-granularity question; revisit after first `PROOF-01` attempt.

## Sources

### Primary (HIGH confidence)
- PyPI June 2026 version verifications for the 14 pinned libraries (per STACK.md Sources).
- Bailey, D. H., & López de Prado, M. (2014). *The Deflated Sharpe Ratio.* SSRN. DSR + multiple-testing canon.
- Bailey, Borwein, López de Prado, Zhu (2015). *The Probability of Backtest Overfitting.* PBO + CSCV source.
- López de Prado, M. (2018). *Advances in Financial Machine Learning.* Purged CV, embargo, CPCV.
- Cong, Li, Tang (2022). *Crypto Wash Trading.* NBER w30783.
- DuckDB official docs (Parquet partitioning, performance); Pydantic official docs; Obsidian YAML help; PEP 544 (Protocols).
- PROJECT.md and doczero.md (operator-supplied, authoritative): Ring 1 scope, principles, PROOF-01 bar, kill trigger, 4 regimes, constraints.

### Secondary (MEDIUM-HIGH)
- Python Backtesting Landscape 2026; IBKR Quant Vector-vs-Event comparison; NautilusTrader docs (validates pure-reducer architecture family).
- Python Package Managers 2026 (Scopir, Cuttlesoft); Polars vs Pandas 2026.
- Mypy vs Pyright vs ty 2026 conformance/speed.
- Walletfinder, QuantStart — confirms 365-day crypto Sharpe convention.
- Blockchain Transparency Institute — wash-trade quantification on Tier-1 venues.
- López de Prado reading notes (Reasonable Deviations); Towards AI CPCV tutorial; CRAN PBO vignette.
- Bitsgap, Blockchain Council, StratBase — confirms look-ahead and "use prev bar close" rule.
- QuantPedia — regime-specific mean-reversion BTC performance; confirms 2022 bear-market failure mode.

### Tertiary (LOW — flag for validation during implementation)
- Exact wash-trade percentages on Binance/Coinbase/Kraken (ranking robust, exact figures vary by study).
- Conservative fee defaults (10 bps + 2 bps) — defensive choice, not market quote.
- `obsidiantools` Python 3.12 compatibility — community-reported workable despite officially-pinned 3.9–3.11 metadata; confirm via Phase 1 smoke test.

---
*Research completed: 2026-06-04*
*Ready for roadmap: yes*
