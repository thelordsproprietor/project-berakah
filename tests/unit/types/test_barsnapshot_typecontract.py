"""THE LOAD-BEARING TEST — BarSnapshot[NowTs] phantom-typed look-ahead contract.

Per ARCHITECTURE.md §2, STACK.md "Look-Ahead as a Type Contract", SYSTEM.md Diagram 5,
REQ HYP-02, ROADMAP Phase 1 Success Criterion 2:

  Pyright (compile-time) + Phantom.parse (runtime) + hypothesis (adversarial) together
  must make look-ahead bias UNREPRESENTABLE — not just policed in code review.

This file is the RUNTIME proof. Companion files:
  - tests/property/test_lookahead_adversarial.py — the adversarial hypothesis proof.
  - tests/property/test_barsnapshot_pyright_rejects.py — the mechanical pyright proof
    (added in Task 1.02.2 alongside the implementation).

Discipline locked: TYPE_CHECKING + pytest.importorskip in every test body.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import polars as pl
import pytest

if TYPE_CHECKING:
    from berakah.types.bars import BarSnapshot  # noqa: F401  # pyright: ignore[reportMissingImports, reportUnusedImport]
    from berakah.types.bars import FutureBarLeakageError  # noqa: F401  # pyright: ignore[reportMissingImports, reportUnusedImport]
    from berakah.types.time import NowTs  # noqa: F401  # pyright: ignore[reportMissingImports, reportUnusedImport]


def _utc(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    """Construct a UTC tz-aware datetime — convenience for test fixtures."""
    return datetime(year, month, day, hour, minute, 0, tzinfo=UTC)


def _build_bar_frame(close_timestamps: list[datetime]) -> pl.DataFrame:
    """Build a minimal polars frame matching the Bars schema (open_ts, close_ts, o, h, l, c, v).

    Polars-only — no pandas — per ARCHITECTURE.md §2.4 and STACK.md.
    """
    n = len(close_timestamps)
    return pl.DataFrame(
        {
            "open_ts": close_timestamps,  # simplification: open == close for fixtures
            "close_ts": close_timestamps,
            "o": [50000.0 + i for i in range(n)],
            "h": [50100.0 + i for i in range(n)],
            "l": [49900.0 + i for i in range(n)],
            "c": [50050.0 + i for i in range(n)],
            "v": [10.0 + i for i in range(n)],
        }
    )


def test_barsnapshot_is_generic_in_t_now() -> None:
    """`BarSnapshot[NowTs]` is a valid type expression — BarSnapshot is Generic in T_Now."""
    bars_mod = pytest.importorskip("berakah.types.bars")
    time_mod = pytest.importorskip("berakah.types.time")
    # If BarSnapshot is properly Generic, BarSnapshot[NowTs] should not raise.
    snapshot_type = bars_mod.BarSnapshot[time_mod.NowTs]
    assert snapshot_type is not None


def test_barsnapshot_is_frozen() -> None:
    """Mutation of BarSnapshot raises FrozenInstanceError."""
    bars_mod = pytest.importorskip("berakah.types.bars")
    time_mod = pytest.importorskip("berakah.types.time")

    now_ts = time_mod.NowTs(time_mod.Timestamp(_utc(2024, 1, 1, 12, 0)))
    frame = _build_bar_frame([_utc(2024, 1, 1, 11, 0), _utc(2024, 1, 1, 11, 30)])
    snap = bars_mod.BarSnapshot.parse(frame, now_ts=now_ts)
    with pytest.raises(dataclasses.FrozenInstanceError):
        snap.now_ts = time_mod.NowTs(  # type: ignore[misc]
            time_mod.Timestamp(_utc(2024, 1, 2, 0, 0))
        )


def test_future_bar_rejected_at_runtime() -> None:
    """THE LOAD-BEARING ASSERTION — Phantom.parse refuses a frame with close_ts > now_ts.

    The runtime tripwire backing HYP-02: even if the type system were bypassed somehow,
    .parse() raises at the boundary. Pitfall 1 + Pitfall 2 defense.
    """
    bars_mod = pytest.importorskip("berakah.types.bars")
    time_mod = pytest.importorskip("berakah.types.time")

    now_ts_dt = _utc(2024, 1, 1, 12, 0)
    now_ts = time_mod.NowTs(time_mod.Timestamp(now_ts_dt))

    # The frame contains a bar at 12:30 — strictly after now_ts. THIS IS A LEAK ATTEMPT.
    leaky_frame = _build_bar_frame(
        [
            _utc(2024, 1, 1, 11, 0),
            _utc(2024, 1, 1, 11, 30),
            _utc(2024, 1, 1, 12, 30),  # FUTURE: 30 minutes after now_ts
        ]
    )

    with pytest.raises(Exception) as exc_info:
        bars_mod.BarSnapshot.parse(leaky_frame, now_ts=now_ts)

    # The error message must reference the leak — "close_ts", "now_ts", or "future".
    err_msg = str(exc_info.value).lower()
    assert any(keyword in err_msg for keyword in ("close_ts", "now_ts", "future", "leak")), (
        f"Exception did not reference the leakage surface. Message: {exc_info.value!r}"
    )


def test_future_bar_rejection_raises_specific_error_type() -> None:
    """The rejection raises FutureBarLeakageError (a subclass of ValueError)."""
    bars_mod = pytest.importorskip("berakah.types.bars")
    time_mod = pytest.importorskip("berakah.types.time")

    now_ts = time_mod.NowTs(time_mod.Timestamp(_utc(2024, 1, 1, 12, 0)))
    leaky_frame = _build_bar_frame(
        [_utc(2024, 1, 1, 11, 0), _utc(2024, 1, 1, 13, 0)]  # last bar is in the future
    )
    with pytest.raises(bars_mod.FutureBarLeakageError):
        bars_mod.BarSnapshot.parse(leaky_frame, now_ts=now_ts)


def test_legal_construction_succeeds() -> None:
    """Frame where all close_ts <= now_ts — parse succeeds, .now_ts is preserved."""
    bars_mod = pytest.importorskip("berakah.types.bars")
    time_mod = pytest.importorskip("berakah.types.time")

    now_ts_dt = _utc(2024, 1, 1, 12, 0)
    now_ts = time_mod.NowTs(time_mod.Timestamp(now_ts_dt))
    safe_frame = _build_bar_frame(
        [_utc(2024, 1, 1, 11, 0), _utc(2024, 1, 1, 11, 30), now_ts_dt]
        # last bar's close_ts == now_ts; boundary inclusive (close_ts <= now_ts).
    )
    snap = bars_mod.BarSnapshot.parse(safe_frame, now_ts=now_ts)
    assert snap.now_ts == now_ts


def test_legal_empty_frame_succeeds() -> None:
    """Empty frame is a legal snapshot — it exposes no bars."""
    bars_mod = pytest.importorskip("berakah.types.bars")
    time_mod = pytest.importorskip("berakah.types.time")

    now_ts = time_mod.NowTs(time_mod.Timestamp(_utc(2024, 1, 1, 12, 0)))
    empty_frame = _build_bar_frame([])
    snap = bars_mod.BarSnapshot.parse(empty_frame, now_ts=now_ts)
    assert snap.height() == 0


def test_barsnapshot_has_no_method_returning_full_frame() -> None:
    """No public method exposes the underlying frame raw. Critical to HYP-02."""
    bars_mod = pytest.importorskip("berakah.types.bars")
    time_mod = pytest.importorskip("berakah.types.time")

    now_ts = time_mod.NowTs(time_mod.Timestamp(_utc(2024, 1, 1, 12, 0)))
    frame = _build_bar_frame([_utc(2024, 1, 1, 11, 0)])
    snap = bars_mod.BarSnapshot.parse(frame, now_ts=now_ts)

    forbidden_names = {"to_dataframe", "as_frame", "full_history", "all_bars", "frame", "raw"}
    public_attrs = {name for name in dir(snap) if not name.startswith("_")}
    leaked = forbidden_names & public_attrs
    assert not leaked, (
        f"BarSnapshot exposes frame-leaking public method(s): {leaked}. "
        f"This defeats HYP-02; remove the method or rename it to start with '_'."
    )


def test_barsnapshot_last_n_returns_only_visible_bars() -> None:
    """last_n returns at most n bars — and they're all from the snapshot's window."""
    bars_mod = pytest.importorskip("berakah.types.bars")
    time_mod = pytest.importorskip("berakah.types.time")

    now_ts_dt = _utc(2024, 1, 1, 12, 0)
    now_ts = time_mod.NowTs(time_mod.Timestamp(now_ts_dt))
    # Build a frame with 5 bars, all <= now_ts.
    timestamps = [now_ts_dt - timedelta(hours=h) for h in range(5, 0, -1)]
    frame = _build_bar_frame(timestamps)
    snap = bars_mod.BarSnapshot.parse(frame, now_ts=now_ts)

    last_two = snap.last_n(2)
    assert last_two.height == 2


def test_barsnapshot_iter_close_ts_returns_tuple() -> None:
    """iter_close_ts returns an immutable tuple — used by adversarial tests."""
    bars_mod = pytest.importorskip("berakah.types.bars")
    time_mod = pytest.importorskip("berakah.types.time")

    now_ts = time_mod.NowTs(time_mod.Timestamp(_utc(2024, 1, 1, 12, 0)))
    timestamps = [_utc(2024, 1, 1, 10, 0), _utc(2024, 1, 1, 11, 0)]
    frame = _build_bar_frame(timestamps)
    snap = bars_mod.BarSnapshot.parse(frame, now_ts=now_ts)

    close_ts_seq = snap.iter_close_ts()
    assert isinstance(close_ts_seq, tuple)
    assert len(close_ts_seq) == 2
