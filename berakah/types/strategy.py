"""Strategy Protocol — the structural contract every strategy module must satisfy.

Per ARCHITECTURE.md §2.2 and SYSTEM.md Diagram 5:

A strategy is a pure function from BarSnapshot[NowTs] to a tuple of OrderIntents.
It does NOT import berakah.data, berakah.vault, or berakah.backtest (enforced by
import-linter in Plan 03). It does NOT hold mutable state across calls.

The signature `on_bar(snap: BarSnapshot[NowTs]) -> tuple[OrderIntent, ...]` is THE
contract that makes look-ahead unrepresentable: there is no parameter through which
a future bar can enter, and no return path through which a strategy could request
one.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from berakah.types.bars import BarSnapshot
from berakah.types.orders import OrderIntent
from berakah.types.time import NowTs


@runtime_checkable
class Strategy(Protocol):
    name: str
    params: object  # frozen dataclass owned by each strategy module (Phase 3)

    def on_bar(self, snap: BarSnapshot[NowTs]) -> tuple[OrderIntent, ...]:
        """Single decision step. Pure function. No I/O. No mutable state."""
        ...


__all__ = ["Strategy"]
