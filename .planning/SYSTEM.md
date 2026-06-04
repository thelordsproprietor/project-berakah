# Berakah — System Diagrams

**Created:** 2026-06-04
**Source of truth:** `.planning/research/ARCHITECTURE.md` (this doc visualizes; that doc specifies)
**Format:** Mermaid (renders natively on GitHub + Obsidian)

This document is the **visual living layer** of the Berakah Ring 1 design. Every diagram cites the ARCHITECTURE.md section it visualizes so drift is auditable. When ARCHITECTURE.md changes, regenerate or re-verify the affected diagram and update the citation.

## Contents

1. [System Architecture (zoomed out)](#1-system-architecture-zoomed-out) — actors, modules, storage, external systems
2. [Module Dependency DAG](#2-module-dependency-dag) — the strict acyclic import graph, CI-enforced
3. [Runtime Data Flow — `berakah run HYP-001`](#3-runtime-data-flow--berakah-run-hyp-001) — end-to-end sequence of one full research loop
4. [Hypothesis Lifecycle State Machine](#4-hypothesis-lifecycle-state-machine) — `drafted → backtested → validated | invalidated`
5. [Look-Ahead Defense — Type Contract View](#5-look-ahead-defense--type-contract-view) — how `BarSnapshot[NowTs]` makes future-bar leakage unrepresentable

---

## 1. System Architecture (zoomed out)

**Visualizes:** ARCHITECTURE.md §1.1 (system context) and §6 (project tree + vault placement).

The bird's-eye view: the operator (PM) authors hypotheses in the Obsidian vault; the `berakah` Python package consumes the vault note + the on-disk data + the on-disk config, runs the research pipeline, writes artifacts to disk, and writes a Markdown validation report *back* into the vault. External world is just Tier-1 exchanges (for historical OHLCV ingestion) and GitHub (for versioning).

```mermaid
flowchart TB
    %% Actors
    OP([Operator / PM]):::actor

    %% External systems
    EX1[(Binance)]:::external
    EX2[(Coinbase)]:::external
    EX3[(Kraken)]:::external
    GH[(GitHub<br/>thelordsproprietor/<br/>project-berakah)]:::external

    %% The two halves of the project
    subgraph repo["repo: C:\Users\omani\projects\berakah\"]
        direction TB

        subgraph vault["berakah_KB/  (Obsidian vault — research record)"]
            direction LR
            DZ[/"doczero.md<br/>(immutable seed)"/]:::vaultDoc
            HYP[/"hypotheses/<br/>HYP-XXX-{slug}.md"/]:::vaultDoc
            RPT[/"reports/<br/>{HYP-ID}/{run_ts}.md"/]:::vaultDoc
            IDX[/"_index.md<br/>(audit log)"/]:::vaultDoc
        end

        subgraph code["berakah/  (Python package — engine of record)"]
            direction TB
            CFG[berakah.config<br/>frozen Pydantic Settings]:::module
            TYPES[berakah.types<br/>BarSnapshot, Strategy Protocol, IDs]:::module
            DATA[berakah.data<br/>ingest · store · load · regime]:::module
            STRAT[berakah.strategy<br/>Strategy Protocol impls]:::module
            BT[berakah.backtest<br/>pure-reducer engine]:::module
            VAL[berakah.validation<br/>IS/OOS · DSR · PBO · CPCV · PROOF-01]:::module
            VLT[berakah.vault<br/>5-function API]:::module
            CLI[berakah.cli<br/>typer subcommands]:::module
        end

        subgraph storage["disk artifacts (gitignored)"]
            direction LR
            PQT[("data/<br/>{exchange}/{pair}/<br/>{tf}/{YYYY-MM}.parquet")]:::store
            ART[("artifacts/runs/<br/>{run_id}/<br/>ledger.parquet<br/>summary.json")]:::store
            LCK[("artifacts/locks/<br/>{hyp_id}.lock<br/>(final-slice lock)")]:::store
        end
    end

    %% Operator interactions
    OP -- "authors hypothesis" --> HYP
    OP -- "invokes" --> CLI
    OP -- "reads validation reports" --> RPT

    %% Data ingestion
    EX1 -. ccxt REST .-> DATA
    EX2 -. ccxt REST .-> DATA
    EX3 -. ccxt REST .-> DATA

    %% Vault ↔ engine
    HYP -- "vault.read_hypothesis" --> VLT
    VLT --> RPT
    VLT --> IDX

    %% Storage flow
    DATA --> PQT
    PQT -. DuckDB views .-> DATA
    BT --> ART
    VAL --> ART
    VAL -- "locks final slice" --> LCK

    %% Module composition (high level only — see Diagram 2 for full DAG)
    CFG -. injects config .-> DATA
    CFG -. injects config .-> BT
    CFG -. injects config .-> VAL
    CFG -. injects config .-> VLT
    CLI -- composes --> DATA
    CLI -- composes --> BT
    CLI -- composes --> VAL
    CLI -- composes --> VLT

    %% Version control
    repo -. git push .-> GH

    %% Styling
    classDef actor fill:#fef3c7,stroke:#92400e,stroke-width:2px,color:#1f2937
    classDef external fill:#dbeafe,stroke:#1e40af,stroke-width:2px,color:#1e3a8a
    classDef vaultDoc fill:#fce7f3,stroke:#9d174d,stroke-width:1px,color:#1f2937
    classDef module fill:#d1fae5,stroke:#065f46,stroke-width:1px,color:#1f2937
    classDef store fill:#e5e7eb,stroke:#374151,stroke-width:1px,color:#1f2937
```

**Reading the diagram:**
- The **vault** (pink) and the **Python package** (green) live as siblings in the repo. Both are tracked in git; the gitignored `data/` and `artifacts/` directories are deliberately *not* in git — they're regenerable from code + Parquet snapshots.
- The vault and code communicate through *one* legal touchpoint: `berakah.vault`'s 5-function API. No other module imports vault paths (CI-enforced by `import-linter`).
- The operator's daily loop is **author note → invoke CLI → read report back in vault.** Everything else is automation.

---

## 2. Module Dependency DAG

**Visualizes:** ARCHITECTURE.md §1.3 (build order) and §1.2 (module responsibilities).

This is the only legal acyclic build order. Every arrow is an *import* (downstream depends on upstream). `import-linter` is configured to reject any PR that introduces a reverse edge. Phase numbers reflect ROADMAP.md.

```mermaid
flowchart TD
    %% Layer 0
    TYPES["berakah.types<br/><br/>Bars · BarSnapshot[NowTs] ·<br/>OrderIntent · Fill · Trade ·<br/>Position · Equity · MetricSet ·<br/>RegimeLabel · Strategy Protocol ·<br/>NewType IDs"]:::layer0

    %% Layer 1 (parallel siblings)
    CFG["berakah.config<br/><br/>BerakahConfig<br/>(Pydantic Settings,<br/>frozen=True, extra=forbid)"]:::layer1
    DATA["berakah.data<br/><br/>ingest · store ·<br/>load · regime"]:::layer1
    STRAT["berakah.strategy<br/><br/>Strategy Protocol impls<br/>(one module per hypothesis)"]:::layer1

    %% Layer 2
    BT["berakah.backtest<br/><br/>pure-reducer event loop ·<br/>sizing · fees · fills ·<br/>artifact writer"]:::layer2

    %% Layer 3
    VAL["berakah.validation<br/><br/>IS/OOS split · metrics ·<br/>DSR · PBO · CPCV ·<br/>final-slice lock ·<br/>PROOF-01 multi-gate"]:::layer3

    %% Layer 4
    VLT["berakah.vault<br/><br/>5-function API<br/>(read_hypothesis, list_hypotheses,<br/>write_report, append_backlink,<br/>update_index)"]:::layer4

    %% Layer 5 (composition only)
    CLI["berakah.cli<br/><br/>typer subcommands:<br/>ingest · backtest · validate · run"]:::layer5

    %% Phase annotations
    P1[/Phase 1/]:::phase
    P2[/Phase 2/]:::phase
    P3[/Phase 3/]:::phase
    P4[/Phase 4/]:::phase
    P5[/Phase 5/]:::phase
    P6[/Phase 6/]:::phase

    %% Edges (downstream depends on upstream)
    TYPES --> CFG
    TYPES --> DATA
    TYPES --> STRAT
    TYPES --> BT
    TYPES --> VAL
    TYPES --> VLT

    CFG --> DATA
    CFG --> BT
    CFG --> VAL
    CFG --> VLT

    DATA --> BT
    STRAT --> BT

    BT --> VAL
    VAL --> VLT

    DATA --> CLI
    STRAT --> CLI
    BT --> CLI
    VAL --> CLI
    VLT --> CLI

    %% Phase mappings
    P1 -.-> TYPES
    P1 -.-> CFG
    P2 -.-> DATA
    P3 -.-> STRAT
    P3 -.-> BT
    P4 -.-> VAL
    P5 -.-> VLT
    P6 -.-> CLI

    %% Forbidden edges (visual reminder — these would be CI-blocked)
    STRAT -.->|"❌ forbidden:<br/>strategy cannot import data"| DATA
    STRAT -.->|"❌ forbidden:<br/>strategy cannot import vault"| VLT
    STRAT -.->|"❌ forbidden:<br/>strategy cannot import backtest"| BT

    %% Styling
    classDef layer0 fill:#fee2e2,stroke:#991b1b,stroke-width:2px,color:#1f2937
    classDef layer1 fill:#fed7aa,stroke:#9a3412,stroke-width:2px,color:#1f2937
    classDef layer2 fill:#fef08a,stroke:#854d0e,stroke-width:2px,color:#1f2937
    classDef layer3 fill:#d9f99d,stroke:#3f6212,stroke-width:2px,color:#1f2937
    classDef layer4 fill:#bbf7d0,stroke:#166534,stroke-width:2px,color:#1f2937
    classDef layer5 fill:#bfdbfe,stroke:#1e40af,stroke-width:2px,color:#1f2937
    classDef phase fill:#fff,stroke:#6b7280,stroke-dasharray:5,color:#374151
```

**Reading the diagram:**
- **Layer 0 (`types`)** has zero internal imports. It's the foundation. Phase 1 builds it before any logic exists.
- **Layer 1 (`config`, `data`, `strategy`)** can be built in parallel — they don't depend on each other.
- **Strategy is uniquely sandboxed**: it can only import from `types` and `config`. `import-linter` forbids edges to `data`, `vault`, `backtest`. The dotted red arrows show what CI rejects.
- **The DAG strictly forces the phase order.** You cannot build Phase 3 before Phase 1; Phase 4 cannot start until Phase 3's `BacktestArtifact` shape is stable.

---

## 3. Runtime Data Flow — `berakah run HYP-001`

**Visualizes:** ARCHITECTURE.md §3 (data flow table) and §4 (backtest pseudocode).

This is the **operator's daily loop** in full. The composite CLI command `berakah run HYP-001` triggers all five subsystems in sequence. Every disk write is an idempotent artifact addressed by `run_id`. The vault is touched twice: read at the start, written at the end.

```mermaid
sequenceDiagram
    autonumber
    actor OP as Operator
    participant CLI as berakah.cli
    participant CFG as berakah.config
    participant VLT as berakah.vault
    participant DATA as berakah.data
    participant STRAT as berakah.strategy<br/>(HYP-001 module)
    participant BT as berakah.backtest
    participant VAL as berakah.validation
    participant DISK as disk artifacts
    participant VAULT as berakah_KB/

    OP->>CLI: berakah run HYP-001
    activate CLI

    CLI->>CFG: load BerakahConfig (frozen)
    CFG-->>CLI: cfg

    CLI->>VLT: read_hypothesis(HYP-001)
    activate VLT
    VLT->>VAULT: read hypotheses/HYP-001-*.md
    VAULT-->>VLT: HypothesisNote(frontmatter+body)
    VLT-->>CLI: HypothesisNote
    deactivate VLT

    CLI->>CLI: verify strategy_commit reachable from HEAD
    Note over CLI: pre-commit guard equivalent<br/>at runtime — refuses if SHA<br/>not in git log (REPORT-04)

    CLI->>DATA: bars_for(pair, tf, start, end)
    activate DATA
    DATA->>DISK: DuckDB query over Parquet
    DISK-->>DATA: typed Bars view
    DATA-->>CLI: Bars (regime-labeled)
    deactivate DATA

    CLI->>STRAT: dynamic import strategy_module
    STRAT-->>CLI: STRATEGY: Strategy

    CLI->>BT: engine.run(strategy, bars, cfg)
    activate BT
    loop for each bar in chronological order
        BT->>BT: snap = BarSnapshot[bar.close_ts](bars)
        BT->>STRAT: strategy.on_bar(snap)
        STRAT-->>BT: tuple[OrderIntent, ...]
        BT->>BT: simulate fill at next_bar.open<br/>+ apply fees + update state
    end
    BT->>DISK: write artifacts/runs/{run_id}/<br/>{ledger.parquet, summary.json}
    BT-->>CLI: BacktestArtifact(run_id, path)
    deactivate BT

    CLI->>VAL: validate(artifact, hypothesis)
    activate VAL
    VAL->>DISK: read BacktestArtifact
    VAL->>VAL: IS/OOS split keyed off frozen_ts
    VAL->>VAL: compute Sharpe (×sqrt(105_120))<br/>+ bootstrap CI<br/>+ regime-stratified
    VAL->>VAL: compute DSR, PBO via CSCV,<br/>CPCV with purge+embargo
    VAL->>DISK: read final-slice lock for HYP-001
    alt lock unused
        VAL->>DISK: consume lock + record run_id
        VAL->>VAL: evaluate final slice
    else lock consumed
        VAL-->>CLI: FinalSliceAlreadyConsumedError
    end
    VAL->>VAL: PROOF-01 multi-gate verdict
    VAL-->>CLI: ValidationReport(verdict, metrics)
    deactivate VAL

    CLI->>VLT: write_report(HYP-001, ValidationReport)
    activate VLT
    VLT->>VLT: render Markdown via Jinja2<br/>+ pin frontmatter:<br/>strategy_commit, data_commit,<br/>frozen_ts, run_id, verdict
    VLT->>VAULT: write reports/HYP-001/{run_ts}.md
    VLT->>VAULT: append backlink to hypothesis note
    VLT->>VAULT: append entry to _index.md audit log
    VLT-->>CLI: report_path
    deactivate VLT

    CLI-->>OP: exit code + verdict + report_path
    deactivate CLI

    Note over OP,VAULT: Operator reads the new Markdown report<br/>inside Obsidian. If PROOF-01 PASS:<br/>edge claim. If FAIL: named failing gate(s)<br/>guide next hypothesis revision.
```

**Reading the diagram:**
- **Step 6 (verify SHA reachable)** is the runtime arm of the vault/code-drift defense. The pre-commit guard (Pitfall 20 defense) blocks bad commits; this runtime check blocks bad *runs*.
- **The backtest loop (steps 11–14)** is where the look-ahead type contract pays off: `snap = BarSnapshot[bar.close_ts](bars)` is the *only* way the strategy sees bars. The phantom type forbids future-bar access at compile time.
- **The final-slice lock (steps 22–25)** is once-per-hypothesis. If the operator tries to re-run validation to "see if it goes up this time," they get `FinalSliceAlreadyConsumedError`. This is researcher-multiple-testing defense (Pitfall 4).
- **The vault writes (steps 29–32)** are atomic from the operator's perspective: report file + backlink + audit log in one transaction. The pre-commit guard runs before any of this is staged.

---

## 4. Hypothesis Lifecycle State Machine

**Visualizes:** REQUIREMENTS.md HYP-03 (lifecycle frontmatter status field) and PITFALLS.md Pitfall 22 (trial budget + cooling-off + kill-window).

Every hypothesis note has a `status` frontmatter field that moves through this state machine. The vault `_index.md` audit log records every transition. The 6-month project kill trigger sums `validated + invalidated` counts to determine "no signal absence."

```mermaid
stateDiagram-v2
    [*] --> drafted: operator creates<br/>HYP-XXX-{slug}.md<br/>with frontmatter

    drafted --> backtested: berakah backtest HYP-XXX<br/>succeeds<br/>(BacktestArtifact written)

    backtested --> backtested: re-run within<br/>trial_budget<br/>(parameter tweaks<br/>on IS data only)

    backtested --> validated: berakah validate HYP-XXX<br/>PROOF-01 PASS<br/>(all 5 gates clear)

    backtested --> invalidated: trial_budget exhausted<br/>OR<br/>PROOF-01 FAIL on final slice<br/>(FinalSliceAlreadyConsumedError<br/>blocks retry)

    backtested --> drafted: operator decides<br/>to revise hypothesis<br/>(creates new frozen_ts<br/>+ resets trial_budget)

    validated --> [*]: terminal — counts toward<br/>"edge proven" milestone
    invalidated --> [*]: terminal — counts toward<br/>kill-trigger denominator

    note right of drafted
        Frontmatter required:
        - strategy_module
        - strategy_commit (SHA)
        - data_manifest
        - data_commit
        - created_ts
        - frozen_ts (set when first backtest runs)
        - trial_budget (N reruns allowed)
        - status: drafted
    end note

    note right of backtested
        Each run records:
        - run_id (deterministic hash)
        - timestamp
        - rolling-3m OOS Sharpe
        Counts against trial_budget.
    end note

    note right of validated
        Hypothesis frontmatter
        updated atomically:
        - status: validated
        - validated_ts
        - final_run_id
        Vault _index.md records
        the validation event.
    end note

    note right of invalidated
        Hypothesis frontmatter
        updated atomically:
        - status: invalidated
        - invalidated_ts
        - reason: trial_budget_exhausted
                | proof_01_failed
                | final_slice_failed
        Counts toward the 6-month
        kill-trigger statistic.
    end note
```

**Reading the diagram:**
- **`drafted` is the only entry state**, and it requires the full frontmatter binding. No code runs until the note is well-formed.
- **`backtested → backtested` self-loop** is the legitimate researcher iteration: tweak parameters on IS data, re-run, see if signal strengthens. Each loop costs one trial-budget unit.
- **`backtested → invalidated`** has two triggers: trial budget exhausted (you're out of attempts) OR final-slice failure (the locked OOS slice killed the hypothesis). Both are terminal.
- **`backtested → drafted`** is the "I had the wrong hypothesis, let me re-think" path: the operator creates a *new* `frozen_ts` and `trial_budget`, effectively starting a fresh hypothesis. Old runs persist for audit but don't count against the new budget.
- **Both terminal states feed the project kill-trigger statistic.** If after 6 months no hypothesis has reached `validated`, the project ends.

---

## 5. Look-Ahead Defense — Type Contract View

**Visualizes:** ARCHITECTURE.md §2 (the `BarSnapshot[NowTs]` pattern) and PITFALLS.md Pitfalls 1, 2 (look-ahead bias).

This is the load-bearing safety asset of the entire engine. The strategy only ever receives a `BarSnapshot[NowTs]` — a phantom-typed view of the full bar history that is *structurally incapable* of exposing bars at or after `now_ts`. The Python type system, `pyright --strict`, `import-linter`, and `hypothesis` adversarial tests together make leakage impossible to write.

```mermaid
flowchart LR
    subgraph timeline["Bar Timeline (chronological)"]
        direction LR
        B1[Bar t-3<br/>closed]:::closed
        B2[Bar t-2<br/>closed]:::closed
        B3[Bar t-1<br/>closed]:::closed
        BNOW["Bar t<br/>(now_ts)<br/>just closed"]:::nowbar
        B5[Bar t+1<br/>FUTURE]:::future
        B6[Bar t+2<br/>FUTURE]:::future
        B7[Bar t+3<br/>FUTURE]:::future
        B1 --> B2 --> B3 --> BNOW --> B5 --> B6 --> B7
    end

    subgraph snapshot["BarSnapshot[NowTs=t]<br/>(what the strategy sees)"]
        direction LR
        V1[t-3]:::visible
        V2[t-2]:::visible
        V3[t-1]:::visible
        V4[t]:::visible
        V1 --> V2 --> V3 --> V4
    end

    subgraph strategy["Strategy.on_bar"]
        direction TB
        SIG[/"signature:<br/>on_bar(snap: BarSnapshot[NowTs])<br/>-> tuple[OrderIntent, ...]"/]:::sig
        BODY[/"body only sees<br/>'snap'.<br/>cannot reach the<br/>full Bars history"/]:::body
        SIG --> BODY
    end

    %% Visibility mapping
    B1 -.-> V1
    B2 -.-> V2
    B3 -.-> V3
    BNOW -.-> V4

    %% Forbidden access (compile-time error)
    B5 -. "❌ pyright error:<br/>cannot construct<br/>BarSnapshot[t] from t+1" .-> snapshot
    B6 -. "❌ phantom.parse rejects" .-> snapshot
    B7 -. "❌ hypothesis<br/>adversarial test<br/>cannot find<br/>leaky input" .-> snapshot

    snapshot --> strategy

    %% Defense layers
    subgraph defenses["Static enforcement (CI-blocking)"]
        direction TB
        D1[pyright --strict<br/>compile-time]:::defense
        D2[phantom-types<br/>predicate at construction]:::defense
        D3[import-linter<br/>strategy cannot import data]:::defense
        D4[hypothesis adversarial<br/>property tests]:::defense
        D5[ruff rule:<br/>no pd.DataFrame in<br/>strategy module params]:::defense
    end

    strategy --> defenses

    %% Styling
    classDef closed fill:#bbf7d0,stroke:#166534,stroke-width:1px,color:#1f2937
    classDef nowbar fill:#fbbf24,stroke:#92400e,stroke-width:2px,color:#1f2937
    classDef future fill:#fecaca,stroke:#991b1b,stroke-width:2px,color:#1f2937,stroke-dasharray:5
    classDef visible fill:#bbf7d0,stroke:#166534,stroke-width:1px,color:#1f2937
    classDef sig fill:#e0e7ff,stroke:#3730a3,stroke-width:1px,color:#1f2937
    classDef body fill:#f5f3ff,stroke:#5b21b6,stroke-width:1px,color:#1f2937
    classDef defense fill:#fef3c7,stroke:#92400e,stroke-width:1px,color:#1f2937
```

**Reading the diagram:**
- **The bar timeline (top)** shows what exists in the data store. Green bars are closed; the orange "now" bar just closed; red bars are future bars the strategy must not see.
- **The `BarSnapshot[NowTs=t]`** is a typed view that exposes only bars with `close_ts <= t`. There is no `.future_bars()` method. There is no way to call `snap[t+1]`.
- **The strategy signature** `on_bar(snap: BarSnapshot[NowTs])` is the *only* legal entry point. The strategy module cannot import `berakah.data` (import-linter blocks it), so it cannot reach the full Bars history sideways.
- **Five enforcement layers** make this CI-blocking:
  1. `pyright --strict` — phantom-typed generic rejects construction with future bars at compile time.
  2. `phantom-types` predicate — runtime backstop at construction.
  3. `import-linter` — strategy module cannot import `data`, `vault`, or `backtest`.
  4. `hypothesis` adversarial tests — tries to find inputs that produce leaky snapshots; CI fails if it does.
  5. `ruff` rule — strategy parameters cannot be `pd.DataFrame` (too easy to leak through).

**Why this matters:** Pitfall 1 (look-ahead bias) is *the* single failure mode that destroys a research engine's core value. Most quant systems police it through code review and prayer. Berakah makes it **impossible to write code that leaks.** The architecture is the guarantee.

---

## Maintenance discipline

This document is one of the four living docs maintained at phase transitions. Refresh triggers:

1. **After ARCHITECTURE.md changes** — re-verify each diagram against its cited ARCHITECTURE section. Update Mermaid source to match.
2. **After a new module is added or moved** — Diagrams 1 and 2 need updates; check if Diagram 3 sequence changes.
3. **When a control-flow assumption changes** (e.g., backtest engine becomes async, or vault gains a new touchpoint) — re-verify Diagram 3.
4. **When a lifecycle state is added or transitions change** — Diagram 4 needs updates.
5. **When the type contract changes** (extremely rare; would be a major architecture revision) — Diagram 5 needs updates.

Drift between this doc and ARCHITECTURE.md is a phase-transition blocker — fix the diagrams before declaring the phase complete.

---
*Last updated: 2026-06-04 after initialization*
