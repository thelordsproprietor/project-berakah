# Berakah

## What This Is

Berakah is an AI-augmented systematic trading research engine fused with a Karpathy-style Obsidian knowledge base (the `berakah_KB/` vault). The MVP — "Ring 1" — is the research engine alone: it ingests historical BTC/ETH market data, encodes mean-reversion hypotheses as testable strategies, runs out-of-sample backtests with vol-targeted sizing, and writes validation results back to the vault as Markdown research records. No paper trading, no live execution. The operator is a single PM (Ronald) directing Claude Code as the implementation engine.

## Core Value

**The research engine must produce trustworthy out-of-sample edge measurements** — no leakage, no overfitting, no look-ahead. If validation infrastructure is broken, nothing downstream matters. Every architectural choice serves this.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

(None yet — ship to validate)

### Active

<!-- Current scope. Building toward these. Hypotheses until validated. -->

- [ ] **DATA-01**: Engine ingests historical BTC/ETH OHLCV from Tier-1 exchanges (Binance, Coinbase, Kraken) at ≥5-minute resolution and stores it in a queryable analytical format
- [ ] **DATA-02**: Engine annotates the data record with regime labels for the four named regimes (Bull 2020–21, Bear 2022, Recovery 2023, ETF era 2024–)
- [ ] **HYP-01**: Operator can author a mean-reversion hypothesis as a vault Markdown note that links to an executable strategy module in code
- [ ] **HYP-02**: Strategy modules expose a compile-time-verifiable contract such that look-ahead bias (reading future bars from a current `now_ts`) is unrepresentable in the type system
- [ ] **BT-01**: Engine runs a backtest of any strategy module against the historical record with vol-targeted position sizing and explicit handling of fees
- [ ] **BT-02**: Backtest output includes regime-stratified Sharpe, drawdown, win rate, and trade-by-trade ledger, written to disk as parquet/JSON
- [ ] **VAL-01**: Engine performs explicit out-of-sample validation: in-sample / out-of-sample splits enforced by the engine, never picked post-hoc
- [ ] **VAL-02**: Engine flags any strategy where in-sample Sharpe diverges from OOS Sharpe by more than a configurable threshold (overfitting detector)
- [ ] **REPORT-01**: Engine writes a Markdown validation report back to the vault, linked to the originating hypothesis note, summarizing regime-stratified results
- [ ] **PROOF-01**: A mean-reversion strategy is found that holds **OOS Sharpe ≥ 1.0 over a rolling 3-month window** AND **regime-stratified Sharpe ≥ 0 across all four labeled regimes** — this is the "edge proven" deliverable that closes Ring 1

### Out of Scope

<!-- Explicit boundaries with reasoning. -->

- **Paper trading / simulated execution layer** — Ring 2 scope. Ring 1 ends at validated OOS edge; execution friction is a separate proof.
- **Live trading of any kind** — Ring 3 scope. Cannot exist before validation infrastructure is trusted.
- **Multi-niche strategy portfolio** — Ring 4 scope. Concentric expansion: one edge first, then broaden.
- **HMM / regime-detection overlay as an active signal modulator** — deferred to the phase after Ring 1. Regime *labels* (the four named regimes) are used for stratified validation in Ring 1, but no live regime classifier gates positions yet.
- **Sub-5-minute timeframes** — institutional spoofing/layering dominates at sub-minute scales; no defensible edge for retail at that horizon, and infra cost is disproportionate.
- **Non-Tier-1 exchanges as data sources** — wash-trade and fake-volume risk contaminates the signal record.
- **Momentum / trend-following strategy family** — explicitly *not* the first niche. Per manipulation analysis, momentum is the *most* exposed niche to institutional flow distortion. Revisit only after mean-reversion is proven.
- **Funding-rate / basis niche** — deferred. Requires perp instrument modeling; adds infrastructure surface that competes with the core validation work.
- **On-chain regime signal niche** — deferred. Whale-wallet manipulation directly contaminates the data source.
- **Alternative data, paid data feeds, LLM in the signal hot path** — out of budget and out of MVP discipline.

## Context

- **Operator**: Ronald Omanibe, working as PM. Claude Code generates effectively 100% of implementation. This means the codebase MUST be agent-friendly per the global CLAUDE.md principles: predictable patterns, exhaustive type contracts, clear module boundaries, declarative/functional style.
- **Knowledge base**: `berakah_KB/` is an Obsidian vault in a Karpathy-style wiki format. Currently contains only `doczero.md` (the seed braindump) and the default Obsidian configuration. The vault's structure will evolve to hold hypotheses, post-mortems, transcripts, papers, tool playbooks, and validation summaries linked to their source strategies.
- **Architectural lens**: doczero.md's "Concentric Monopoly Stack" — Ring 1 (research only) → Ring 2 (paper-trade) → Ring 3 (live small-size) → Ring 4 (multi-niche portfolio). Inspired by Renaissance/Medallion's many-weak-edges approach, scaled to retail.
- **Manipulation context**: BTC/ETH spot markets contain stop hunts, sustained ETF/whale flows, and short-term spoofing. Mean-reversion is the niche most resilient to the dominant manipulation tactic (stop hunts *create* the overshoots the strategy fades). Sustained directional flow is the residual risk, addressed by the deferred HMM phase and by vol-target sizing + hard drawdown caps in Ring 1.
- **Engineering principles** (from global CLAUDE.md, binding here): (1) type-driven architecture, (2) global modular composition with strict interfaces, (3) AI-agent-friendly code, (4) declarative & functional design, (5) hard constraints over loose logic. The `now_ts` look-ahead guarantee (HYP-02) is a direct application of principle 5.

## Constraints

- **Tech stack**: Python 3.12+ ecosystem only. No exotic languages. Claude generates Python; quant libraries are Python-native.
- **Tooling/data budget**: $0–25 / month total. Free historical data, free or sub-$25 APIs. No alt-data, no paid feeds.
- **Operator time**: Near full-time initially, leveraged through Claude. PM-mode, not engineer-mode.
- **Hardware**: Single laptop. Single point of failure accepted at MVP scale; no infra requirements beyond local execution.
- **Asset universe**: BTC + ETH spot only.
- **Instrument**: Plain spot only — no margin, no perp, no leverage. Removes catastrophic loss modes from the validation surface.
- **Timeframe floor**: 5-minute bars or larger.
- **Exchange whitelist**: Tier-1 only (Binance, Coinbase, Kraken).
- **Time-to-MVP target**: ~6 weeks of focused work to first validated OOS report (`PROOF-01`-attempting strategy + full validation pipeline).
- **Project kill trigger**: 6 calendar months elapsed since project start with no strategy achieving the `PROOF-01` bar (OOS Sharpe ≥ 1.0 with non-negative regime-stratified Sharpe). Time-based, not P&L-based; the trigger fires on signal absence.
- **No live capital at risk during Ring 1.** Live trading is downstream of a separate Ring-3 milestone and a separate safety-floor review.

## Key Decisions

<!-- Significant choices that constrain future work. -->

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| MVP scope: Ring 1 only (research engine, no execution layer) | doczero discipline: "smallest research machine that proves one real edge before broadening." Validation is the load-bearing asset. | — Pending |
| First edge family: BTC/ETH spot mean-reversion | Most resilient of the candidate niches to crypto's dominant manipulation tactic (stop hunts *help* mean-reversion). Sustained-flow residual risk gated by deferred HMM phase + vol-target sizing. | — Pending |
| Vault = research record, code = engine of record | Clear ownership boundary. Vault stores narrative + hypotheses + post-mortems. Code stores executable strategy modules + raw backtest outputs. Backtest reports flow back to vault as Markdown. | — Pending |
| HMM / regime overlay deferred to post-Ring-1 phase | Adds significant validation complexity (regime-conditional statistics, leakage risk). Ring 1 uses regime *labels* for stratified reporting, but no live regime classifier gates positions yet. | — Pending |
| Tier-1 exchanges only (Binance / Coinbase / Kraken) | Wash-trade and fake-volume contamination is documented on smaller venues. Tier-1 reduces the signal-integrity risk to a manageable level. | — Pending |
| 5-minute timeframe floor | Institutional spoofing/layering dominates at sub-minute scales; no defensible retail edge there. | — Pending |
| "Edge proven" bar: OOS Sharpe ≥ 1.0 (rolling 3-month) AND non-negative regime-stratified Sharpe across all 4 labeled regimes | Time-based stop trigger needs an unambiguous, math-grounded definition. This combination prevents both overfit-by-luck and regime-fragile strategies. | — Pending |
| Project kill trigger: 6 calendar months without crossing the bar above | Time-based, not P&L-based. Fires on signal absence, not on variance. Prevents the failure mode where the operator chases marginal improvements indefinitely. | — Pending |
| Start truly clean — no restoration of the discarded `c6237f7` planning history | User pivoted the project conception. The discarded artifacts framed Berakah as a more execution-heavy system; the new framing centers the vault and the research loop. | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-06-04 after initialization*
