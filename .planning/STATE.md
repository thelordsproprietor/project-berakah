# Project State: Berakah Ring 1

**Last updated:** 2026-06-04
**Mode:** yolo
**Granularity:** coarse

## Project Reference

**What this is:** AI-augmented systematic trading research engine fused with a Karpathy-style Obsidian vault. Ring 1 MVP is the backend-only Python research engine that ingests historical BTC/ETH OHLCV from Tier-1 exchanges, encodes mean-reversion hypotheses as type-contract-protected strategy modules, runs out-of-sample backtests with vol-targeted sizing, and writes validation reports back to the vault as Markdown.

**Core value:** The research engine must produce **trustworthy out-of-sample edge measurements** — no leakage, no overfitting, no look-ahead. If validation infrastructure is broken, nothing downstream matters. Every architectural choice serves this.

**Closing bar (PROOF-01):**
- OOS Sharpe ≥ 1.0 over a rolling 3-month window
- Regime-stratified Sharpe ≥ 0 across all 4 labeled regimes (Bull 2020–21, Bear 2022, Recovery 2023, ETF era 2024–)
- Deflated Sharpe Ratio ≥ 0.95 against pre-registered trial count
- Probability of Backtest Overfitting ≤ 0.5
- Holds on the never-touched final-validation slice

**Kill trigger:** 6 calendar months from project start with no strategy clearing PROOF-01.

## Current Position

**Phase:** None (planning phase complete; implementation not started)
**Plan:** None
**Status:** Roadmap drafted; awaiting `/gsd:plan-phase 1` to decompose Phase 1 into executable plans

**Progress:**
```
[0/6 phases complete]
░░░░░░░░░░░░░░░░░░░░ 0%
```

## Roadmap Snapshot

| # | Phase | Status | Requirements |
|---|-------|--------|--------------|
| 1 | Typed Foundation + Look-Ahead Contract | Not started | HYP-02, CONFIG-01/02/03 |
| 2 | Data Layer + Regime Labels | Not started | DATA-01/02/03 |
| 3 | Strategy Contract + Backtest Engine | Not started | HYP-01, BT-01/02/03 |
| 4 | Validation Discipline | Not started | VAL-01/02/03/04/05/06/07 |
| 5 | Vault Round-Trip + Report Layer | Not started | HYP-03, REPORT-01/02/03/04 |
| 6 | CLI Wiring + First PROOF-01 Attempt | Not started | CLI-01/02/03/04, PROOF-01 |

## Performance Metrics

(Populated by `/gsd:transition` as phases complete.)

- **Phases completed:** 0 / 6
- **Plans completed:** 0
- **Requirements validated:** 0 / 28
- **Kill-window days remaining:** TBD (clock starts when engine ships in Phase 6)

## Accumulated Context

### Decisions

(Carried from PROJECT.md; logged here for in-flight reference.)

- **MVP scope = Ring 1 only.** Backend research engine, no execution, no paper trading, no live capital. Validation infrastructure is the load-bearing asset.
- **First edge family = BTC/ETH spot mean-reversion.** Most resilient to crypto's dominant manipulation tactic (stop-hunt overshoots *help* mean-reversion strategies).
- **Type-driven look-ahead defense.** `BarSnapshot[NowTs]` phantom-typed contract; look-ahead bias is unrepresentable at compile time, not policed at code review.
- **Custom event-driven backtest engine.** ~800 LOC. Rejects vectorbt/backtrader/zipline/nautilus_trader because none let us encode look-ahead at the type level.
- **Crypto Sharpe annualization constant.** `sqrt(365 * 24 * 12) ≈ 324.2`. Not `sqrt(252)`. Pinned in a single module; every Sharpe reads from there.
- **6-phase decomposition.** Coarse granularity but DAG + Pitfall 23 force this minimum; further compression breaks the type-contract-first ordering or merges "engine works" with "research succeeds."
- **Tier-1 exchanges only.** Binance, Coinbase, Kraken. Documented wash-trade contamination on smaller venues is unacceptable.
- **Macro-defined frozen regime labels.** No HMM-derived regime detection in Ring 1; labels are a TOML file, never an algorithm.
- **Vault as typed I/O.** `berakah_KB/` is a sibling directory of `berakah/`, version-controlled in the same repo, written-to only via the 5-function `berakah.vault.api`.

### Open Questions (deferred to phase planning)

- **Phase 4:** CPCV path-count default for single-laptop budget (50 / 100 / 200)
- **Phase 4:** Final-validation slice shape (contiguous last-3-months vs non-contiguous regime samples)
- **Phase 5:** Exact `_index.md` structure; `obsidiantools` Python 3.12 compatibility smoke test
- **Phase 6:** First strategy's parameter grid (lookback / entry-z / exit-z / hold-bar)

### TODOs

- Decompose Phase 1 into executable plans via `/gsd:plan-phase 1`

### Blockers

(none)

## Session Continuity

**Last session ended:** 2026-06-04 (planning phase)
**Resume point:** Run `/gsd:plan-phase 1` to begin Phase 1 decomposition.

**Pre-flight check before starting Phase 1:**
- Confirm Python 3.12.x is the runtime
- Confirm `uv` is installed
- Confirm git working tree is clean
- Confirm `berakah_KB/` exists as sibling of `berakah/` (already does)

---
*State initialized: 2026-06-04*
