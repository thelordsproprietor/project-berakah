"""Tests for berakah.types.time — NewType timestamps (Timestamp, BarCloseTs, NowTs).

Per the LOCKED TYPE_CHECKING + pytest.importorskip discipline (Plan 01-02 checker Issue 4):
- berakah.types.* imports at module level live under `if TYPE_CHECKING:` (pyright only).
- Inside each test body, `pytest.importorskip(...)` gracefully skips on missing modules.

This file defines what "time NewTypes work" means before Task 1.02.2 implements them.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    # Compile-time-only: pyright resolves these for type info; at runtime they don't execute.
    # Pyright ignores protect the RED-phase commit before Task 1.02.2 implements the modules.
    from berakah.types.time import BarCloseTs  # noqa: F401  # pyright: ignore[reportMissingImports, reportUnusedImport]
    from berakah.types.time import NowTs  # noqa: F401  # pyright: ignore[reportMissingImports, reportUnusedImport]
    from berakah.types.time import Timestamp  # noqa: F401  # pyright: ignore[reportMissingImports, reportUnusedImport]


def test_timestamp_is_newtype() -> None:
    """`Timestamp` is a typing.NewType — compile-time distinction from datetime."""
    time_module = pytest.importorskip("berakah.types.time")
    timestamp = time_module.Timestamp
    # NewType objects expose __supertype__ pointing to the wrapped type.
    assert hasattr(timestamp, "__supertype__"), "Timestamp must be a typing.NewType"
    assert timestamp.__supertype__ is datetime


def test_now_ts_is_newtype() -> None:
    """`NowTs` is a typing.NewType — the engine-certified 'current decision time' brand."""
    time_module = pytest.importorskip("berakah.types.time")
    now_ts = time_module.NowTs
    assert hasattr(now_ts, "__supertype__"), "NowTs must be a typing.NewType"


def test_bar_close_ts_is_newtype() -> None:
    """`BarCloseTs` is a typing.NewType — branded as a bar's finalized close moment."""
    time_module = pytest.importorskip("berakah.types.time")
    bar_close_ts = time_module.BarCloseTs
    assert hasattr(bar_close_ts, "__supertype__"), "BarCloseTs must be a typing.NewType"


def test_now_ts_constructs_from_utc_datetime() -> None:
    """`NowTs(datetime)` works at runtime (NewType is erased) — produces a datetime."""
    time_module = pytest.importorskip("berakah.types.time")
    raw_dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    branded = time_module.NowTs(raw_dt)
    # NewType is a no-op at runtime; the value is identity-equal to the wrapped datetime.
    assert branded == raw_dt
    assert isinstance(branded, datetime)


def test_timestamp_constructs_from_utc_datetime() -> None:
    """`Timestamp(datetime)` works at runtime — preserves the datetime value."""
    time_module = pytest.importorskip("berakah.types.time")
    raw_dt = datetime(2023, 6, 15, 9, 30, 0, tzinfo=UTC)
    branded = time_module.Timestamp(raw_dt)
    assert branded == raw_dt
