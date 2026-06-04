"""Tests for import-linter contracts — CONFIG-02.

Per CONFIG-02: import-linter MUST reject any commit that introduces a forbidden
edge. The proof is to stage a deliberately broken import, invoke `lint-imports`,
assert non-zero exit, then revert.
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_FILE = Path(__file__).parent / "_broken_import_fixture.py"


def test_clean_repo_passes_lint_imports() -> None:
    """Sanity: with no contract violations, lint-imports exits 0."""
    result = subprocess.run(
        ["uv", "run", "lint-imports", "--config", "importlinter.cfg"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, (
        f"lint-imports failed on clean repo: stdout={result.stdout!r}, stderr={result.stderr!r}"
    )


@pytest.fixture
def staged_broken_import() -> Iterator[Path]:
    """Stage the broken-import fixture under berakah/strategy/ and yield its path.

    berakah/strategy/ and berakah/data/ exist as permanent empty packages (Plan 03
    ships them as infrastructure placeholders so import-linter contracts can be
    active from Phase 1). This fixture only adds a _violation.py file inside
    berakah/strategy/, runs the test, then removes the violation file.
    """
    strategy_dir = REPO_ROOT / "berakah" / "strategy"
    created_dir = not strategy_dir.exists()
    strategy_dir.mkdir(parents=True, exist_ok=True)

    # Create __init__.py if absent (should already exist from Plan 03's infrastructure)
    init_path = strategy_dir / "__init__.py"
    created_init = not init_path.exists()
    if created_init:
        init_path.write_text("", encoding="utf-8")

    # We also need a stub `berakah/data/__init__.py` so the broken import even
    # parses at lint-imports time (lint-imports does AST analysis, not runtime
    # import, but it does need the target package to be discoverable).
    data_dir = REPO_ROOT / "berakah" / "data"
    created_data_dir = not data_dir.exists()
    data_dir.mkdir(parents=True, exist_ok=True)
    data_init = data_dir / "__init__.py"
    created_data_init = not data_init.exists()
    if created_data_init:
        data_init.write_text("", encoding="utf-8")

    # Stage the fixture
    target = strategy_dir / "_violation.py"
    shutil.copyfile(FIXTURE_FILE, target)

    try:
        yield target
    finally:
        # Teardown: remove fixture, restore directory state. Permanent
        # infrastructure (berakah/strategy/__init__.py, berakah/data/__init__.py)
        # remains intact — only files we created during the fixture run are
        # cleaned up.
        target.unlink(missing_ok=True)
        if created_init:
            init_path.unlink(missing_ok=True)
        if created_data_init:
            data_init.unlink(missing_ok=True)
        if created_dir and strategy_dir.exists() and not any(strategy_dir.iterdir()):
            strategy_dir.rmdir()
        if created_data_dir and data_dir.exists() and not any(data_dir.iterdir()):
            data_dir.rmdir()


def test_broken_import_is_blocked(staged_broken_import: Path) -> None:
    """CONFIG-02: a deliberately broken commit demonstrates the block.

    Stages a file containing `from berakah import data` inside berakah/strategy/,
    runs lint-imports, asserts non-zero exit and that the failing-contract name
    appears in the output.
    """
    assert staged_broken_import.exists()

    result = subprocess.run(
        ["uv", "run", "lint-imports", "--config", "importlinter.cfg"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert result.returncode != 0, (
        f"lint-imports passed despite a strategy module importing data. "
        f"stdout={result.stdout!r}, stderr={result.stderr!r}"
    )

    combined = (result.stdout + "\n" + result.stderr).lower()
    # The output should mention the violated contract or the forbidden import
    assert "strategy" in combined and (
        "data" in combined or "forbidden" in combined or "broken" in combined
    ), (
        f"lint-imports failed but the output didn't reference the strategy/data "
        f"violation: stdout={result.stdout!r}, stderr={result.stderr!r}"
    )


def test_lint_imports_config_file_exists() -> None:
    cfg = REPO_ROOT / "importlinter.cfg"
    assert cfg.exists()
    content = cfg.read_text(encoding="utf-8")
    # Verify all 4 contracts are declared (types-purity may be commented out
    # pending Plan 01-02 landing berakah/types/ — the literal contract name
    # must still appear in the file for traceability)
    assert "importlinter:contract:dag" in content
    assert "importlinter:contract:strategy-sandbox" in content
    assert "importlinter:contract:types-purity" in content
    assert "importlinter:contract:config-purity" in content


def test_layered_contract_lists_all_layers() -> None:
    cfg = (REPO_ROOT / "importlinter.cfg").read_text(encoding="utf-8")
    # Every layer name per ARCHITECTURE.md §1.3 must appear somewhere in the file
    # (DAG contract layer list, or other contract source_modules / forbidden_modules)
    for layer in [
        "berakah.types",
        "berakah.config",
        "berakah.data",
        "berakah.strategy",
        "berakah.backtest",
        "berakah.validation",
        "berakah.vault",
        "berakah.cli",
    ]:
        assert layer in cfg, f"Layer {layer} missing from importlinter.cfg"
