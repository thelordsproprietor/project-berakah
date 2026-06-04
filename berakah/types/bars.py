"""Bars and BarSnapshot[NowTs] — the look-ahead type contract (HYP-02).

Per ARCHITECTURE.md §2 and STACK.md "Look-Ahead as a Type Contract":

`Bars` is a polars DataFrame view (typed by schema convention) carrying full
historical OHLCV. The data layer (Phase 2) produces it; the engine (Phase 3) consumes it.

`BarSnapshot[T_Now]` is a Generic frozen dataclass that the engine constructs once per
bar via `.parse()`. The Phantom-style predicate at the parse boundary rejects any
underlying frame containing a row with `close_ts > now_ts`. Strategies receive
BarSnapshot[NowTs] and have NO PUBLIC METHOD that exposes future bars.

This makes look-ahead bias structurally unrepresentable. See SYSTEM.md Diagram 5 and
PITFALLS.md Pitfalls 1, 2 for the failure modes this defends against.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import polars as pl

# NOTE: NowTs is imported by __init__.py from berakah.types.time; this module just
# declares the type parameter (PEP 695) bound to datetime. Strategy code uses
# BarSnapshot[NowTs] — the phantom-typed view.

# Bars is a polars DataFrame conforming to the documented schema:
#   open_ts: datetime UTC tz-aware
#   close_ts: datetime UTC tz-aware (the load-bearing column)
#   o, h, l, c, v: float64
# The schema is enforced at the data-layer boundary (Phase 2). We expose Bars
# as a type alias here so downstream modules can annotate against it.
type Bars = pl.DataFrame


class FutureBarLeakageError(ValueError):
    """Raised by BarSnapshot.parse when the underlying frame contains a bar
    with close_ts > now_ts. The runtime tripwire for HYP-02."""


@dataclass(frozen=True, slots=True)
class BarSnapshot[T_Now: datetime]:
    """Phantom-typed view of bars guaranteed to contain only rows with close_ts <= now_ts.

    Constructed ONLY via `BarSnapshot.parse(frame, now_ts=...)`. Direct construction
    with an unfiltered frame is forbidden by convention (the constructor accepts
    anything at runtime; `.parse()` is the predicate-checked entry point).

    Public methods do NOT expose the underlying frame. They expose windows and aggregates
    of the bars known to be at or before now_ts.
    """

    _frame: pl.DataFrame  # private; columns per Bars schema; close_ts <= now_ts for all rows
    now_ts: T_Now

    @classmethod
    def parse(cls, frame: pl.DataFrame, *, now_ts: T_Now) -> BarSnapshot[T_Now]:
        """Build a snapshot from a frame, enforcing close_ts <= now_ts.

        Raises FutureBarLeakageError if any row violates the predicate.
        Empty frame is permitted (returns a snapshot exposing no bars).
        """
        if frame.height > 0:
            if "close_ts" not in frame.columns:
                raise FutureBarLeakageError(
                    f"BarSnapshot.parse: frame missing required column 'close_ts'. "
                    f"Got columns: {frame.columns}"
                )
            max_close_ts = frame["close_ts"].max()
            # close_ts column dtype is Datetime; max_close_ts is a Python datetime
            if max_close_ts is not None and max_close_ts > now_ts:  # type: ignore[operator]
                raise FutureBarLeakageError(
                    f"BarSnapshot.parse refused leaky frame: max close_ts={max_close_ts} "
                    f"> now_ts={now_ts}. HYP-02 enforcement; see PITFALLS.md#pitfall-1."
                )
        return cls(_frame=frame, now_ts=now_ts)

    def last_n(self, n: int) -> pl.DataFrame:
        """Return the n most recent bars (all guaranteed close_ts <= now_ts)."""
        return self._frame.tail(n)

    def window(self, lookback_bars: int) -> pl.DataFrame:
        """Alias of last_n for strategy-author ergonomics."""
        return self.last_n(lookback_bars)

    def latest_close(self) -> float:
        """The most recent bar's close price."""
        if self._frame.height == 0:
            raise ValueError("BarSnapshot is empty; no latest close available.")
        return float(self._frame["c"][-1])

    def height(self) -> int:
        """Number of bars in the snapshot."""
        return self._frame.height

    def iter_close_ts(self) -> tuple[datetime, ...]:
        """Iterate close_ts values — used by adversarial tests to verify the invariant.

        NOTE: returns a tuple (immutable) of datetimes. Does NOT expose the frame.
        """
        if self._frame.height == 0:
            return ()
        return tuple(self._frame["close_ts"].to_list())

    # NOTE: There is intentionally NO method that:
    #   - returns the raw _frame
    #   - accepts a future ts as argument
    #   - reaches outside [0..now_ts] in time


__all__ = ["BarSnapshot", "Bars", "FutureBarLeakageError"]
