"""Tests for BerakahConfig — CONFIG-01.

Per CONFIG-01: 'frozen=True, extra="forbid"; no scattered env-var reads in the code.'
Per Pitfall 11: annualization_factor MUST be sqrt(105_120) — not sqrt(252).
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from pydantic import ValidationError

import berakah
from berakah.config import BerakahConfig


def test_default_construction_succeeds() -> None:
    cfg = BerakahConfig()
    assert isinstance(cfg.project_root, Path)
    assert isinstance(cfg.data_root, Path)
    assert isinstance(cfg.artifacts_root, Path)
    assert isinstance(cfg.vault_root, Path)
    assert isinstance(cfg.regime_manifest_path, Path)
    assert isinstance(cfg.annualization_factor, float)
    assert isinstance(cfg.exchanges, tuple)
    assert isinstance(cfg.pairs, tuple)


def test_config_is_frozen() -> None:
    cfg = BerakahConfig()
    with pytest.raises(ValidationError):
        cfg.vault_root = Path("/tmp/different")  # type: ignore[misc]


def test_unknown_field_at_init_raises() -> None:
    with pytest.raises(ValidationError) as exc_info:
        BerakahConfig(unknown_field="x")  # type: ignore[call-arg]
    # Pydantic's error includes 'extra_forbidden' code
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()


def test_unknown_env_var_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    # An env var with the BERAKAH_ prefix but no matching field
    monkeypatch.setenv("BERAKAH_TOTALLY_BOGUS_FIELD", "x")
    with pytest.raises(ValidationError):
        BerakahConfig()


def test_env_var_overrides_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BERAKAH_TIMEFRAME_FLOOR", "15m")
    cfg = BerakahConfig()
    assert cfg.timeframe_floor == "15m"


def test_invalid_timeframe_floor_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BERAKAH_TIMEFRAME_FLOOR", "1s")
    with pytest.raises(ValidationError):
        BerakahConfig()


def test_annualization_factor_is_crypto_correct() -> None:
    """Pitfall 11: sqrt(365 * 24 * 12) = sqrt(105_120), NOT sqrt(252).

    This is the single source of truth for the project. Phase 4 imports from here.
    """
    cfg = BerakahConfig()
    expected = math.sqrt(365 * 24 * 12)
    assert cfg.annualization_factor == expected, (
        f"BerakahConfig.annualization_factor = {cfg.annualization_factor}; "
        f"expected sqrt(105_120) = {expected}. See PITFALLS.md#pitfall-11."
    )
    # Defense in depth: confirm it's NOT the equity default
    assert cfg.annualization_factor != math.sqrt(252), (
        "annualization_factor equals sqrt(252) — that is the EQUITY-MARKET constant. "
        "Crypto requires sqrt(105_120) per Pitfall 11. Reject."
    )


def test_tier1_exchanges_pinned() -> None:
    """Per PROJECT.md constraint: Tier-1 exchanges only (Binance, Coinbase, Kraken)."""
    cfg = BerakahConfig()
    assert set(cfg.exchanges) == {"kraken", "coinbase", "binance"}


def test_ring1_pairs_pinned() -> None:
    """Per PROJECT.md constraint: BTC + ETH spot only."""
    cfg = BerakahConfig()
    assert set(cfg.pairs) == {"BTC/USDT", "ETH/USDT"}


def test_default_paths_are_under_project_root() -> None:
    cfg = BerakahConfig()
    # data_root, artifacts_root, vault_root, regime_manifest_path are all under project_root
    assert str(cfg.data_root).startswith(str(cfg.project_root))
    assert str(cfg.artifacts_root).startswith(str(cfg.project_root))
    assert str(cfg.vault_root).startswith(str(cfg.project_root))


def test_no_direct_env_var_reads_in_codebase_outside_config() -> None:
    """CONFIG-01: 'no scattered env-var reads in the code'.

    This is a project-wide invariant. As of Phase 1, only berakah/ exists (no other
    modules). Once Phase 2+ ships, this test catches any module that bypasses
    BerakahConfig and reads env vars directly.
    """
    assert berakah.__file__ is not None
    berakah_root = Path(berakah.__file__).parent

    # Patterns that indicate direct env-var access; written as concatenated strings
    # to avoid this test file itself tripping the grep.
    forbidden_patterns = [
        "os" + ".getenv",
        "os" + ".environ.get",
        "os" + ".environ[",
    ]

    offenders: list[str] = []
    for py_file in berakah_root.rglob("*.py"):
        if py_file.name == "config.py":
            continue
        text = py_file.read_text(encoding="utf-8")
        for pattern in forbidden_patterns:
            if pattern in text:
                offenders.append(f"{py_file.relative_to(berakah_root)} ({pattern})")
                break

    assert not offenders, (
        f"CONFIG-01 violation: env-var access outside config.py: {offenders}. "
        f"All config must flow through BerakahConfig."
    )
