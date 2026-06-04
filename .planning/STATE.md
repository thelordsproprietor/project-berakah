---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_plan: Not started
status: planning
stopped_at: "Completed 01-02-PLAN.md (2 task commits: c356ae5, 743ff1a). HYP-02 realized at compile-time + runtime + adversarial."
last_updated: "2026-06-04T23:34:19.066Z"
last_activity: 2026-06-04
progress:
  total_phases: 6
  completed_phases: 1
  total_plans: 3
  completed_plans: 3
---

# Project State: Berakah Ring 1

**Last updated:** 2026-06-05
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

**Phase:** 2
Current Plan: Not started
Total Plans in Phase: 3
Plan: 3 of 3
**Status:** Ready to plan
**Last activity:** 2026-06-04

**Progress (current phase, by plan):**

```
[██████████] 100%
```

**Progress (project, by phase):**

```
[1/6 phases complete (Phase 1 ready for /gsd:transition)]
███░░░░░░░░░░░░░░░░░ 17%
```

## Roadmap Snapshot

| # | Phase | Status | Requirements |
|---|-------|--------|--------------|
| 1 | Typed Foundation + Look-Ahead Contract | Complete (3/3 plans complete; all requirements validated) | HYP-02, CONFIG-01/02/03 |
| 2 | Data Layer + Regime Labels | Not started | DATA-01/02/03 |
| 3 | Strategy Contract + Backtest Engine | Not started | HYP-01, BT-01/02/03 |
| 4 | Validation Discipline | Not started | VAL-01/02/03/04/05/06/07 |
| 5 | Vault Round-Trip + Report Layer | Not started | HYP-03, REPORT-01/02/03/04 |
| 6 | CLI Wiring + First PROOF-01 Attempt | Not started | CLI-01/02/03/04, PROOF-01 |

## Performance Metrics

(Populated by `/gsd:transition` as phases complete.)

- **Phases completed:** 0 / 6 (Phase 1 complete; awaiting `/gsd:transition` to formally close it)
- **Plans completed:** 3
- **Requirements validated:** 4 / 28 (HYP-02, CONFIG-01, CONFIG-02, CONFIG-03)
- **Kill-window days remaining:** TBD (clock starts when engine ships in Phase 6)

### Plan-level metrics

| Phase | Plan | Duration | Tasks | Files | Completed |
|---|---|---|---|---|---|
| 01 | 01 (toolchain-bootstrap) | ~15 min | 3 | 14 (13 created, 1 modified) | 2026-06-04 |
| 01 | 02 (look-ahead-type-contract) | ~13 min | 2 | 21 (21 created, 2 modified) | 2026-06-05 |
| 01 | 03 (config + import-linter) | ~11 min | 2 | 14 | 2026-06-05 |

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
- [Phase 01]: (Plan 01-03) pydantic-settings v2 silently accepts unknown env vars under extra='forbid' — closed via model_validator(mode='before') reading os.environ once at construction time; this is the only direct env-var read in the codebase
- [Phase 01]: (Plan 01-03) Permanently staged 6 empty __init__.py placeholders for berakah/{data,strategy,backtest,validation,vault,cli}/ — required to activate import-linter forbidden-edge contracts from Phase 1 (import-linter 2.6 hard-errors if source_modules references a non-existent module); these are infrastructure-not-edge per Pitfall 23, similar to berakah/py.typed
- [Phase 01]: (Plan 01-03) types-purity contract commented out pending Plan 01-02 landing berakah/types/__init__.py — Plan 02's SUMMARY should enable it. Literal contract name remains in importlinter.cfg (in a comment) for traceability test.
- [Phase 01]: (Plan 01-03) Fixed .gitignore: changed data/ and artifacts/ (unanchored) to /data/ and /artifacts/ (repo-root-anchored) — unanchored form was matching berakah/data/ and berakah/artifacts/ source packages and silently hiding them from version control
- [Phase 01]: (Plan 01-03) cfg.annualization_factor = sqrt(105_120) is the single source of truth for the crypto Sharpe constant — Pitfall 11 prevention. Phase 4 must import from BerakahConfig, not define a separate module-level constant.
- [Phase 01]: (Plan 01-02) PEP 695 syntax chosen over legacy Generic[TypeVar]+TypeAlias forms — type Bars = pl.DataFrame, class BarSnapshot[T_Now: datetime], class RegimeLabel(StrEnum), class Side(StrEnum). Ruff UP040/UP042/UP046 enforce this; pyright handles both equivalently. PEP 695 is the canonical Python 3.12+ idiom.
- [Phase 01]: (Plan 01-02) phantom-types library NOT used despite STACK.md flagging it as load-bearing for HYP-02. phantom-types' Phantom pattern requires multiple-inheritance with the wrapped type, incompatible with polars.DataFrame's Rust-backed __init__. ARCHITECTURE.md §2.1's exact sketch uses Generic[T_Now] + parse() classmethod + private _frame attribute — the architecturally cleaner pattern (and what was implemented). The runtime predicate fires in BarSnapshot.parse() via FutureBarLeakageError raise; the compile-time shield comes from pyright treating BarSnapshot[NowTs] and BarSnapshot[datetime] as distinct under PEP 695.
- [Phase 01]: (Plan 01-02) I001 (isort) per-file-ignore added for tests/unit/types/*.py and tests/property/*.py because the LOCKED TYPE_CHECKING discipline (one  per line with  per line) is incompatible with isort's import-collapsing. Scope narrow: only RED-phase test files; production code in berakah/ has full I001 enforcement.
- [Phase 01]: (Plan 01-02) HYP-02 realized at all 3 levels demanded by ROADMAP SC2: (1) pyright compile-time — mechanical subprocess proof in tests/property/test_barsnapshot_pyright_rejects.py runs 'uv run pyright --outputjson' on a generated fixture and asserts error "Type datetime is not assignable to declared type NowTs" fires; (2) runtime — FutureBarLeakageError raised by BarSnapshot.parse when close_ts > now_ts; (3) adversarial — hypothesis @given runs 200 examples (200 passing, 0 failing, 3 invalid) confirming no input produces a leaky snapshot.

### Decisions logged during execution

- **(Plan 01-01) uv installed via official PowerShell installer to `C:\Users\omani\.local\bin\uv.exe`** (uv was not on PATH at session start; bootstrap is a documented STACK.md step). User PATH may need restart for `uv` to be invokable without absolute path.
- **(Plan 01-01) Pyright strict scope set to `["berakah"]` only**, not `["berakah", "tests"]` as the plan spec suggested. The strict-list array overrides per-environment settings, so `tests/` uses an `executionEnvironment` override that disables stub-related errors for untyped 3rd-party libraries (ccxt, scipy.stats). `berakah/` core remains fully strict.
- **(Plan 01-01) `reportMissingTypeStubs` lowered globally to `"none"`** — the type contract architecture governs `berakah/` code, not 3rd-party libraries. The `berakah/strategy/` extra-strict executionEnvironment override remains, pre-armed for Phase 3.
- **(Plan 01-01) `importlinter.cfg` kept as the canonical filename** per plan's artifact spec — pre-commit and CI invoke `lint-imports --config importlinter.cfg` explicitly because import-linter 2.6 does NOT auto-discover this filename.
- **(Plan 01-01) Pre-commit file-shape hooks exclude `berakah_KB/`, `.planning/`, and `uv.lock`** — initial run modified vault Markdown and Obsidian config (Critical Constraint #3 violation). Now excluded via regex.

### Open Questions (deferred to phase planning)

- **Phase 4:** CPCV path-count default for single-laptop budget (50 / 100 / 200)
- **Phase 4:** Final-validation slice shape (contiguous last-3-months vs non-contiguous regime samples)
- **Phase 5:** Exact `_index.md` structure; `obsidiantools` Python 3.12 compatibility smoke test — **PARTIALLY RESOLVED in Plan 01-01:** obsidiantools==0.11.0 installs cleanly on Python 3.12.13; the STACK.md yellow flag did not materialize. Full `_index.md` structure decision still deferred to Phase 5.
- **Phase 6:** First strategy's parameter grid (lookback / entry-z / exit-z / hold-bar)

### TODOs

- Phase 1 complete: invoke `/gsd:transition` to formally close Phase 1 and advance to Phase 2 (Data Layer + Regime Labels)
- Plan 01-03 left the `types-purity` import-linter contract commented out pending Plan 01-02; that contract can now be enabled because `berakah/types/__init__.py` exists (deferred to a Plan 01-03 follow-up or absorbed into Phase 2 setup)

### Blockers

(none)

## Session Continuity

**Last session ended:** 2026-06-05 (Plan 01-01 completed)
**Resume point:** Begin Wave 2 — execute Plan 01-02 and Plan 01-03 in parallel.
**Stopped at:** Completed 01-02-PLAN.md (2 task commits: c356ae5, 743ff1a). HYP-02 realized at compile-time + runtime + adversarial.

**Pre-flight check before starting Phase 1 Wave 2:**

- `uv sync --frozen` exits 0 (CONFIRMED at end of Plan 01-01)
- `uv run pyright` exits with 0 errors, 0 warnings (CONFIRMED)
- `uv run ruff check .` exits 0 (CONFIRMED)
- `uv run pytest tests/` exits 0 (6 toolchain tests pass) (CONFIRMED)
- `berakah/__init__.py` is empty (CONFIRMED — Pitfall 23 maintained)

---
*State initialized: 2026-06-04*
*Plan 01-01 completed: 2026-06-04 (durable evidence in 01-01-SUMMARY.md)*
