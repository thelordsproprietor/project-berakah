"""Tests for berakah.types.regime — RegimeLabel enum (4 macro-defined frozen regimes).

Per ARCHITECTURE.md §7 and PROJECT.md: the 4 regimes are macro-defined (not HMM-derived).
Per PITFALLS.md Pitfall 7: data-fit regime detection is forbidden in Ring 1.

Discipline locked: TYPE_CHECKING import + pytest.importorskip in test body.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from berakah.types.regime import RegimeLabel  # noqa: F401  # pyright: ignore[reportMissingImports, reportUnusedImport]


def test_regime_label_has_four_values() -> None:
    """RegimeLabel enum must have exactly 4 macro-defined members."""
    regime = pytest.importorskip("berakah.types.regime")
    members = list(regime.RegimeLabel)
    assert len(members) == 4, (
        f"RegimeLabel must have exactly 4 macro-defined regimes; got {len(members)}: {members}"
    )


def test_regime_labels_named_correctly() -> None:
    """Members are exactly BULL_2020_21, BEAR_2022, RECOVERY_2023, ETF_ERA_2024_PLUS."""
    regime = pytest.importorskip("berakah.types.regime")
    expected = {"BULL_2020_21", "BEAR_2022", "RECOVERY_2023", "ETF_ERA_2024_PLUS"}
    actual = {member.name for member in regime.RegimeLabel}
    assert actual == expected, f"Expected {expected}, got {actual}"


def test_regime_label_is_frozen() -> None:
    """Enum members cannot be mutated — enums are intrinsically immutable in Python."""
    regime = pytest.importorskip("berakah.types.regime")
    bull = regime.RegimeLabel.BULL_2020_21
    # Attempting to set an attribute on an enum member raises AttributeError.
    with pytest.raises((AttributeError, TypeError)):
        bull.name = "MUTATED"  # type: ignore[misc]


def test_regime_label_is_str_enum() -> None:
    """RegimeLabel is a str-backed enum (each value is a string identifier)."""
    regime = pytest.importorskip("berakah.types.regime")
    bull = regime.RegimeLabel.BULL_2020_21
    assert isinstance(bull, str)
