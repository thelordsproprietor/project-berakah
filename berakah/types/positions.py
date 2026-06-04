"""Position / Equity / EngineState — frozen state types for the backtest engine.

Per ARCHITECTURE.md §4.1 and §4.2, the engine is a pure reducer over immutable
EngineState. Every step returns a new instance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from berakah.types.ids import StrategyId
from berakah.types.time import BarCloseTs


@dataclass(frozen=True, slots=True)
class Position:
    strategy_id: StrategyId
    qty: Decimal  # signed; 0 means flat
    avg_entry_price: Decimal  # 0 if flat
    opened_at: BarCloseTs | None  # None if flat


@dataclass(frozen=True, slots=True)
class Equity:
    cash: Decimal  # available cash
    position_value: Decimal  # mark-to-market value of open positions
    total: Decimal  # cash + position_value


@dataclass(frozen=True, slots=True)
class EngineState:
    """The complete state of the backtest engine at one bar.

    Pure reducer: engine.step(state, bar) -> new_state. No mutation.
    """

    equity: Equity
    positions: tuple[Position, ...] = field(default_factory=tuple)
    bar_index: int = 0
    as_of: BarCloseTs | None = None


__all__ = ["EngineState", "Equity", "Position"]
