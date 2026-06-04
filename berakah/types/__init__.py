"""Public type surface for berakah.types.

Downstream modules import from `berakah.types` (this __init__), not from submodules
directly. This keeps the public contract one read away.
"""

from __future__ import annotations

from berakah.types.artifacts import BacktestArtifact, ValidationReport
from berakah.types.bars import Bars, BarSnapshot, FutureBarLeakageError
from berakah.types.ids import FillId, HypothesisId, OrderId, RunId, StrategyId
from berakah.types.metrics import MetricSet, RegimeStratifiedMetrics
from berakah.types.orders import Fill, IntentKind, OrderIntent, Side, Trade
from berakah.types.positions import EngineState, Equity, Position
from berakah.types.regime import RegimeLabel
from berakah.types.strategy import Strategy
from berakah.types.time import BarCloseTs, NowTs, Timestamp

__all__ = [
    # cross-phase artifacts
    "BacktestArtifact",
    # bars & time
    "BarCloseTs",
    "BarSnapshot",
    "Bars",
    # positions / equity / state
    "EngineState",
    "Equity",
    # orders / fills / trades
    "Fill",
    # ids
    "FillId",
    "FutureBarLeakageError",
    "HypothesisId",
    "IntentKind",
    # metrics
    "MetricSet",
    "NowTs",
    "OrderId",
    "OrderIntent",
    "Position",
    # regime
    "RegimeLabel",
    "RegimeStratifiedMetrics",
    "RunId",
    "Side",
    # strategy
    "Strategy",
    "StrategyId",
    "Timestamp",
    "Trade",
    "ValidationReport",
]
