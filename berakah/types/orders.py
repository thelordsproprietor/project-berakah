"""Order/Fill/Trade types — immutable, type-strict.

Per ARCHITECTURE.md §1.2 and the principle of declarative/functional design (#4),
every record is a frozen dataclass with explicit types. No mutation.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from berakah.types.ids import FillId, OrderId, StrategyId
from berakah.types.time import BarCloseTs


class Side(StrEnum):
    BUY = "buy"
    SELL = "sell"


IntentKind = Literal["enter", "exit", "adjust"]


@dataclass(frozen=True, slots=True)
class OrderIntent:
    """A strategy's request: 'I want to enter/exit/adjust this position by this qty'.

    The engine (Phase 3) converts intents into orders, simulates fills at next-bar-open,
    and applies the fee model. Intents are pure; they do not know about fills.
    """

    order_id: OrderId
    strategy_id: StrategyId
    side: Side
    intent_kind: IntentKind
    target_qty: Decimal  # signed: positive = long, negative = short
    issued_at: BarCloseTs


@dataclass(frozen=True, slots=True)
class Fill:
    """A simulated fill produced by the engine in response to an OrderIntent."""

    fill_id: FillId
    order_id: OrderId
    side: Side
    filled_qty: Decimal
    fill_price: Decimal  # per-unit price after slippage
    fee: Decimal  # cash cost of the fill
    filled_at: BarCloseTs  # next bar's open close_ts (engine convention)


@dataclass(frozen=True, slots=True)
class Trade:
    """A complete round-trip: entry fill + exit fill + realized PnL."""

    strategy_id: StrategyId
    entry: Fill
    exit: Fill
    realized_pnl: Decimal


__all__ = ["Fill", "IntentKind", "OrderIntent", "Side", "Trade"]
