"""Tests for berakah.types.ids — NewType identifiers (HypothesisId, RunId, etc).

Per the LOCKED TYPE_CHECKING + pytest.importorskip discipline:
- berakah.types.ids imports live under `if TYPE_CHECKING:` (pyright only).
- Test bodies use `pytest.importorskip(...)` for graceful runtime skip.

NewType IDs are str-backed compile-time distinctions; at runtime each is a plain str.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    # Compile-time-only imports; ignores protect the RED-phase commit.
    from berakah.types.ids import FillId  # noqa: F401  # pyright: ignore[reportMissingImports, reportUnusedImport]
    from berakah.types.ids import HypothesisId  # noqa: F401  # pyright: ignore[reportMissingImports, reportUnusedImport]
    from berakah.types.ids import OrderId  # noqa: F401  # pyright: ignore[reportMissingImports, reportUnusedImport]
    from berakah.types.ids import RunId  # noqa: F401  # pyright: ignore[reportMissingImports, reportUnusedImport]
    from berakah.types.ids import StrategyId  # noqa: F401  # pyright: ignore[reportMissingImports, reportUnusedImport]


def test_hypothesis_id_is_newtype() -> None:
    """`HypothesisId` is a typing.NewType wrapping str."""
    ids = pytest.importorskip("berakah.types.ids")
    assert hasattr(ids.HypothesisId, "__supertype__")
    assert ids.HypothesisId.__supertype__ is str


def test_run_id_is_newtype() -> None:
    """`RunId` is a typing.NewType wrapping str."""
    ids = pytest.importorskip("berakah.types.ids")
    assert hasattr(ids.RunId, "__supertype__")
    assert ids.RunId.__supertype__ is str


def test_strategy_id_is_newtype() -> None:
    """`StrategyId` is a typing.NewType wrapping str."""
    ids = pytest.importorskip("berakah.types.ids")
    assert hasattr(ids.StrategyId, "__supertype__")
    assert ids.StrategyId.__supertype__ is str


def test_order_id_is_newtype() -> None:
    """`OrderId` is a typing.NewType wrapping str."""
    ids = pytest.importorskip("berakah.types.ids")
    assert hasattr(ids.OrderId, "__supertype__")
    assert ids.OrderId.__supertype__ is str


def test_fill_id_is_newtype() -> None:
    """`FillId` is a typing.NewType wrapping str."""
    ids = pytest.importorskip("berakah.types.ids")
    assert hasattr(ids.FillId, "__supertype__")
    assert ids.FillId.__supertype__ is str


def test_ids_are_strings_at_runtime() -> None:
    """NewType is erased at runtime — every ID is a plain str."""
    ids = pytest.importorskip("berakah.types.ids")
    hyp = ids.HypothesisId("HYP-001")
    run = ids.RunId("r_2026-06-04T1430_a3f9")
    strat = ids.StrategyId("mr_zscore_v1")
    order = ids.OrderId("ord_001")
    fill = ids.FillId("fill_001")
    assert isinstance(hyp, str)
    assert isinstance(run, str)
    assert isinstance(strat, str)
    assert isinstance(order, str)
    assert isinstance(fill, str)
    assert hyp == "HYP-001"
