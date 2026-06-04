"""Regime labels — 4 macro-defined frozen regimes per PROJECT.md and ARCHITECTURE.md §7.

Per Pitfall 7 (regime-specific overfit): these are MACRO-defined, never algorithmically
derived. No HMM, no data-fit boundaries. Dates live in this enum AND in the TOML
manifest used by berakah.data (Phase 2). The enum is the canonical Python-side reference.
"""

from __future__ import annotations

from enum import StrEnum


class RegimeLabel(StrEnum):
    BULL_2020_21 = "bull_2020_21"  # 2020-03-13 to 2021-11-10
    BEAR_2022 = "bear_2022"  # 2021-11-11 to 2022-12-31
    RECOVERY_2023 = "recovery_2023"  # 2023-01-01 to 2023-12-31
    ETF_ERA_2024_PLUS = "etf_era_2024_plus"  # 2024-01-01 onward


__all__ = ["RegimeLabel"]
