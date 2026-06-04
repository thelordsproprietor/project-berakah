# Stack Research — Berakah Ring 1

**Domain:** AI-augmented systematic trading research engine (BTC/ETH spot mean-reversion, vault-integrated)
**Researched:** 2026-06-04
**Confidence:** HIGH on most dimensions (versions verified via PyPI June 2026). MEDIUM on backtest-engine choice (verified pattern, but the "build vs adopt" call is opinionated).

---

## TL;DR — The Stack

Python 3.12+. `uv` for everything env/dep. `polars` as the primary dataframe layer, `duckdb` over Parquet as the analytical store, `ccxt` for OHLCV ingestion. **Custom event-driven backtest engine** (not vectorbt, not backtrader) because look-ahead-as-type-contract requires owning the temporal-access surface. `pydantic` v2 + `phantom-types` + `typing.NewType` + `typing.Protocol` to encode the look-ahead invariant in the type system. `hypothesis` for property-based leakage tests. `pyright --strict` as the type-checker (with `mypy` as fallback only). `ruff` for lint+format. `pytest` for unit tests. `structlog` for queryable structured event records. `obsidiantools` + `python-frontmatter` for vault read/write. **No quantstats, no empyrical, no pyfolio** — write the metrics ourselves on top of polars+scipy because (a) they're trivial, (b) we need them computed inside the OOS-aware pipeline, and (c) `pyfolio`/`empyrical` are dead and `quantstats` ties us to pandas.

---

## Recommended Stack

### Core Technologies

| Technology | Version (June 2026) | Purpose | Why Recommended |
|------------|---------------------|---------|-----------------|
| **Python** | 3.12.x (3.13 also fine) | Language baseline | 3.12 is current LTS-grade; 3.13 brings PEP 649 lazy annotations and free-threading preview but adds churn. Pin 3.12 in `pyproject.toml`; allow 3.13 as max. Avoid 3.14 — too new (released late 2025), Pydantic just started supporting it. |
| **uv** | 0.11.19 | Package + environment + Python-version manager | Replaces pyenv + virtualenv + pip + pip-tools + ~90% of Poetry. 10–100× faster than pip. Cross-platform single lockfile (`uv.lock`). 75M monthly downloads on PyPI, now larger than Poetry. Aligns with principle #5 (hard constraints): `uv sync --frozen` enforces lockfile compliance in CI. |
| **ccxt** | 4.5.56 | Unified historical OHLCV ingestion across Binance, Coinbase, Kraken | The only Python library with maintained, unified adapters for all three Tier-1 venues at once. Releases ~weekly (last 2026-05-27). Handles auth, rate-limit, schema normalization. Alternative would be 3× per-exchange clients (Binance python-binance, Coinbase Advanced Trade SDK, krakenex) — strictly more code and more drift. |
| **polars** | 1.41.2 | Primary dataframe layer for time-series transforms, feature engineering, backtest internals | Rust core, Apache Arrow memory, lazy execution, multi-threaded by default. ~10× pandas on typical analytical workloads (verified May 2026 benchmarks). Strong native types and a real schema concept (`pl.Schema`) — pandas' `dtype` story is mush. Plays well with `pyright --strict`. Lazy mode (`.lazy()` → `.collect()`) lets the engine push down predicates to the parquet/duckdb layer for free. |
| **duckdb** | 1.5.3 | Analytical SQL engine over Parquet (bar data, regime labels, trade ledgers) | In-process, zero-config, columnar, vectorized. Zero-copy interop with Polars and Arrow. Native `ASOF JOIN` is built for point-in-time alignment of bars to regime labels and trades to bars — directly serves VAL-01. Reads Parquet directly via `read_parquet('path/*.parquet')` with predicate pushdown. No daemon, no port, no server cost. |
| **pyarrow** | 24.0.0 | Parquet I/O substrate underneath polars and duckdb | The de-facto Parquet implementation. Polars and DuckDB both use it under the hood for cross-language portability of the data record. Declare it as an explicit dep (don't rely on transitive). |
| **pydantic** | 2.13.4 | Boundary validation (frontmatter parsing, ccxt response parsing, strategy module config) | The validation-at-boundaries half of principle #1. v2 is Rust-cored and fast. Pyright plugin gap is now closed in v2 via static type emission. Use `BaseModel` at I/O boundaries; use plain dataclasses or NewType/Protocol inside the pure core. **Do not** use pydantic for hot-loop bar processing — too much overhead. |
| **phantom-types** | 3.0.2 | Compile-time encoding of the "this value has been temporally guarded" invariant | The load-bearing library for HYP-02. Lets us define `PointInTimeBars = phantom(predicate=is_point_in_time_safe)` and have pyright refuse any path where raw `Bars` is passed to a function expecting `PointInTimeBars`. See "Look-ahead as type contract" section below. Maintained, production-stable, used by serious shops for Parse-Don't-Validate patterns. |

### Supporting Libraries

| Library | Version (June 2026) | Purpose | When to Use |
|---------|---------------------|---------|-------------|
| **structlog** | 25.5.0 | Structured event logging — every bar processed, every signal fired, every fill simulated emits a queryable JSON record | Always. Configure with the JSON renderer + filesystem sink so the entire backtest run can be replayed/audited by `duckdb.read_json_auto()`. ~25% faster than loguru, contextvar-aware (binds `strategy_id`, `bar_ts`, `run_id` to every line without re-passing). |
| **scipy** | 1.14.x | `scipy.stats` for Sharpe ratio CI, Welch's t-test on IS vs OOS Sharpe (the VAL-02 overfitting detector), bootstrap resampling | Always — this is the entire VAL-02 surface. Trivial to use; no need for any wrapper library. |
| **numpy** | 2.1.x | Numerical primitives under polars; explicit dep for rolling stats and the rare hand-written vectorized loop | Implicit via polars/scipy but pin it. NumPy 2.x is the current stable. |
| **hypothesis** | 6.155.1 | Property-based testing of the temporal invariant — `@given(arbitrary_strategy, arbitrary_bars)` then assert no future bar was read | Always for the strategy contract layer (see "Look-ahead as type contract"). Used by CPython stdlib, NumPy, Pydantic — proven to find leakage bugs by adversarial input generation. |
| **obsidiantools** | 0.11.0 | Parse the `berakah_KB/` vault: extract wikilinks, frontmatter, the link graph | Use in the *read* direction — when the engine looks up a hypothesis note linked from a strategy module, or builds a backlink-aware report. Python 3.9+ (we're on 3.12, fine). Maintained, the one credible Obsidian-aware library in Python. |
| **python-frontmatter** | 1.3.0 | Read/**write** YAML frontmatter in Markdown files (the engine *generates* validation reports back to the vault) | Use in the *write* direction — `obsidiantools` is read-mostly. `python-frontmatter` is the canonical write-side library: `frontmatter.dumps(post)` round-trips cleanly with Obsidian's parser. |
| **PyYAML** | 6.0.x | Frontmatter dep, also for the engine's own config files | Implicit via python-frontmatter; pin it. Use `yaml.safe_load` only. |
| **markdown-it-py** | 3.0.x | The Markdown AST library that `obsidiantools` uses internally; expose it for custom report generation if needed | Optional. Reach for it only if `python-frontmatter` writes don't preserve Obsidian's wikilinks correctly (they should — wikilinks live in body text and the body is opaque to frontmatter libs). |
| **httpx** | 0.27.x | HTTP client for any direct exchange REST calls (ccxt covers OHLCV but we may want raw klines from Binance for cross-check) | When ccxt's normalization is suspected of dropping precision. Async-capable, modern, type-stub-friendly. |
| **tenacity** | 9.0.x | Retry-with-backoff decorator for the ingestion layer (exchange rate-limit responses, transient network) | Always in the ingestion module. Declarative `@retry` decorator is idiomatic, plays well with structlog (`before_sleep_log`). |
| **rich** | 13.x | Pretty CLI output for backtest progress bars, regime-stratified result tables when running locally | Operator-facing only. Keep it out of the engine core. |

### Development Tools

| Tool | Version (June 2026) | Purpose | Notes |
|------|---------------------|---------|-------|
| **pyright** | 1.1.410 | Primary static type checker, run in `--strict` mode | The most spec-conformant checker (98% vs mypy's 58%), 2–5× faster than mypy, and it's what powers the user's editor via Pylance. Configure via `pyrightconfig.json` with `strict: ["src/"]`. This is the compile-time shield for HYP-02. |
| **ruff** | 0.15.16 | Linter + formatter (replaces flake8, black, isort, pyupgrade, pydocstyle, autoflake) | One tool, sub-second on the whole codebase. Configure in `pyproject.toml` under `[tool.ruff]`. Enable rule sets `E,F,W,I,N,UP,B,SIM,RUF,PL` minimum. Use `ruff format` not black. |
| **pytest** | 9.0.3 | Test runner | Default. Configure `pytest.ini_options` in pyproject. Use `pytest-xdist` for parallel test runs once the suite grows. |
| **pytest-hypothesis** integration | (bundled in hypothesis 6.155.1) | Pytest plugin auto-enabled when `hypothesis` is installed | `@given(...)` decorator works inline with pytest test functions. No extra config. |
| **pre-commit** | 3.x | Git hook runner for ruff + pyright on each commit | Optional but cheap. Belt-and-braces enforcement of principle #5. |

**Deliberately NOT included as dev tools:** `black`, `flake8`, `isort`, `mypy`, `tox`, `poetry`. Ruff replaces the first four; pyright replaces mypy; uv + nox (if ever needed) replaces tox+poetry.

---

## Installation

```bash
# Bootstrap: install uv itself
# (Windows PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Create the project
cd C:\Users\omani\projects\berakah
uv init --python 3.12

# Core data / numerics
uv add polars duckdb pyarrow ccxt

# Type system & boundary validation
uv add pydantic phantom-types

# Logging & resilience
uv add structlog tenacity httpx

# Vault integration
uv add obsidiantools python-frontmatter PyYAML

# Numerics for validation metrics
uv add scipy numpy

# Operator-facing CLI
uv add rich

# Dev dependencies
uv add --dev pytest hypothesis pyright ruff pre-commit
```

The resulting `pyproject.toml` should pin Python: `requires-python = ">=3.12,<3.14"`.

Lockfile (`uv.lock`) is committed. CI runs `uv sync --frozen` to guarantee bit-identical environments.

---

## Look-Ahead as a Type Contract (HYP-02)

This is the load-bearing pattern. The constraint says: "Strategy modules expose a compile-time-verifiable contract such that look-ahead bias is unrepresentable." Here's the concrete encoding.

### Layer 1 — `NewType` to brand a timestamp

```python
from typing import NewType
from datetime import datetime

NowTs = NewType("NowTs", datetime)
# A NowTs is a datetime that the engine has certified as "the current
# decision time for this iteration." Strategies can only receive NowTs
# values from the engine, never construct them.
```

`NewType` is a zero-cost compile-time-only distinction — at runtime it's just a `datetime`. Pyright treats `datetime` and `NowTs` as different types: you cannot pass a plain `datetime` where `NowTs` is expected.

### Layer 2 — `phantom-types` to brand a bar window

```python
from phantom import Phantom
import polars as pl

class PointInTimeBars(pl.DataFrame, Phantom, predicate=is_point_in_time_safe):
    """A bars DataFrame guaranteed by the engine to contain only rows
    with timestamp < now_ts."""
    ...

def is_point_in_time_safe(df: pl.DataFrame) -> bool:
    # Verified at the engine boundary; never inside a strategy.
    return df.height > 0 and df["ts"].max() < df.attrs["now_ts"]
```

The engine performs the trim and the `PointInTimeBars.parse(df)` conversion once per bar. Strategies receive `PointInTimeBars` and cannot construct one themselves without going through `parse` (which runs the predicate at runtime as a tripwire).

### Layer 3 — `Protocol` for the strategy interface

```python
from typing import Protocol

class MeanReversionStrategy(Protocol):
    def signal(
        self,
        now_ts: NowTs,
        bars: PointInTimeBars,
        state: StrategyState,
    ) -> Signal: ...
```

The signature is the contract. Any strategy that compiles against this Protocol cannot, by construction, accept a wider bars dataframe. There is no parameter through which a future bar could enter.

### Layer 4 — `hypothesis` to adversarially verify the contract

```python
from hypothesis import given, strategies as st

@given(bars=arbitrary_bars(), now=arbitrary_timestamp())
def test_strategy_never_reads_future(bars: pl.DataFrame, now: datetime):
    pit_bars = engine.trim_to_point_in_time(bars, now)
    sig = my_strategy.signal(NowTs(now), pit_bars, initial_state())
    # Any value the strategy used must be derivable from bars where ts < now.
    # Verified by replaying the trace with the suffix removed and asserting
    # identical signal output.
    assert sig == my_strategy.signal(NowTs(now), engine.trim_to_point_in_time(bars[bars["ts"] < now], now), initial_state())
```

Property-based testing won't find a leak that's already prevented at the type level, but it will catch impure leaks via mutable global state, file reads, or accidentally captured closures over the full dataset.

The combination — Layer 1+2+3 makes leakage *unrepresentable at compile time* (principle #5), Layer 4 catches the impure-side-effect class of leakage that types can't see. This is exactly the negative-space coding the global CLAUDE.md asks for.

---

## Backtest Engine: Build, Don't Adopt

This is the most consequential decision. The recommendation is to **write a custom event-driven engine** (~600–1200 lines for Ring 1 scope) rather than adopt vectorbt, backtesting.py, backtrader, nautilus_trader, or zipline-reloaded.

### Comparison

| Approach | Lines of Code (Ring 1) | Look-Ahead Defense | Agent-Friendliness | Verdict |
|----------|------------------------|--------------------|--------------------|---------|
| **Custom event-driven** | ~800 | Owned end-to-end via the PIT type contract above | Maximal — types are the architecture, no library quirks to memorize | **WINNER** |
| `vectorbt` | ~200 | Vectorized; the framework's docs explicitly admit "off-by-one indexing errors occur easily" and rely on the user remembering to `.shift(1)`. Cannot be encoded in types. | Medium — its API is large and idiosyncratic, agents will hallucinate calls | Reject as primary |
| `backtesting.py` | ~400 | OHLC-on-bar-close convention; no type-level guarantee | Low — single-file, opinionated, no real Protocol layer | Reject |
| `backtrader` | ~400 | None — Python-2-era event system | Low — stale (last release 2023), heavy OO patterns Claude won't extend cleanly | Reject |
| `nautilus_trader` | ~400 | Production-grade event-driven, Rust core. Excellent. | Medium — heavyweight, opinionated, big surface area, optimized for live deployment not retail research | Defer to Ring 3 |
| `zipline-reloaded` | ~500 | Tied to pipeline of historical US equities; crypto support is bolt-on | Low — Quantopian-era abstractions | Reject |

**Winner: Custom event-driven.** Three reasons:

1. **HYP-02 is the entire point.** No third-party framework lets us define the look-ahead invariant at the *type* level. They all defend procedurally ("shift the signal," "use the right OHLC field," etc.). That violates principle #5 (hard constraints over loose logic). The whole rationale for picking Python over Rust was that we get a strong type system *plus* agent leverage — squandering it by adopting a framework that re-introduces runtime leakage risk is the worst-of-both.

2. **AI-agent friendliness (principle #3).** A custom engine of ~800 lines with strict Protocol-driven interfaces is something Claude can hold in working memory and extend correctly. vectorbt's API surface, by contrast, is large enough that the agent will hallucinate method calls. Repetition is a feature here.

3. **Ring 1 scope is small.** The engine needs: (a) bar iterator with timestamp trim, (b) strategy.signal() call site, (c) vol-target sizer, (d) fee model, (e) trade ledger writer, (f) regime-stratified Sharpe/drawdown calculator. That's ~6 modules. The cost of writing them is less than the cost of learning a framework's idiosyncrasies, *and* it doesn't accrue a dependency to be displaced in Ring 2/3 when execution friction modeling enters scope.

**When to re-evaluate:** When Ring 3 adds live trading, evaluate `nautilus_trader` for the execution layer. Its event-driven model and Rust core are production-grade. But for Ring 1's research-only scope, it's overkill and its API isn't agent-friendly.

---

## Statistics & Validation: scipy + custom, NOT quantstats/empyrical/pyfolio

| Library | Status | Verdict |
|---------|--------|---------|
| `pyfolio` | Dead (last meaningful release 2020) | Reject |
| `empyrical` | Dead (Quantopian-archived); `empyrical-reloaded` is a community fork with limited momentum | Reject (would have to pin a fork) |
| `quantstats` | Maintained, but pandas-only and assumes daily-returns Series | Reject as primary; possible escape hatch for tear-sheet generation |
| `scipy.stats` + custom polars functions | Maintained by SciPy core team; ~80 lines of code gives us Sharpe, drawdown, win rate, regime-stratified Sharpe, IS-vs-OOS t-test | **WINNER** |

Write the metrics in ~80 lines of polars + scipy. We need them computed against polars trade ledgers, partitioned by regime label, with the IS/OOS split enforced by the engine — that's not what quantstats does. The metrics themselves are arithmetic.

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `uv` | `poetry` | If publishing a library to PyPI with complex extras — Poetry's publish workflow is slightly smoother. Not relevant for Berakah (closed-source app). |
| `polars` | `pandas` 2.2+ | If integrating with a library that *only* speaks pandas (e.g., `quantstats` if we ever adopt it for tear-sheets). Use `polars.to_pandas()` at the boundary. |
| `duckdb` | `sqlite` with `arrow` extension | If single-writer constraint matters and dataset is < 10GB. DuckDB is strictly better for analytical reads. |
| `pyright` | `mypy 1.x` | If we hit a pyright bug that blocks. Mypy's Pydantic plugin is more battle-tested. Pyright now reads pydantic v2's stubs natively, so this is increasingly unlikely. |
| `structlog` | `loguru` | If the operator prefers minimal config over composability. Loguru's API is friendlier but harder to query post-hoc. |
| `ccxt` | `python-binance` + `coinbase-advanced-py` + `krakenex` | If a specific exchange's CCXT adapter drops a field we need (rare). Use as a per-exchange escape hatch behind a `Protocol`-typed adapter. |
| Custom event-driven engine | `nautilus_trader` | When Ring 3 adds live trading. Not for Ring 1. |
| Custom metrics in scipy | `quantstats` | When the operator wants a polished HTML tear-sheet to share. Run as a one-shot post-process on the trade ledger. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `vectorbt` / `vectorbt-pro` | Vectorized engine means look-ahead defense is procedural, not type-level. Library's own docs admit "off-by-one indexing errors occur easily." Violates principle #5. | Custom event-driven engine with PIT type contract |
| `backtrader` | Last release 2023; Python-2-era patterns; heavy OO; agent-hostile API surface | Custom event-driven engine |
| `zipline` / `zipline-reloaded` | Architected around Quantopian's daily-bar US-equity pipeline; crypto support is bolt-on; Pipeline DSL adds a second abstraction layer Claude doesn't need | Custom event-driven engine |
| `pyfolio` | Unmaintained since 2020; depends on dead empyrical | scipy + custom polars functions |
| `empyrical` (original Quantopian) | Unmaintained since 2020 | `scipy.stats` + custom polars metrics |
| `pandas` as primary | Single-threaded, weaker type story, ~10× slower than polars on grouped/rolling time-series ops | `polars`; convert to pandas only at the boundary of a pandas-only library |
| `pip` directly (without uv) | 10–100× slower; platform-specific lockfiles; no Python version management | `uv` |
| `poetry` | 10× slower than uv; PyPI publishing is its only remaining advantage; we're not publishing | `uv` |
| `pip-tools` | Platform-specific `requirements.txt`; manual workflow; uv does the same job in one command | `uv` |
| `mypy` (as primary) | 2–5× slower than pyright; 58% spec conformance vs pyright's 98%; not what the editor uses anyway | `pyright --strict` |
| `black` + `isort` + `flake8` | Three tools, slower, redundant with ruff | `ruff` (one tool, sub-second) |
| `loguru` (as primary) | Less queryable, less composable; harder to bind contextvars across async boundaries | `structlog` |
| `python-binance` / `coinbase-advanced-py` / `krakenex` (as primary) | Three separate libraries, three different schemas to normalize, three update cadences to track | `ccxt` (unified adapter) |
| `Backtesting.py` | Bar-close convention without type-level enforcement; small but agent-hostile API | Custom event-driven engine |
| `pandas-ta` / `ta-lib` | Pandas-only, look-ahead is a runtime concern, hard to type-strict | Compute the handful of indicators we need (RSI, Z-score on rolling mean) directly in polars expressions |
| `tox` | Replaced by `uv run` + a Makefile or `noxfile.py` if needed | `uv run pytest`, `uv run ruff check`, etc. |
| Any LLM-in-hot-path library (e.g., `langchain` agents inside the signal loop) | Explicitly out of scope per hard constraints | None — operator may use LLMs at the *meta* level (vault analysis, hypothesis generation) but not in the signal path |

---

## Stack Patterns by Variant

**If the engine needs cross-machine reproducibility (e.g., laptop ↔ cloud spot instance):**
- Same stack. `uv.lock` is cross-platform, polars/duckdb/pyarrow are wheels. Add a `.python-version` file (`3.12`) so `uv` provisions the same interpreter.
- No change required.

**If the dataset grows past laptop RAM (~20GB+ of bars across more pairs/timeframes):**
- DuckDB already handles this via streaming Parquet scans — no migration. Polars lazy mode pushes filters down.
- Switch the dataframe hot path to `polars.LazyFrame` exclusively if you find yourself materializing accidentally.

**If we add a second strategy family in Ring 4 (not in scope for Ring 1):**
- Add a `StrategyFamily` enum and a `Protocol` per family. The engine core stays unchanged because the look-ahead contract is defined per-strategy, not per-family.

**If the operator wants a static-site report viewer later:**
- The reports are already Markdown in the vault. Obsidian Publish or `mkdocs` reads them as-is. No code change.

---

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `python==3.12.*` | All other packages listed | Pin in `pyproject.toml`'s `requires-python`. Avoid 3.14 until Pydantic full support stabilizes (started in 2.12). |
| `polars==1.41.*` | `pyarrow==24.*`, `duckdb==1.5.*` | All Arrow-backed; zero-copy interop works across all three. Don't mix major versions of polars across the lockfile. |
| `duckdb==1.5.3` | `polars>=1.30`, `pyarrow>=20` | DuckDB's polars relation feature requires polars 1.30+. |
| `pydantic==2.13.*` | `pyright>=1.1.380` | Pyright reads Pydantic's static type emission natively from v2.10+; older pyrights had spurious errors. |
| `pyright==1.1.410` | `python>=3.7` | The PyPI wrapper bundles the Node binary; no separate npm install. |
| `ruff==0.15.*` | Standalone — no Python-version coupling at the user level | Configure via `pyproject.toml` `[tool.ruff]`. |
| `hypothesis==6.155.*` | `pytest>=8` | Pytest plugin is bundled. No separate `pytest-hypothesis` install. |
| `ccxt==4.5.56` | `python>=3.8` | Wheels exist for all platforms. Version updates ~weekly; pin and re-bump quarterly. |
| `obsidiantools==0.11.0` | `python>=3.9,<3.12` officially, **but** works on 3.12 per community reports | This is the one yellow flag. If 3.12 install fails, use 3.11 as a fallback, or migrate to `python-frontmatter` + `markdown-it-py` for vault parsing (more code, full type control). |
| `phantom-types==3.0.2` | `python>=3.9` through `3.13` | Pydantic integration is native. |
| `structlog==25.5.0` | `python>=3.8` through `3.14` | Stdlib `logging` interop is built-in. |
| `python-frontmatter==1.3.0` | `python>=3.6` | `PyYAML` is a transitive dep. |

---

## Confidence Notes

| Recommendation | Confidence | Why |
|----------------|------------|-----|
| Python 3.12, uv, polars, duckdb, ccxt, pyarrow | HIGH | Versions verified on PyPI June 2026. These are the 2026 consensus picks across the entire data/quant Python community. |
| Pydantic v2.13 + phantom-types + NewType + Protocol for HYP-02 | HIGH on pattern, MEDIUM on which library carries the most weight | The pattern (Parse-Don't-Validate + brand types + Protocol contracts) is correct and well-documented. Whether phantom-types or hand-rolled NewType subclassing is cleaner is a taste call we'll make in implementation. |
| Custom event-driven backtest engine (reject vectorbt/backtrader/zipline) | MEDIUM-HIGH | The reasoning is sound — the type-contract requirement is genuinely not solvable with vectorbt without abandoning the principle. But this is a build decision the operator should sanity-check before committing. If the operator prefers a 1–2 week head-start, vectorbt is the least-bad adoption with a wrapper. |
| pyright over mypy | HIGH | Spec conformance and speed numbers are clear; pyright is what Pylance uses; no compelling reason to choose mypy for a greenfield project. |
| structlog over loguru | MEDIUM-HIGH | Both work. structlog is the better fit for "logs are a queryable record of every event in the run." Loguru is the better fit for "logs are operator-facing tail output." Berakah is the former. |
| scipy + custom metrics over quantstats/empyrical | HIGH | empyrical and pyfolio are dead. quantstats is pandas-only and assumes daily Series. ~80 lines of polars+scipy is the right answer. |
| ccxt as ingestion library | HIGH | The only unified Tier-1 multi-exchange adapter library in active development. Alternative is 3× per-exchange libraries — strictly more surface. |
| obsidiantools + python-frontmatter for vault | MEDIUM | obsidiantools is the only library that understands Obsidian wikilinks. Its 3.12 compatibility is the one yellow flag. python-frontmatter is rock-solid for the write side. |
| ruff + pytest + hypothesis | HIGH | 2026 default dev stack. No real alternatives to consider. |

---

## Sources

### Primary (PyPI / official — HIGH confidence)
- [ccxt 4.5.56 — PyPI](https://pypi.org/project/ccxt/) — verified May 27, 2026 release
- [polars 1.41.2 — PyPI](https://pypi.org/project/polars/) — verified May 29, 2026 release
- [duckdb 1.5.3 — PyPI](https://pypi.org/project/duckdb/) — verified May 20, 2026 release
- [uv 0.11.19 — PyPI](https://pypi.org/project/uv/) — verified June 3, 2026 release
- [pydantic 2.13.4 — PyPI](https://pypi.org/project/pydantic/) — verified May 6, 2026 release
- [ruff 0.15.16 — PyPI](https://pypi.org/project/ruff/) — verified June 4, 2026 release
- [hypothesis 6.155.1 — PyPI](https://pypi.org/project/hypothesis/) — verified May 29, 2026 release
- [pyright 1.1.410 — GitHub Releases](https://github.com/microsoft/pyright/releases) — verified late May 2026 release
- [pytest 9.0.3 — PyPI](https://pypi.org/project/pytest/) — verified April 7, 2026 release
- [structlog 25.5.0 — PyPI](https://pypi.org/project/structlog/) — verified October 2025 release
- [pyarrow 24.0.0 — PyPI](https://pypi.org/project/pyarrow/) — verified April 21, 2026 release
- [obsidiantools 0.11.0 — PyPI](https://pypi.org/project/obsidiantools/) — verified July 8, 2025 release
- [python-frontmatter 1.3.0 — PyPI](https://pypi.org/project/python-frontmatter/) — verified May 20, 2026 release
- [phantom-types 3.0.2 — PyPI](https://pypi.org/project/phantom-types/) — verified October 27, 2024 release

### Secondary (verified analyses — MEDIUM-HIGH confidence)
- [Python Package Managers 2026 — Scopir](https://scopir.com/posts/best-python-package-managers-2026/) — uv adoption and benchmark data
- [Python Dependency Management in 2026 — Cuttlesoft](https://cuttlesoft.com/blog/2026/01/27/python-dependency-management-in-2026/)
- [uv vs pip vs Poetry — danilchenko.dev](https://www.danilchenko.dev/posts/uv-vs-pip-vs-poetry/)
- [Polars vs Pandas in 2026 — danilchenko.dev](https://www.danilchenko.dev/posts/polars-vs-pandas/)
- [Mastering Python Data Analysis 2026 — Nerd Level Tech](https://nerdleveltech.com/mastering-python-data-analysis-in-2026-from-pandas-to-polars)
- [Python Project Setup 2026 — KDnuggets](https://www.kdnuggets.com/python-project-setup-2026-uv-ruff-ty-polars)
- [DuckDB 2026 — Open Source For You](https://www.opensourceforu.com/2026/02/duckdb-speeding-up-in-process-analytics-with-python/)
- [Trading Data Analytics with DuckDB + Parquet — Quant Factory / Medium](https://medium.com/quant-factory/trading-data-analytics-part-1-first-steps-with-duckdb-and-parquet-files-f74fd2869372)
- [The Python Backtesting Landscape 2026](https://python.financial/) — confirms vectorbt/backtrader/nautilus comparison
- [NautilusTrader docs](https://nautilustrader.io/docs/latest/concepts/backtesting/) — confirms event-driven architecture
- [Vector vs Event-Based Backtesting — Interactive Brokers Campus](https://www.interactivebrokers.com/campus/ibkr-quant-news/a-practical-breakdown-of-vector-based-vs-event-based-backtesting/) — confirms look-ahead-bias-by-construction in vectorized engines
- [mypy vs Pyright vs ty 2026 — danilchenko.dev](https://www.danilchenko.dev/posts/ty-vs-mypy-vs-pyright/) — conformance and speed data
- [Python Logging Libraries 2026 — Dash0](https://www.dash0.com/guides/python-logging-libraries) — structlog vs loguru comparison
- [Python Logging Best Practices 2026 — tutorials.technology](https://tutorials.technology/tutorials/python-logging-best-practices-structlog-loguru-2026.html)
- [Ruff 2026 — tutorials.technology](https://tutorials.technology/tutorials/ruff-python-linting-2026.html)
- [Pydantic v2.12 release notes](https://pydantic.dev/articles/pydantic-v2-12-release) — 3.14 support timeline
- [phantom-types docs](https://phantom-types.readthedocs.io/en/3.0.0/pages/types.html) — Parse-Don't-Validate pattern
- [PEP 544 — Protocols](https://peps.python.org/pep-0544/) — structural subtyping
- [obsidiantools — GitHub](https://github.com/mfarragher/obsidiantools) and [Front Matter docs](https://deepwiki.com/mfarragher/obsidiantools/3.3-front-matter-and-tags)
- [QuantStats vs alternatives — TradingBrokers](https://tradingbrokers.com/pyfolio-alternatives/) — confirms pyfolio/empyrical are dead
- [CCXT Python Tutorial 2026](https://blog.adnansiddiqi.me/getting-started-with-ccxt-crypto-exchange-library-and-python/) — confirms OHLCV pattern, rate-limit handling

---

*Stack research for: AI-augmented systematic trading research engine (Berakah Ring 1)*
*Researched: 2026-06-04*
