"""Tests for berakah.types.orders — Side enum, OrderIntent/Fill/Trade frozen dataclasses.

Per ARCHITECTURE.md §1.2 and Engineering Principle 4 (declarative/functional):
every record is a frozen dataclass with explicit types. No mutation.

Per Plan 01-02 acceptance criterion (Issue 7): orders.py must contain
≥ 3 occurrences of `frozen=True` (OrderIntent, Fill, Trade).

Discipline: TYPE_CHECKING + pytest.importorskip.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from berakah.types.orders import Fill  # noqa: F401  # pyright: ignore[reportMissingImports, reportUnusedImport]
    from berakah.types.orders import OrderIntent  # noqa: F401  # pyright: ignore[reportMissingImports, reportUnusedImport]
    from berakah.types.orders import Side  # noqa: F401  # pyright: ignore[reportMissingImports, reportUnusedImport]
    from berakah.types.orders import Trade  # noqa: F401  # pyright: ignore[reportMissingImports, reportUnusedImport]


def test_side_enum_has_buy_and_sell() -> None:
    """Side enum exposes BUY and SELL."""
    orders = pytest.importorskip("berakah.types.orders")
    assert orders.Side.BUY is not None
    assert orders.Side.SELL is not None
    members = {m.name for m in orders.Side}
    assert {"BUY", "SELL"} <= members


def test_order_intent_is_frozen() -> None:
    """Mutation of OrderIntent raises FrozenInstanceError."""
    orders = pytest.importorskip("berakah.types.orders")
    ids = pytest.importorskip("berakah.types.ids")
    time_mod = pytest.importorskip("berakah.types.time")

    issued_at = time_mod.BarCloseTs(time_mod.Timestamp(datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)))
    oi = orders.OrderIntent(
        order_id=ids.OrderId("ord_001"),
        strategy_id=ids.StrategyId("mr_zscore_v1"),
        side=orders.Side.BUY,
        intent_kind="enter",
        target_qty=Decimal("0.5"),
        issued_at=issued_at,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        oi.target_qty = Decimal("1.0")  # type: ignore[misc]


def test_order_intent_has_required_fields() -> None:
    """OrderIntent has order_id, strategy_id, side, intent_kind, target_qty, issued_at."""
    orders = pytest.importorskip("berakah.types.orders")
    field_names = {f.name for f in dataclasses.fields(orders.OrderIntent)}
    expected = {"order_id", "strategy_id", "side", "intent_kind", "target_qty", "issued_at"}
    assert expected <= field_names, f"Missing fields: {expected - field_names}"


def test_fill_is_frozen() -> None:
    """Mutation of Fill raises FrozenInstanceError."""
    orders = pytest.importorskip("berakah.types.orders")
    ids = pytest.importorskip("berakah.types.ids")
    time_mod = pytest.importorskip("berakah.types.time")

    filled_at = time_mod.BarCloseTs(time_mod.Timestamp(datetime(2024, 1, 1, 12, 5, 0, tzinfo=UTC)))
    fill = orders.Fill(
        fill_id=ids.FillId("fill_001"),
        order_id=ids.OrderId("ord_001"),
        side=orders.Side.BUY,
        filled_qty=Decimal("0.5"),
        fill_price=Decimal("50000.0"),
        fee=Decimal("2.5"),
        filled_at=filled_at,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        fill.fee = Decimal("0")  # type: ignore[misc]


def test_trade_is_frozen() -> None:
    """Mutation of Trade raises FrozenInstanceError."""
    orders = pytest.importorskip("berakah.types.orders")
    ids = pytest.importorskip("berakah.types.ids")
    time_mod = pytest.importorskip("berakah.types.time")

    entry_at = time_mod.BarCloseTs(time_mod.Timestamp(datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)))
    exit_at = time_mod.BarCloseTs(time_mod.Timestamp(datetime(2024, 1, 1, 13, 0, 0, tzinfo=UTC)))
    entry = orders.Fill(
        fill_id=ids.FillId("fill_001"),
        order_id=ids.OrderId("ord_001"),
        side=orders.Side.BUY,
        filled_qty=Decimal("0.5"),
        fill_price=Decimal("50000.0"),
        fee=Decimal("2.5"),
        filled_at=entry_at,
    )
    exit_fill = orders.Fill(
        fill_id=ids.FillId("fill_002"),
        order_id=ids.OrderId("ord_002"),
        side=orders.Side.SELL,
        filled_qty=Decimal("0.5"),
        fill_price=Decimal("51000.0"),
        fee=Decimal("2.55"),
        filled_at=exit_at,
    )
    trade = orders.Trade(
        strategy_id=ids.StrategyId("mr_zscore_v1"),
        entry=entry,
        exit=exit_fill,
        realized_pnl=Decimal("494.95"),
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        trade.realized_pnl = Decimal("0")  # type: ignore[misc]
