"""Time NewTypes branding datetime to encode 'this timestamp has been engine-verified'.

Per HYP-02 and ARCHITECTURE.md §2.1:
- `Timestamp`: any UTC tz-aware datetime; the base brand for all engine timestamps.
- `BarCloseTs`: a Timestamp known to be a bar's close (the moment the bar finalized).
- `NowTs`: a Timestamp the ENGINE has certified as 'the current decision time' for one
  iteration of the backtest loop. Strategies receive NowTs values from the engine and
  cannot construct them — this is the load-bearing brand that makes look-ahead
  unrepresentable.

Per Pitfall 24 (UTC discipline): all timestamps are UTC tz-aware. Naive datetimes
are forbidden by convention (enforced at engine boundary in Phase 3).
"""

from __future__ import annotations

from datetime import datetime
from typing import NewType

Timestamp = NewType("Timestamp", datetime)
BarCloseTs = NewType("BarCloseTs", Timestamp)
NowTs = NewType("NowTs", Timestamp)

__all__ = ["BarCloseTs", "NowTs", "Timestamp"]
