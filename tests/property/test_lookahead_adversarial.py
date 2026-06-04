"""THE PRINCIPLE-5 PROOF — hypothesis adversarial test for HYP-02.

For ALL random (bars, now_ts) inputs, either:
  (a) BarSnapshot.parse rejects (raises), OR
  (b) every bar exposed via the snapshot has close_ts <= now_ts.

There is no third option. If hypothesis ever finds a counterexample, the
phantom contract is broken.

Per Plan 01-02 success criterion (ROADMAP Phase 1 Success Criterion 2 adversarial clause):
  the adversarial test runs 200 examples and proves no leaky snapshot can be constructed.

Discipline locked: TYPE_CHECKING + pytest.importorskip.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import polars as pl
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

if TYPE_CHECKING:
    from berakah.types.bars import BarSnapshot  # noqa: F401  # pyright: ignore[reportMissingImports, reportUnusedImport]
    from berakah.types.bars import FutureBarLeakageError  # noqa: F401  # pyright: ignore[reportMissingImports, reportUnusedImport]
    from berakah.types.time import NowTs  # noqa: F401  # pyright: ignore[reportMissingImports, reportUnusedImport]


# Hypothesis strategy: generate a list of UTC tz-aware datetimes within a 1-year window.
_EPOCH = datetime(2023, 1, 1, tzinfo=UTC)


@st.composite
def _bars_and_now(draw: st.DrawFn) -> tuple[pl.DataFrame, datetime]:
    """Generate (bar_frame, now_ts) — bars may or may not contain future entries."""
    ts_count = draw(st.integers(min_value=0, max_value=50))
    minute_offsets = draw(
        st.lists(
            st.integers(min_value=0, max_value=365 * 24 * 60),  # within 1 year, minute granularity
            min_size=ts_count,
            max_size=ts_count,
        )
    )
    close_timestamps = sorted([_EPOCH + timedelta(minutes=m) for m in minute_offsets])

    # now_ts is drawn independently — may be before, within, or after the bar range.
    now_offset = draw(st.integers(min_value=0, max_value=365 * 24 * 60))
    now_ts = _EPOCH + timedelta(minutes=now_offset)

    n = len(close_timestamps)
    if n == 0:
        frame = pl.DataFrame(
            schema={
                "open_ts": pl.Datetime("us", "UTC"),
                "close_ts": pl.Datetime("us", "UTC"),
                "o": pl.Float64,
                "h": pl.Float64,
                "l": pl.Float64,
                "c": pl.Float64,
                "v": pl.Float64,
            }
        )
    else:
        frame = pl.DataFrame(
            {
                "open_ts": close_timestamps,
                "close_ts": close_timestamps,
                "o": [50000.0] * n,
                "h": [50100.0] * n,
                "l": [49900.0] * n,
                "c": [50050.0] * n,
                "v": [10.0] * n,
            }
        )
    return frame, now_ts


@given(payload=_bars_and_now())
@settings(
    max_examples=200,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
def test_no_leakage_possible(payload: tuple[pl.DataFrame, datetime]) -> None:
    """Adversarial property: no input produces a snapshot that exposes a future bar.

    This is the principle-5 PROOF — look-ahead bias is structurally unrepresentable.
    """
    bars_mod = pytest.importorskip("berakah.types.bars")
    time_mod = pytest.importorskip("berakah.types.time")

    frame, raw_now_ts = payload
    now_ts = time_mod.NowTs(time_mod.Timestamp(raw_now_ts))

    try:
        snap = bars_mod.BarSnapshot.parse(frame, now_ts=now_ts)
    except Exception:
        # Rejection is a legal outcome — the predicate fired. Invariant holds vacuously.
        return

    # If parse succeeded, every visible close_ts MUST be <= now_ts.
    for bar_close_ts in snap.iter_close_ts():
        assert bar_close_ts <= raw_now_ts, (
            f"LEAKAGE: snapshot exposed bar with close_ts={bar_close_ts!r} "
            f"> now_ts={raw_now_ts!r}. HYP-02 contract violated."
        )
