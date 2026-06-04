"""Tests for berakah.types.strategy — the Strategy Protocol.

Per ARCHITECTURE.md §2.2: Strategy is a structural type. Any class with the right shape
(name, params, on_bar method) satisfies it. The signature
`on_bar(snap: BarSnapshot[NowTs]) -> tuple[OrderIntent, ...]` is the contract that makes
look-ahead unrepresentable.

Discipline: TYPE_CHECKING + pytest.importorskip.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from berakah.types.bars import BarSnapshot  # noqa: F401  # pyright: ignore[reportMissingImports, reportUnusedImport]
    from berakah.types.orders import OrderIntent  # noqa: F401  # pyright: ignore[reportMissingImports, reportUnusedImport]
    from berakah.types.strategy import Strategy  # noqa: F401  # pyright: ignore[reportMissingImports, reportUnusedImport]
    from berakah.types.time import NowTs  # noqa: F401  # pyright: ignore[reportMissingImports, reportUnusedImport]


def test_strategy_protocol_exists() -> None:
    """`from berakah.types.strategy import Strategy` succeeds."""
    strategy_mod = pytest.importorskip("berakah.types.strategy")
    assert hasattr(strategy_mod, "Strategy")


def test_strategy_protocol_has_on_bar() -> None:
    """The Strategy Protocol declares the on_bar method."""
    strategy_mod = pytest.importorskip("berakah.types.strategy")
    # Protocols expose their declared members via __protocol_attrs__ (Python 3.12+).
    # Fall back to dir() if the attribute name differs in this Python version.
    if hasattr(strategy_mod.Strategy, "__protocol_attrs__"):
        attrs = strategy_mod.Strategy.__protocol_attrs__
        assert "on_bar" in attrs
    else:
        assert "on_bar" in dir(strategy_mod.Strategy)


def test_concrete_class_satisfies_protocol() -> None:
    """A class with name, params, on_bar structurally satisfies Strategy."""
    strategy_mod = pytest.importorskip("berakah.types.strategy")
    pytest.importorskip("berakah.types.bars")
    pytest.importorskip("berakah.types.orders")
    pytest.importorskip("berakah.types.time")

    class _ConformingStrategy:
        name: str = "test_strategy"
        params: object = object()

        def on_bar(self, snap: object) -> tuple[object, ...]:
            return ()

    instance = _ConformingStrategy()
    # runtime_checkable Protocol supports isinstance for structural conformance.
    assert isinstance(instance, strategy_mod.Strategy)


def test_class_missing_on_bar_does_not_satisfy() -> None:
    """A class without on_bar fails the structural isinstance check."""
    strategy_mod = pytest.importorskip("berakah.types.strategy")

    class _IncompleteStrategy:
        name: str = "incomplete"
        params: object = object()
        # No on_bar method.

    instance = _IncompleteStrategy()
    assert not isinstance(instance, strategy_mod.Strategy)
