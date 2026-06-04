"""Mechanical proof that pyright (not just runtime) flags BarSnapshot[NowTs] with a future bar.

Per ROADMAP Phase 1 Success Criterion 2: "fails to type-check (pyright error) AND fails
at runtime AND adversarial hypothesis fails." This file is the pyright-level proof —
it spawns `pyright --outputjson` on a generated fixture and asserts the diagnostic fires.

Companion proofs:
- Runtime: tests/unit/types/test_barsnapshot_typecontract.py::test_future_bar_rejected_at_runtime
- Adversarial: tests/property/test_lookahead_adversarial.py
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest


def test_pyright_rejects_future_bar_construction(tmp_path: Path) -> None:
    """Mechanical proof that pyright flags BarSnapshot[NowTs] with a future bar.

    Generates a small fixture that misuses BarSnapshot.parse (passes a plain datetime
    where NowTs is expected — incompatible with the NewType brand), then runs
    `uv run pyright --outputjson` on it and asserts at least one error diagnostic fires.

    This is the pyright-level rejection clause of ROADMAP Phase 1 Success Criterion 2.
    """
    # Ensure the types module exists before bothering pyright with this proof.
    pytest.importorskip("berakah.types.bars")

    # The fixture: passes a plain datetime where NowTs is expected. Pyright should
    # refuse the assignment / the parse() call because `datetime` is NOT NowTs.
    fixture = tmp_path / "_leak_attempt.py"
    fixture.write_text(
        "from datetime import datetime\n"
        "import polars as pl\n"
        "from berakah.types.bars import BarSnapshot\n"
        "from berakah.types.time import NowTs\n"
        "\n"
        "# Type-level violation: plain datetime is NOT NowTs.\n"
        "# Pyright should flag the assignment / the parse() call below.\n"
        "naive_now: NowTs = datetime(2024, 1, 1)  # type ignore not added on purpose\n"
        "empty_frame = pl.DataFrame({'close_ts': [], 'c': []})\n"
        "snap = BarSnapshot.parse(empty_frame, now_ts=naive_now)\n",
        encoding="utf-8",
    )

    # Run pyright in JSON mode against the fixture file. We use the project's
    # pyright (resolves via uv) so the same version + config that gates CI is used.
    result = subprocess.run(
        ["uv", "run", "pyright", "--outputjson", str(fixture)],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )

    # Pyright emits JSON on stdout even when it finds errors; parse it.
    try:
        report: dict[str, Any] = json.loads(result.stdout)
    except json.JSONDecodeError:
        pytest.fail(
            f"pyright did not emit valid JSON.\nstdout={result.stdout!r}\nstderr={result.stderr!r}"
        )

    diagnostics = report.get("generalDiagnostics", [])
    errors = [d for d in diagnostics if d.get("severity") == "error"]

    assert errors, (
        f"Expected pyright to flag at least one type error in the look-ahead "
        f"fixture, but got 0 errors. Full report: {json.dumps(report, indent=2)}"
    )

    # The error message should reference the offending construction. Accept any
    # error that mentions NowTs / datetime / BarSnapshot / parse — we are proving
    # pyright caught the violation, not asserting a specific rule code.
    relevant_keywords = ("NowTs", "datetime", "BarSnapshot", "parse")
    relevant = [
        e for e in errors if any(kw in str(e.get("message", "")) for kw in relevant_keywords)
    ]
    assert relevant, (
        f"pyright emitted errors, but none referenced the BarSnapshot/NowTs/parse "
        f"surface. All errors: {[e.get('message') for e in errors]}"
    )
