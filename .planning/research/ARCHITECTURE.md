# Architecture Research

**Domain:** Systematic-trading research engine (Python, backend-only) fused with an Obsidian Markdown knowledge base
**Researched:** 2026-06-04
**Confidence:** HIGH
**Doubles as:** Berakah Ring 1 Backend Structure Document

---

## 0. Executive Posture

Berakah Ring 1 is a **backend-only research engine** whose single load-bearing guarantee is "out-of-sample edge measurement we can trust." The architecture is shaped by that goal and by the five engineering principles in the project's binding instructions:

1. **Type-driven architecture** — types ARE the architecture, not annotations on top of it.
2. **Global modular composition** — packages are subsystems behind strict interfaces, not folder buckets.
3. **AI-agent-friendly codebases** — predictable, repetitive, exhaustively typed; Claude must read a 200-line window and have a complete mental model.
4. **Declarative & functional design** — immutable by default, pure where possible, side effects at the edges.
5. **Hard constraints over loose logic** — wrong states unrepresentable. The `now_ts` look-ahead guarantee (HYP-02) is the canonical application.

Everything below is a consequence of those five rules applied to the Ring 1 problem.

The recommended architecture is a **pipeline of pure transformations between immutable artifacts on disk**, with a thin imperative shell at the CLI edge. The vault is treated as **structured input/output**, not as a database — Markdown notes with flat YAML frontmatter are the on-disk schema between the operator's narrative and the engine's executable contracts.

---

## 1. System Overview

### 1.1 Layered View

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          CLI / ENTRY POINTS                             │
│  berakah ingest │ berakah backtest │ berakah validate │ berakah report  │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │  (typed Config object — Pydantic Settings)
┌──────────────────────────▼──────────────────────────────────────────────┐
│                      ORCHESTRATION LAYER                                │
│              berakah.vault   (Markdown ↔ engine bridge)                 │
│   reads hypothesis notes, dispatches runs, writes reports back to vault │
└──────────┬─────────────────────────┬──────────────────────┬─────────────┘
           │                         │                      │
┌──────────▼─────────┐  ┌────────────▼──────────┐  ┌────────▼────────────┐
│  STRATEGY LAYER    │  │   BACKTEST LAYER      │  │  VALIDATION LAYER   │
│ berakah.strategy   │  │ berakah.backtest      │  │ berakah.validation  │
│  Protocol contract │  │ event-driven, pure    │  │ IS/OOS split,       │
│  one module / hyp. │  │ reducer over bars     │  │ metrics, overfit    │
│                    │  │ uses BarSnapshot[t]   │  │ regime stratifier   │
└──────────┬─────────┘  └────────────┬──────────┘  └────────┬────────────┘
           │                         │                      │
           └─────────────┬───────────┴──────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────────────┐
│                        DATA LAYER                                       │
│   berakah.data    ingest │ store │ load │ regime-label                  │
│   DuckDB views over Hive-partitioned Parquet                            │
└────────────────────────┬────────────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────────────┐
│                       TYPES LAYER                                       │
│   berakah.types    Bars, BarSnapshot[now_ts], Order, Fill, Trade,       │
│                    Position, Equity, Metrics, RegimeLabel, etc.         │
│                    (NewType, Protocol, Pydantic v2, Generic[NowTs])     │
└─────────────────────────────────────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────────────┐
│                       STORAGE                                           │
│  data/{exchange}/{pair}/{tf}/{YYYY-MM}.parquet   (canonical bar store)  │
│  artifacts/runs/{run_id}/{ledger,equity,metrics}.parquet|json           │
│  berakah_KB/  (sibling Obsidian vault — Markdown hypothesis + reports)  │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Component Responsibilities

| Component | Owns | Does Not Own | Talks To |
|-----------|------|--------------|----------|
| `berakah.types` | Every type used across module boundaries (Bars, BarSnapshot, Order, Fill, Trade, Position, Equity, Metrics, RegimeLabel, RunId, HypothesisId, all IDs as NewType, the Strategy Protocol). | Any runtime logic. No I/O, no computation beyond constructors/validators. | Imported by *every other module*. Imports nothing internal. |
| `berakah.data` | Ingesting exchange OHLCV, writing Parquet, regime labeling, exposing typed `Bars` views via DuckDB. | Strategy logic, backtest logic. Returns data; does not run anything. | `types`. Exchange APIs (Kraken / Coinbase / Binance) over HTTP. DuckDB. Local filesystem. |
| `berakah.strategy` | The `Strategy` Protocol and concrete strategy modules (e.g. `mr_zscore_v1.py`). Each strategy is a pure function `BarSnapshot[now_ts] → OrderIntent[]`. | Execution simulation, fees, position state, metrics. | `types` only. Strategies receive snapshots; they do not query data or vault. |
| `berakah.backtest` | The event-driven loop. Takes a `Strategy` + `Bars` + `BacktestConfig` and produces a `BacktestArtifact` (immutable). Handles sizing, fee model, fill simulation at next-bar-open. | Strategy logic, validation analysis, vault I/O. | `types`, `strategy` (uses Protocol), `data` (consumes `Bars`). |
| `berakah.validation` | IS/OOS split enforcement, metric computation (Sharpe, drawdown, win-rate, regime-stratified Sharpe), overfitting detector, `PROOF-01` gate evaluation. | Running the backtest. Generating the artifact. | `types`, consumes `BacktestArtifact` from disk. |
| `berakah.vault` | Reading hypothesis Markdown notes and their frontmatter; resolving `strategy_module` references; writing validation report Markdown back into the vault next to the hypothesis. | Computation. Just I/O + parsing + templating. | `types`, filesystem, `python-frontmatter`, Jinja2 (templating). |
| `berakah.config` | Typed Pydantic Settings model (`BerakahConfig`) used by every CLI entry point. Exchange lists, timeframe, OOS criteria, regime boundaries, vault path, data path. | Runtime mutation. Config is constructed once at process boundary, immutable thereafter. | `types`, environment variables (read once at startup). |
| `berakah.cli` | The Typer/Click app. Parses argv, constructs `BerakahConfig`, dispatches to the right subsystem function, exits. | Logic. The CLI is a thin shell. | Every other module. Imperative only at this edge. |

### 1.3 Dependency DAG (build order)

The acyclic graph below is the only legal order for module construction:

```
                       types
                         │
        ┌────────────────┼─────────────┐
        │                │             │
       data           strategy       config
        │                │             │
        └───────┬────────┘             │
                │                      │
            backtest                   │
                │                      │
            validation                 │
                │                      │
                └────────────┬─────────┘
                             │
                           vault
                             │
                            cli
```

**Build order:** `types → (data, strategy, config) in parallel → backtest → validation → vault → cli`.

No reverse edges. No cycles. Strategies do not import data; they receive snapshots. Validation does not import backtest internals; it reads artifacts.

---

## 2. The `now_ts` Look-Ahead Guarantee (HYP-02) — Concrete Sketch

This is the architecture's single most important pattern. The user requested "look-ahead-as-type-contract" be sketched concretely, not hand-waved. Here it is.

### 2.1 The pattern: phantom-typed snapshot, generic over `NowTs`

We use Python's `Generic` + `NewType` to bind a strategy's view of history to a specific timestamp. The strategy receives `BarSnapshot[NowTs]`, never `Bars`. The snapshot is the *only* legal interface for strategies to see market history, and it cannot expose any bar with `close_ts > now_ts`.

```python
# berakah/types/time.py
from typing import NewType
import pandas as pd

Timestamp = NewType("Timestamp", pd.Timestamp)        # UTC, tz-aware, no naive ever
BarCloseTs = NewType("BarCloseTs", Timestamp)         # bar.close_ts
NowTs = NewType("NowTs", Timestamp)                   # the "current moment" in a backtest

# berakah/types/bars.py
from dataclasses import dataclass
from typing import Generic, TypeVar
import pandas as pd

T_Now = TypeVar("T_Now", bound=Timestamp)

@dataclass(frozen=True, slots=True)
class BarSnapshot(Generic[T_Now]):
    """
    A read-only view of bars whose close_ts <= now_ts.

    Constructed ONLY by berakah.backtest.engine. Strategies receive it; they cannot
    construct it themselves (constructor is module-private by convention + lint rule).
    """
    _frame: pd.DataFrame   # private; columns: open_ts, close_ts, o, h, l, c, v
    now_ts: T_Now          # phantom-typed timestamp

    def last_n(self, n: int) -> pd.DataFrame:
        """Return the n most recent bars where close_ts <= now_ts."""
        return self._frame.tail(n)

    def window(self, lookback_bars: int) -> pd.DataFrame:
        return self._frame.tail(lookback_bars)

    def latest_close(self) -> float:
        return float(self._frame["c"].iloc[-1])

    # NOTE: there is NO method that takes a future ts as argument.
    # NOTE: there is NO method that returns the underlying _frame.
```

### 2.2 The Strategy Protocol — bound to the snapshot type

```python
# berakah/types/strategy.py
from typing import Protocol
from berakah.types.bars import BarSnapshot, NowTs
from berakah.types.orders import OrderIntent

class Strategy(Protocol):
    """
    A strategy is a pure function from snapshot -> intents.

    It MUST NOT:
      - import berakah.data
      - read files
      - hold mutable state across calls (use the params dataclass instead)
      - accept anything other than BarSnapshot[NowTs]

    The type signature of `on_bar` is the contract that makes look-ahead unrepresentable.
    """
    name: str
    params: object  # a frozen dataclass owned by the strategy module

    def on_bar(self, snap: BarSnapshot[NowTs]) -> tuple[OrderIntent, ...]:
        ...
```

### 2.3 Why this enforces the invariant

The strategy's signature is `on_bar(snap: BarSnapshot[NowTs]) -> tuple[OrderIntent, ...]`. There is **no parameter** that gives the strategy access to:

- a raw DataFrame of all history
- the future timestamp range
- the DuckDB connection
- the vault
- the next bar

The engine (the *only* construction site for `BarSnapshot`) filters the underlying frame to `close_ts <= now_ts` once before constructing the snapshot. The strategy cannot reach past the snapshot because its only argument is the snapshot. **Look-ahead bias requires the strategy to do something the type signature forbids.**

This is Principle 5 — Hard Constraints Over Loose Logic — applied surgically. We do not check at runtime "did the strategy peek?". We make the peek impossible to write.

### 2.4 Static enforcement

The repository ships with:

- `mypy --strict` on `berakah/strategy/**` with `--disallow-any-explicit`. A strategy that tries to call `snap._frame` triggers a private-access warning; a strategy that imports `berakah.data` triggers a custom `import-linter` contract violation.
- An `import-linter` contract (`importlinter.cfg`) declaring `berakah.strategy` *forbidden* from importing `berakah.data`, `berakah.vault`, `berakah.backtest`. Enforced in CI.
- A lightweight `ruff` rule disallowing `pd.DataFrame` as a parameter in any function under `berakah/strategy/`.

These are the lint-level guards Principle 5 calls for: invariants compiled in, not policed in review.

---

## 3. Data Flow (with explicit direction)

### 3.1 Ingest flow

```
   Exchange REST API (Kraken/Coinbase/Binance via ccxt)
              │
              ▼  (async fetch, paged)
   berakah.data.ingest.fetch_ohlcv()  -> list[BarDict]
              │
              ▼  (validate, dedupe, sort, tz-normalize to UTC)
   berakah.data.ingest.canonicalize() -> pd.DataFrame[Bars schema]
              │
              ▼  (Hive-partition write)
   data/{exchange}/{pair}/{timeframe}/{YYYY-MM}.parquet
              │
              ▼  (one-time, idempotent)
   berakah.data.regime.label()        -> writes regime column inline
```

### 3.2 Query flow (used by backtest)

```
   data/.../*.parquet
        │
        ▼  (DuckDB scan with predicate pushdown on close_ts)
   berakah.data.load.bars_for(pair, tf, start, end) -> Bars  (immutable view)
        │
        ▼  (passed to backtest)
   berakah.backtest.engine.run(strategy, bars, cfg) -> BacktestArtifact
```

### 3.3 Hypothesis run flow (end-to-end)

```
   berakah_KB/hypotheses/HYP-001-btc-zscore-mr.md         (operator writes this)
        │
        ▼  vault.read_hypothesis(HYP-001)
   HypothesisNote { id, strategy_module="berakah.strategy.mr_zscore_v1",
                    status, created, last_run, body_md }
        │
        ▼  importlib.import_module(note.strategy_module)
   Strategy instance (mr_zscore_v1.STRATEGY)
        │
        ▼  data.load.bars_for(...)
   Bars
        │
        ▼  backtest.engine.run(strategy, bars, cfg)
   BacktestArtifact (written to artifacts/runs/{run_id}/)
        │
        ▼  validation.report.build(artifact, cfg)
   ValidationReport (Sharpe IS/OOS, regime-stratified, overfit-flag, PROOF-01 verdict)
        │
        ▼  vault.write_report(HYP-001, report, run_ts)
   berakah_KB/reports/HYP-001/{run_ts}.md   + backlink injected into HYP-001 note
```

The flow is **strictly one-directional per run**. Vault → engine → vault. There is no in-engine state that survives between runs; the artifact on disk is the only memory.

### 3.4 What flows where (table)

| From | To | Carries | Format |
|------|----|---------|--------|
| Exchange API | `data.ingest` | OHLCV rows | JSON via ccxt |
| `data.ingest` | filesystem | Canonical bars | Hive-partitioned Parquet |
| filesystem | `data.load` (DuckDB) | Filtered bars | DuckDB view → `Bars` |
| `data.load` | `backtest.engine` | `Bars` | In-memory frame, immutable |
| `backtest.engine` | strategy.on_bar | `BarSnapshot[now_ts]` | Phantom-typed view |
| strategy.on_bar | `backtest.engine` | `tuple[OrderIntent, ...]` | Immutable tuple |
| `backtest.engine` | filesystem | `BacktestArtifact` | Parquet (ledger, equity) + JSON (summary) |
| filesystem | `validation.report` | `BacktestArtifact` | Read-only |
| `validation.report` | `vault.write` | `ValidationReport` | Pydantic model |
| `vault.write` | filesystem | Markdown report | `.md` with YAML frontmatter |
| `vault.read` | orchestrator | `HypothesisNote` | Pydantic model from `.md` |

---

## 4. Backtest Engine Design (event-driven, pure reducer)

### 4.1 The loop, as a reducer

The backtest is structured as a **pure reducer** stepping immutable state. Stating it as pseudocode (this becomes the literal implementation):

```python
# berakah/backtest/engine.py
def run(strategy: Strategy, bars: Bars, cfg: BacktestConfig) -> BacktestArtifact:
    state: EngineState = EngineState.initial(cfg)
    events: list[EngineEvent] = []

    for i, bar in enumerate(bars.iter_chronological()):
        # 1. Build snapshot for the strategy (close_ts <= bar.close_ts)
        snap = BarSnapshot._build(bars.view_up_to(bar.close_ts), now_ts=bar.close_ts)

        # 2. Pure: ask the strategy for intents
        intents = strategy.on_bar(snap)

        # 3. Pure: simulate fills at NEXT bar's open (one-bar execution delay)
        next_bar = bars.peek_next(i)  # may be None at the last bar
        fills, state = simulate_fills(state, intents, next_bar, cfg.fees)

        # 4. Pure: update positions and equity using next_bar.close as MTM
        state = mark_to_market(state, next_bar)

        # 5. Append an event record (immutable)
        events.append(EngineEvent(bar=bar, intents=intents, fills=fills, state=state))

    return BacktestArtifact.from_events(events, cfg)
```

### 4.2 Why this satisfies the principles

- **Pure**: every helper (`simulate_fills`, `mark_to_market`, `BarSnapshot._build`) is a pure function of `(state, inputs) -> new_state`. No globals.
- **Immutable**: `EngineState` is a frozen dataclass; every transition returns a new instance.
- **Deterministic**: no clocks, no randomness without injected seed, no I/O during the loop.
- **No look-ahead**: `simulate_fills` consumes `next_bar` but `bar.close_ts` already passed; the strategy's intent was generated *without* seeing `next_bar`. Execution at next-bar-open is the realistic, leakage-free fill model.
- **Reproducible**: run the same `(strategy, bars, cfg)` and you get the exact same `BacktestArtifact`. This is a CI assertion.

### 4.3 What the engine intentionally does NOT do

- It does not load data. The caller passes `Bars`.
- It does not write to the vault. The caller writes the artifact and the report.
- It does not decide IS/OOS splits. `validation` does. The engine runs the whole window passed to it.
- It does not parallelize over strategies. One run = one process = one artifact. The CLI may spawn multiple runs; that's CLI concern, not engine.

### 4.4 The fee model

A single function injected via `BacktestConfig.fees`:

```python
@dataclass(frozen=True)
class FeeModel:
    maker_bps: float
    taker_bps: float
    slippage_bps: float
    def apply(self, fill_price: float, side: Side, qty: float) -> tuple[float, float]:
        """Returns (effective_price, fee_paid). Pure."""
```

Default for Ring 1: taker fees on every fill, plus a flat 2bps slippage. Conservative — the goal is to make sure an edge survives realistic friction, not to optimize the fee model.

---

## 5. Vault Read/Write Contract

The vault is treated as **a typed I/O surface**, not a database. The schema is the Markdown file shape plus its YAML frontmatter.

### 5.1 Vault layout (inside `berakah_KB/`)

```
berakah_KB/
├── doczero.md                        # seed braindump (already exists)
├── hypotheses/
│   ├── HYP-001-btc-zscore-mr.md
│   ├── HYP-002-eth-bb-fade.md
│   └── ...
├── reports/
│   ├── HYP-001/
│   │   ├── 2026-06-04T1430.md        # one report per run
│   │   └── 2026-06-11T0900.md
│   └── HYP-002/
│       └── ...
├── postmortems/                      # operator-authored, engine never writes
├── papers/                           # ingested references
├── transcripts/                      # raw input material
└── .obsidian/                        # vault config — engine never touches
```

### 5.2 Hypothesis note shape (operator writes these)

`berakah_KB/hypotheses/HYP-001-btc-zscore-mr.md`:

```markdown
---
id: HYP-001
slug: btc-zscore-mr
title: BTC z-score mean reversion on 1h bars
strategy_module: berakah.strategy.mr_zscore_v1
status: drafted          # drafted | backtested | validated | invalidated
created: 2026-06-04
last_run: null           # ISO timestamp, written by engine
last_report: null        # path relative to vault root, written by engine
tags: [mean-reversion, btc, ring-1]
---

# BTC z-score mean reversion (1h)

## Hypothesis
After 1h close moves > 2σ from the 48-bar rolling mean, price reverts toward
the mean within the next 6–12 bars. The edge is the overshoot left by stop-hunt
liquidations on Tier-1 spot venues.

## Expected edge mechanism
[narrative...]

## Parameters in scope
- lookback: 48
- entry_z: 2.0
- exit_z: 0.25
- max_hold_bars: 12

## References
- [[papers/Avellaneda-2010-StatArb]]
- [[transcripts/2025-09-meeting-mean-reversion]]

## Reports
<!-- engine appends backlinks here on each run -->
```

**Frontmatter rules** (these are the contract):

- Flat YAML only — Obsidian Properties do not support nesting. Verified.
- `id` matches the filename prefix; `slug` matches the filename suffix.
- `strategy_module` is a fully-qualified importable Python path. The engine refuses to run if `importlib.import_module(strategy_module)` fails or if the imported module lacks a `STRATEGY: Strategy` symbol.
- `status` is one of four enum values. Engine transitions it: `drafted → backtested` after first run; operator promotes to `validated` or `invalidated` based on the report.
- `last_run` and `last_report` are engine-managed. Operator should not edit them.

### 5.3 Report note shape (engine writes these)

`berakah_KB/reports/HYP-001/2026-06-04T1430.md`:

```markdown
---
hypothesis_id: HYP-001
run_id: r_2026-06-04T1430_a3f9
run_ts: 2026-06-04T14:30:00Z
strategy_module: berakah.strategy.mr_zscore_v1
strategy_params_hash: 7f2c9e
data_window: 2020-01-01..2026-05-31
is_oos_split: 2024-01-01
proof_01_pass: false
overfit_flag: false
sharpe_is: 1.42
sharpe_oos: 0.81
sharpe_oos_3m_rolling_min: 0.34
max_drawdown_oos: -0.12
win_rate_oos: 0.54
regime_sharpe_bull_2020_21: 1.12
regime_sharpe_bear_2022: 0.42
regime_sharpe_recovery_2023: 0.98
regime_sharpe_etf_era_2024_plus: 0.58
artifact_path: artifacts/runs/r_2026-06-04T1430_a3f9/
---

# Run report — HYP-001 — 2026-06-04 14:30 UTC

## PROOF-01 verdict
FAIL — OOS rolling-3m Sharpe minimum is 0.34, below the 1.0 bar.

## Summary
[engine-generated narrative from the metrics above]

## Equity curve
![[../../../artifacts/runs/r_2026-06-04T1430_a3f9/equity.png]]

## Regime-stratified results
| Regime | Trades | Sharpe | MaxDD | Win rate |
|--------|--------|--------|-------|----------|
| Bull 2020–21 | 412 | 1.12 | -0.08 | 0.56 |
| ... | ... | ... | ... | ... |

## Trade ledger
See `artifact_path/ledger.parquet`.
```

The report is written via a Jinja2 template (`berakah/vault/templates/report.md.j2`). The frontmatter fields are flat scalars only — this is what makes them queryable from Obsidian's Properties view and DataView plugin without surprises.

### 5.4 The `vault` module's surface (the only legal vault touchpoints)

```python
# berakah/vault/api.py — the ENTIRE public surface
def read_hypothesis(vault_root: Path, hyp_id: HypothesisId) -> HypothesisNote: ...
def list_hypotheses(vault_root: Path) -> tuple[HypothesisNote, ...]: ...
def write_report(vault_root: Path, report: ValidationReport) -> Path: ...
def append_report_backlink(vault_root: Path, hyp_id: HypothesisId, report_path: Path) -> None: ...
def update_hypothesis_run_metadata(vault_root: Path, hyp_id: HypothesisId,
                                   run_ts: Timestamp, report_path: Path) -> None: ...
```

No other module touches `berakah_KB/`. Enforced by an `import-linter` contract: `berakah.{data,strategy,backtest,validation,types,config,cli}` may not import `pathlib` operations targeting paths under `vault_root`. (Implemented as a custom checker on the `vault.api` surface.)

---

## 6. Project Tree Layout

The vault lives **as a sibling directory inside the repo root**, not nested under `berakah/`, not external. Rationale: the vault is the operator's input/output surface and is the project's research record — it must be version-controlled in the same git repo (it already is per `git status`), but it is not Python code and must not pollute the Python import root.

```
berakah/                              # repo root (this is git root)
│
├── pyproject.toml                    # single source for project + tool config
├── README.md
├── .python-version                   # pinned 3.12.x
├── uv.lock                           # uv-managed lockfile (recommended over pip)
├── ruff.toml                         # lint config (or in pyproject)
├── mypy.ini                          # strict typing config
├── importlinter.cfg                  # module-boundary contracts
│
├── berakah/                          # the Python package
│   ├── __init__.py
│   ├── py.typed                      # PEP 561 marker — we ship types
│   │
│   ├── types/                        # Layer 0 — depends on nothing
│   │   ├── __init__.py               # re-exports the public type surface
│   │   ├── time.py                   # Timestamp, BarCloseTs, NowTs
│   │   ├── ids.py                    # NewType IDs: RunId, HypothesisId, OrderId
│   │   ├── bars.py                   # Bars, BarSnapshot[T_Now]
│   │   ├── orders.py                 # OrderIntent, Order, Fill, Side enum
│   │   ├── positions.py              # Position, Equity, EngineState
│   │   ├── metrics.py                # MetricSet, RegimeStratifiedMetrics
│   │   ├── strategy.py               # Strategy Protocol
│   │   ├── regime.py                 # RegimeLabel enum (4 named regimes)
│   │   └── artifacts.py              # BacktestArtifact, ValidationReport
│   │
│   ├── config.py                     # Pydantic Settings — BerakahConfig
│   │
│   ├── data/                         # Layer 1
│   │   ├── __init__.py
│   │   ├── ingest.py                 # ccxt-based fetchers, canonicalization
│   │   ├── store.py                  # Parquet write, Hive partitioning
│   │   ├── load.py                   # DuckDB queries -> Bars
│   │   └── regime.py                 # Regime labeling (4 named regimes)
│   │
│   ├── strategy/                     # Layer 1 (parallel with data)
│   │   ├── __init__.py
│   │   ├── _base.py                  # Strategy helpers (frozen dataclass utils)
│   │   ├── mr_zscore_v1.py           # first concrete strategy
│   │   └── ...                       # one module per hypothesis
│   │
│   ├── backtest/                     # Layer 2
│   │   ├── __init__.py
│   │   ├── engine.py                 # run() — the loop
│   │   ├── fees.py                   # FeeModel
│   │   ├── sizing.py                 # vol-target sizing
│   │   ├── fills.py                  # next-bar-open fill simulation
│   │   └── artifact.py               # BacktestArtifact builders + parquet writers
│   │
│   ├── validation/                   # Layer 3
│   │   ├── __init__.py
│   │   ├── split.py                  # IS/OOS split enforcement
│   │   ├── metrics.py                # Sharpe, drawdown, win-rate calculators
│   │   ├── regime.py                 # regime-stratified breakdowns
│   │   ├── overfit.py                # IS-vs-OOS divergence detector
│   │   ├── proof.py                  # PROOF-01 gate evaluation
│   │   └── report.py                 # builds ValidationReport from artifact
│   │
│   ├── vault/                        # Layer 4
│   │   ├── __init__.py
│   │   ├── api.py                    # the 5 public functions (see §5.4)
│   │   ├── _read.py                  # frontmatter parsing
│   │   ├── _write.py                 # Jinja2 templating
│   │   └── templates/
│   │       ├── report.md.j2
│   │       └── hypothesis_skeleton.md.j2
│   │
│   └── cli/                          # Layer 5 — thin shell
│       ├── __init__.py
│       ├── app.py                    # Typer app, subcommands wired here
│       ├── ingest.py                 # `berakah ingest ...`
│       ├── backtest.py               # `berakah backtest HYP-XXX`
│       ├── validate.py               # `berakah validate HYP-XXX --oos-from ...`
│       └── report.py                 # `berakah report HYP-XXX --regime-stratify`
│
├── tests/
│   ├── unit/
│   │   ├── types/                    # type-level tests (mypy stub assertions)
│   │   ├── data/
│   │   ├── strategy/
│   │   ├── backtest/
│   │   ├── validation/
│   │   └── vault/
│   ├── integration/
│   │   ├── test_end_to_end.py        # ingest -> backtest -> validate -> vault
│   │   └── test_no_lookahead.py      # property test: strategies cannot peek
│   ├── property/
│   │   └── test_engine_purity.py     # same inputs -> same outputs (hypothesis)
│   └── fixtures/
│       └── tiny_bars.parquet         # 200 bars, used everywhere
│
├── data/                             # canonical bar store (gitignored)
│   ├── .gitkeep
│   └── kraken/BTC-USDT/5m/2026-06.parquet
│
├── artifacts/                        # backtest output store (gitignored)
│   ├── .gitkeep
│   └── runs/r_2026-06-04T1430_a3f9/
│       ├── ledger.parquet
│       ├── equity.parquet
│       ├── summary.json
│       └── equity.png
│
├── berakah_KB/                       # the Obsidian vault (sibling, NOT under berakah/)
│   ├── .obsidian/                    # vault config (already exists)
│   ├── doczero.md                    # already exists
│   ├── hypotheses/                   # operator-authored .md files
│   ├── reports/                      # engine-written .md files
│   ├── postmortems/
│   ├── papers/
│   └── transcripts/
│
└── .planning/                        # GSD planning artifacts (already exists)
    ├── PROJECT.md
    └── research/
        ├── STACK.md
        ├── FEATURES.md
        ├── ARCHITECTURE.md           # this file
        └── PITFALLS.md
```

### 6.1 Layout rationale

- **`berakah_KB/` is a sibling of `berakah/`**, not nested. The vault is operator-facing and toolable by Obsidian directly; nesting it under the Python package would mean import-system surprises and make Obsidian's vault root awkward. Both already exist as siblings in the repo — keep it that way.
- **`data/` and `artifacts/` are gitignored** but tracked with `.gitkeep`. They are deterministic outputs of code + raw data; never commit them. Re-runnable from `ingest` + `backtest`.
- **`berakah/types/` is a directory, not a single module.** One submodule per type family. This is the most-imported part of the codebase; granularity reduces import blast radius and helps Claude target the right file.
- **`berakah/strategy/` is one file per hypothesis.** A strategy module's filename is its identity. Hypothesis notes link to the module by importable path, which is just the filename without `.py`.
- **`berakah/cli/` is the only place imperative composition is allowed.** Every other module exports pure functions.
- **`tests/` mirrors `berakah/` 1:1.** Predictability for AI agents — Principle 3.

---

## 7. Configuration

Single Pydantic v2 Settings model, constructed once at the CLI boundary, immutable thereafter, threaded through every entry point explicitly.

```python
# berakah/config.py
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class FeeConfig(BaseSettings):
    maker_bps: float = 1.0
    taker_bps: float = 5.0
    slippage_bps: float = 2.0

class BacktestConfig(BaseSettings):
    initial_equity_usd: float = 10_000.0
    vol_target_annualized: float = 0.10
    max_position_fraction: float = 0.5
    fees: FeeConfig = Field(default_factory=FeeConfig)

class ValidationConfig(BaseSettings):
    oos_split_date: str = "2024-01-01"
    overfit_sharpe_divergence_threshold: float = 0.5
    proof_01_rolling_window_months: int = 3
    proof_01_min_oos_sharpe: float = 1.0
    proof_01_min_regime_sharpe: float = 0.0

class RegimeConfig(BaseSettings):
    bull_2020_21: tuple[str, str] = ("2020-03-13", "2021-11-10")
    bear_2022:    tuple[str, str] = ("2021-11-11", "2022-12-31")
    recovery_2023:tuple[str, str] = ("2023-01-01", "2023-12-31")
    etf_era_2024_plus: tuple[str, str] = ("2024-01-01", "2099-12-31")

class BerakahConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BERAKAH_",
        env_nested_delimiter="__",
        frozen=True,
        extra="forbid",
    )
    project_root: Path = Field(default_factory=lambda: Path.cwd())
    data_root: Path = Field(default_factory=lambda: Path.cwd() / "data")
    artifacts_root: Path = Field(default_factory=lambda: Path.cwd() / "artifacts")
    vault_root: Path = Field(default_factory=lambda: Path.cwd() / "berakah_KB")

    exchanges: tuple[str, ...] = ("kraken", "coinbase", "binance")
    pairs: tuple[str, ...] = ("BTC/USDT", "ETH/USDT")
    timeframe: str = "5m"

    backtest: BacktestConfig = Field(default_factory=BacktestConfig)
    validation: ValidationConfig = Field(default_factory=ValidationConfig)
    regimes: RegimeConfig = Field(default_factory=RegimeConfig)
```

**Rules:**

- `frozen=True` — config cannot be mutated after construction.
- `extra="forbid"` — unknown fields raise. No silent typo absorption.
- Env vars are read once at startup via `BERAKAH_*` prefix (e.g., `BERAKAH_BACKTEST__INITIAL_EQUITY_USD=50000`).
- Strategies do **not** read config. They receive their own `params` frozen dataclass at construction.
- No `os.getenv` calls anywhere outside `config.py`.

---

## 8. CLI Surface (entry points)

Typer-based, four subcommands matching the user's spec.

```bash
# Ingest historical OHLCV
berakah ingest --exchange kraken --pair BTC/USDT --from 2020-01-01 [--to YYYY-MM-DD]

# Run a backtest end-to-end for one hypothesis
berakah backtest HYP-001 [--from YYYY-MM-DD] [--to YYYY-MM-DD]

# Run validation (assumes a recent backtest artifact exists for HYP)
berakah validate HYP-001 --oos-from 2024-01-01

# Build a report (regime-stratified) and write it back to the vault
berakah report HYP-001 [--regime-stratify] [--open-in-obsidian]
```

Each subcommand is a one-screen function in `berakah/cli/{name}.py` that:

1. Constructs `BerakahConfig` (defaults + env + flags).
2. Calls the relevant pure subsystem function.
3. Exits with code 0 on success, non-zero with a typed error message on failure.

There is also one convenience composite:

```bash
berakah run HYP-001        # ingest-if-missing → backtest → validate → report
```

This is the operator's normal loop. It's the only command that crosses module boundaries; it lives in `cli/run.py` and is a thin glue function.

---

## 9. Architectural Patterns

### Pattern 1: Phantom-typed snapshot (look-ahead barrier)

**What:** Generic-parameterized snapshot view (`BarSnapshot[NowTs]`) bound to a specific timestamp, given to strategies as their *only* market-history input.
**When to use:** Any time you need to forbid an entire class of bug at the type level.
**Trade-offs:**
- (+) Look-ahead bias literally cannot be written.
- (+) AI agents reading a strategy file see the constraint in the signature.
- (–) Adds one layer of indirection over a raw DataFrame.
- (–) Generic parameterization is mostly documentary at runtime in Python — the static check is what matters.

### Pattern 2: Pure-reducer event loop

**What:** Backtest implemented as `for bar in bars: state = step(state, bar, strategy.on_bar(snap))`. Every step is pure.
**When to use:** Whenever determinism + reproducibility matter more than raw speed. (For Ring 1 they do.)
**Trade-offs:**
- (+) Deterministic, testable, parallelizable across strategies.
- (+) Property tests (run twice, assert equal) cost almost nothing.
- (–) Slower than a vectorized backtest. Acceptable at 5m bars over a few years.

### Pattern 3: Vault-as-typed-I/O

**What:** Obsidian Markdown notes with flat YAML frontmatter are the schema between the operator and the engine. `vault.api` is the only crossing point.
**When to use:** When the human is part of the loop and wants to author hypotheses in natural language linked to executable code.
**Trade-offs:**
- (+) The operator works in Obsidian; the engine works in code; they meet at a parseable format.
- (+) The vault is the research record, durable independent of the engine.
- (–) Markdown isn't a database; structured queries across many notes use DataView or are done by enumerating files. Fine at MVP scale.

### Pattern 4: Artifact-as-handoff

**What:** Modules communicate across boundaries by writing immutable artifacts to disk (`BacktestArtifact` as parquet+json), not by passing live objects.
**When to use:** When you want each stage independently re-runnable, debuggable, and inspectable.
**Trade-offs:**
- (+) Validation can re-run on yesterday's artifact without re-doing the backtest.
- (+) Artifacts are gold: the contract is "if this parquet exists, validation can produce a report."
- (–) Two layers of serialization. Mitigated by Pydantic + parquet.

### Pattern 5: Module-boundary contracts via import-linter

**What:** `importlinter.cfg` declares which packages may import which. Strategies cannot import `data` or `vault`. CI enforces it.
**When to use:** Always, in any modular system, but especially with AI-generated code that drifts toward shortcuts.
**Trade-offs:**
- (+) Architecture violations become compile-time errors.
- (+) Claude reading the contracts file gets a one-screen summary of the architecture.
- (–) Requires the operator to update the contract when adding a new module. Cheap.

---

## 10. Scaling Considerations

Berakah Ring 1 is single-operator, single-laptop, BTC/ETH only, 5m+ bars. Scaling is not the architecture's first concern. But here is the honest assessment:

| Scale | What changes | Adjustment |
|-------|--------------|------------|
| Today (1 operator, ~100 hypotheses) | Nothing | Current design is correct. |
| Ring 1 mature (~1000 hypotheses, batch sweeps) | Backtest loop becomes the bottleneck | Run `multiprocessing` pool over hypotheses at the CLI level; each process owns one artifact. The pure-reducer design parallelizes trivially. No engine changes needed. |
| Ring 2 (paper trading layer added) | Real-time component appears | Add a new package `berakah.execution` with its own contracts. Backtest remains as-is. |
| Ring 4 (portfolio of strategies, correlations) | Cross-strategy state | Add `berakah.portfolio` consuming N `BacktestArtifact` files. Still no changes to `backtest`, `strategy`, or `data`. |

**First bottleneck**: backtest loop CPU on long histories. Mitigation: per-strategy multiprocessing at the CLI. No structural change needed.

**Second bottleneck**: DuckDB query plans on years of 5m bars. Mitigation: the Hive partition layout (`{exchange}/{pair}/{tf}/{YYYY-MM}.parquet`) gives partition pruning for free. Verified at 2026 Q2 in the DuckDB docs: 100 MB – 10 GB per file is the sweet spot.

**What does NOT scale and should not be made to scale in Ring 1**: a global event bus, a daemon engine, a database for hypotheses. We deliberately do not build those. Ring 2+ may revisit.

---

## 11. Anti-Patterns (specific to this domain and these principles)

### Anti-Pattern 1: "Just pass the full DataFrame to the strategy"

**What people do:** `def on_bar(self, all_bars: pd.DataFrame, current_idx: int)`.
**Why it's wrong:** The strategy can index `all_bars.iloc[current_idx + 5]` and you have look-ahead bias. The convention "don't do that" is loose logic. Principle 5 forbids it.
**Do this instead:** Pass `BarSnapshot[NowTs]`. The snapshot literally does not contain future rows. No discipline required; the type makes it impossible.

### Anti-Pattern 2: Mutable global "Portfolio" object

**What people do:** A `Portfolio` singleton that strategies and the engine both mutate.
**Why it's wrong:** Path-dependent bugs, unreproducible runs, parallelism becomes impossible, and the strategy now has state it shouldn't.
**Do this instead:** `EngineState` is a frozen dataclass owned by the engine. Strategies are pure: signal in, intents out. Position management lives in the engine alone.

### Anti-Pattern 3: Reading the vault from the backtest engine

**What people do:** Engine peeks at the hypothesis note to "self-configure."
**Why it's wrong:** The engine should be runnable without a vault at all — that's how we test it. Coupling them makes the engine harder to reason about and to test.
**Do this instead:** The vault is read at the CLI / orchestration layer, which then calls the engine with explicit arguments. `import-linter` blocks the bad import.

### Anti-Pattern 4: Storing config in JSON/YAML files the engine reads ad-hoc

**What people do:** `config.json` here, `params.yml` there, each module reads its own.
**Why it's wrong:** No single source of truth, no type checking, env-var bingo. Configuration becomes a maintenance pit.
**Do this instead:** One `BerakahConfig` (Pydantic Settings), constructed at the CLI edge, passed explicitly to subsystem functions. Frozen.

### Anti-Pattern 5: Picking the OOS split after running the backtest

**What people do:** Run the backtest on all data, then "find the split that looks good."
**Why it's wrong:** It IS the overfitting. Multiple-comparison and look-ahead in disguise.
**Do this instead:** `ValidationConfig.oos_split_date` is fixed in config before the run. The engine reads the whole window; the validator splits by the pre-committed date. If you change the split, you must record why in the vault as a post-mortem note.

### Anti-Pattern 6: Letting strategies hold mutable state across `on_bar` calls

**What people do:** `self._last_signal = sig` inside the strategy, used in the next bar.
**Why it's wrong:** Strategies become non-replayable; debugging requires reconstructing trajectories; parallel evaluations diverge.
**Do this instead:** Anything a strategy needs to remember is computed from the snapshot. If the strategy needs `last_signal`, it derives it from a window of past intents — but that means it should be looking at past bars, not internal state. Snapshots are the memory.

### Anti-Pattern 7: Writing reports straight from the backtest engine

**What people do:** Engine writes the Markdown report inline at the end of `run()`.
**Why it's wrong:** Couples computation to presentation; re-running the report requires re-running the backtest.
**Do this instead:** Engine writes a `BacktestArtifact` (parquet + json). Validation reads the artifact, writes a `ValidationReport`. Vault writes the Markdown. Three pure functions, three artifacts, three boundaries.

---

## 12. Integration Points

### External services

| Service | Integration | Notes |
|---------|-------------|-------|
| Kraken / Coinbase / Binance | `ccxt` library, HTTP REST, async paged fetch in `data.ingest` | Tier-1 only per constraint. Rate limits respected. No websocket — Ring 1 is historical only. |
| DuckDB | In-process; reads parquet files from `data/` | No server, no client/server split. Zero ops. |
| Obsidian | Filesystem only — engine reads/writes `.md` files; Obsidian watches the folder | No plugin required. Operator can optionally use DataView for vault queries. |
| Filesystem (local) | All persistence | Single laptop scale per constraint. |

### Internal boundaries (the only legal cross-module calls)

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `cli → config` | Function call returning `BerakahConfig` | One-shot at process start. |
| `cli → data.{ingest,load}` | Function call passing `BerakahConfig` | Imperative composition only at this edge. |
| `cli → vault.api` | Function call | Reading hypothesis, writing report. |
| `vault → strategy module` | `importlib.import_module(note.strategy_module)` | The dynamic-import surface; gated by frontmatter validation. |
| `cli → backtest.engine.run` | Pure function call | Returns `BacktestArtifact`. |
| `backtest → strategy.on_bar` | Pure function call with `BarSnapshot[NowTs]` | The hot path; the look-ahead barrier. |
| `cli → validation.report.build` | Pure function call reading `BacktestArtifact` from disk | Returns `ValidationReport`. |
| `cli → vault.api.write_report` | Function call | The only write into `berakah_KB/`. |

Every boundary above is enforced by `import-linter`. Any line of code that crosses a boundary not listed here fails CI.

---

## 13. How the Five Engineering Principles Show Up

| Principle | Where it appears in this architecture |
|-----------|---------------------------------------|
| **1. Type-driven architecture** | `berakah.types/` is a sibling of every domain module. `BarSnapshot[NowTs]`, `Strategy` Protocol, `EngineState` frozen dataclass, Pydantic config. Types are written before logic. |
| **2. Global modular composition** | The dependency DAG (§1.3). `import-linter` contracts. Artifact handoff between stages so each stage is swappable. |
| **3. AI-agent-friendly codebases** | Predictable layout (tests mirror src 1:1). One file per hypothesis. Five-function vault API. Pyramidal type re-exports. The architecture file you're reading is itself part of this — Claude reads it and has a complete model. |
| **4. Declarative & functional design** | Pure reducer backtest loop. Frozen `EngineState`. No globals. Strategies are pure functions of snapshots. Side effects live at `cli/`, `data.ingest`, `vault._write`. |
| **5. Hard constraints over loose logic** | `BarSnapshot[NowTs]` makes look-ahead unrepresentable. `frozen=True` everywhere. `extra="forbid"` on config. `import-linter` makes boundary violations CI failures. `ruff` rule against `pd.DataFrame` params in strategies. |

---

## 14. Sources

- DuckDB: [Reading and Writing Parquet Files](https://duckdb.org/docs/current/data/parquet/overview) — partition pruning and file format guidance (HIGH).
- DuckDB: [Parquet Tips](https://duckdb.org/docs/current/data/parquet/tips) — 100 MB – 10 GB per file, 100k–1M row groups (HIGH).
- DuckDB: [File Formats Performance](https://duckdb.org/docs/current/guides/performance/file_formats) (HIGH).
- Bhagya Rana, "5 DuckDB Partitioning Moves for Faster Time-Series Reads" — Hive partitioning patterns for time-series (MEDIUM, secondary).
- VertoxQuant, "[Event-Driven Backtester in Python](https://www.vertoxquant.com/p/event-driven-backtester-in-python)" — confirms the strategy-as-pure-signal-generator pattern (MEDIUM).
- QuantStart, "[Event-Driven Backtesting with Python — Part I](https://www.quantstart.com/articles/Event-Driven-Backtesting-with-Python-Part-I/)" — the drip-feed / no-lookahead rationale (MEDIUM).
- Python.financial 2026, "[The Python Backtesting Landscape (2026)](https://python.financial/)" — NautilusTrader's central-runtime + message-bus pattern; confirms an architectural family that validates the pure-reducer approach (MEDIUM).
- Pydantic: [Custom Data Types](https://docs.pydantic.dev/2.3/usage/types/custom/) and [Types overview](https://docs.pydantic.dev/latest/concepts/types/) — supports the typed config + custom types approach (HIGH).
- Python typing discussion, "[Generic NewType?](https://discuss.python.org/t/generic-newtype/61234)" — confirms `TypeVar`-bound generic dataclasses as the idiom for phantom-typed views in Python 3.12+ (MEDIUM).
- Obsidian forum, "[Current status for parsing/working with YAML frontmatter](https://forum.obsidian.md/t/current-status-for-parsing-working-with-yaml-frontmatter/70290)" — confirms flat YAML constraint for Obsidian Properties (MEDIUM).
- Obsidian help, [YAML front matter](https://help.obsidian.md/Advanced+topics/YAML+front+matter) — schema reference (HIGH).
- Operator-supplied `PROJECT.md` and `doczero.md` — Ring 1 scope, principles, the concentric monopoly stack framing (HIGH, authoritative).

---

*Architecture research for: Berakah Ring 1 (research engine, backend-only)*
*Researched: 2026-06-04*
*Doubles as: Berakah Ring 1 Backend Structure Document*
