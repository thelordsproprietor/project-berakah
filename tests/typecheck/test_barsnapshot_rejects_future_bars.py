# NOTE: This file is documentation-as-code of patterns pyright would reject.
# It lives in tests/typecheck/ which is excluded from CI pyright runs and ruff.
# The mechanical proof — invoking pyright as a subprocess and asserting the
# diagnostic fires — lives in tests/property/test_barsnapshot_pyright_rejects.py.
# The runtime proof lives in tests/unit/types/test_barsnapshot_typecontract.py.
#
# Patterns pyright WOULD reject (illustrative):
#
# Pattern A: passing a plain datetime where NowTs is expected.
#   from datetime import datetime
#   from berakah.types.bars import BarSnapshot
#   from berakah.types.time import NowTs
#   import polars as pl
#
#   naive_now: NowTs = datetime(2024, 1, 1)   # pyright: error — datetime is not NowTs
#   empty: pl.DataFrame = pl.DataFrame({"close_ts": [], "c": []})
#   snap = BarSnapshot.parse(empty, now_ts=naive_now)
#
# Pattern B: calling private _frame attribute (reportPrivateUsage).
#   from berakah.types.bars import BarSnapshot
#   snap: BarSnapshot[NowTs] = ...
#   raw = snap._frame   # pyright: error reportPrivateUsage
#
# Pattern C: strategy.on_bar receiving an unbound bars frame.
#   from berakah.types.strategy import Strategy
#   def evil_strategy_call(s: Strategy, raw_bars: pl.DataFrame) -> None:
#       s.on_bar(raw_bars)  # pyright: error — DataFrame is not BarSnapshot[NowTs]
#
# These patterns ARE the violations; CI's pyright never reads this file.
# This file is reference material for the operator + AI agents.
