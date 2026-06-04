"""BacktestArtifact and ValidationReport — cross-phase handoff types.

Per the artifact-as-handoff pattern (ARCHITECTURE.md §9 Pattern 4):
- Phase 3 writes BacktestArtifact to disk (parquet + JSON).
- Phase 4 reads BacktestArtifact, computes ValidationReport.
- Phase 5 reads ValidationReport, renders Markdown into the vault.

These are Pydantic models (not plain dataclasses) because they cross the disk
boundary and need validation at I/O. `frozen=True, extra=forbid` — Principle 5.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from berakah.types.ids import HypothesisId, RunId, StrategyId
from berakah.types.metrics import RegimeStratifiedMetrics


class BacktestArtifact(BaseModel):
    """Phase 3 output. Pointer-with-metadata to the on-disk parquet ledger and
    summary JSON. The heavy data (per-bar equity, per-trade ledger) is in parquet;
    this model carries the key + summary."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: RunId
    strategy_id: StrategyId
    hypothesis_id: HypothesisId
    artifact_root: Path  # artifacts/runs/{run_id}/
    ledger_parquet: Path
    equity_parquet: Path
    summary_json: Path
    data_window_start: datetime  # UTC
    data_window_end: datetime  # UTC
    code_sha: str  # git SHA of strategy module
    data_sha: str  # SHA of data manifest
    config_sha: str  # SHA of BerakahConfig serialization
    created_ts: datetime  # UTC


class ValidationReport(BaseModel):
    """Phase 4 output. The decision artifact carrying the PROOF-01 verdict.
    Phase 5 renders this into Markdown for the vault."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: RunId
    hypothesis_id: HypothesisId
    strategy_id: StrategyId

    # Metrics — IS, OOS, final-validation-slice
    is_metrics: RegimeStratifiedMetrics
    oos_metrics: RegimeStratifiedMetrics
    final_slice_metrics: RegimeStratifiedMetrics | None  # None if slice not consumed yet

    # Overfitting defense (Phase 4)
    deflated_sharpe: float
    probability_backtest_overfit: float
    trial_budget_used: int
    trial_budget_total: int

    # PROOF-01 verdict
    proof_01_verdict: bool  # True = PASS, False = FAIL
    failed_gates: tuple[str, ...] = Field(default_factory=tuple)  # named gates if FAIL

    # Reproducibility
    code_sha: str
    data_sha: str
    config_sha: str
    annualization_factor: float  # sqrt(105_120) ≈ 324.2 per Pitfall 11
    created_ts: datetime  # UTC


__all__ = ["BacktestArtifact", "ValidationReport"]
