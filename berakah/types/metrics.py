"""Metric types — output shapes from the validation engine (Phase 4).

Defined in Phase 1 because the artifact-as-handoff pattern (ARCHITECTURE.md §9 Pattern 4)
requires the BacktestArtifact (Phase 3 output) to carry these shapes through to
ValidationReport (Phase 4 output) and into the vault (Phase 5).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from berakah.types.regime import RegimeLabel


@dataclass(frozen=True, slots=True)
class MetricSet:
    """Standard metrics for a single (sub)sample of a backtest."""

    sharpe: float
    sharpe_ci_lower: float  # bootstrap 95% CI lower bound (Pitfall 27)
    sharpe_ci_upper: float  # bootstrap 95% CI upper bound
    sortino: float
    max_drawdown: float  # negative number; e.g., -0.18 = 18% drawdown
    win_rate: float  # 0.0 to 1.0
    trade_count: int
    total_pnl: Decimal


@dataclass(frozen=True, slots=True)
class RegimeStratifiedMetrics:
    """Per-regime metric breakdown — the PROOF-01 gate input."""

    aggregate: MetricSet
    by_regime: tuple[tuple[RegimeLabel, MetricSet], ...]


__all__ = ["MetricSet", "RegimeStratifiedMetrics"]
