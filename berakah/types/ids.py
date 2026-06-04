"""Identifier NewTypes for cross-module typed references.

Per ARCHITECTURE.md §1.2, all IDs are str-backed NewTypes. NewType is a compile-time
distinction — at runtime each ID is a plain str.
"""

from __future__ import annotations

from typing import NewType

HypothesisId = NewType("HypothesisId", str)  # e.g., "HYP-001"
RunId = NewType("RunId", str)  # e.g., "r_2026-06-04T1430_a3f9"
StrategyId = NewType("StrategyId", str)  # e.g., "mr_zscore_v1"
OrderId = NewType("OrderId", str)
FillId = NewType("FillId", str)

__all__ = ["FillId", "HypothesisId", "OrderId", "RunId", "StrategyId"]
