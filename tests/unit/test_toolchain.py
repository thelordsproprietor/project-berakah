"""Toolchain smoke test: every Phase 1 dependency must be importable.

Defends against: silent dependency drift, Python version mismatches.
If this test fails (either as an ImportError at collection time or as an
assertion failure at run time), `uv sync --frozen` produced an unexpected
environment.

Pattern: imports are at module-top so an ImportError fails *collection* (the
loudest failure mode pytest offers). Each test then asserts an invariant on the
imported module — version, attribute presence, basic smoke value.
"""

from __future__ import annotations

import sys

# Core data stack (STACK.md §"Core Technologies")
import ccxt
import duckdb

# Vault read/write (obsidiantools is the yellow flag per STACK.md;
# imported here so missing-on-3.12 fails loudly at collection)
import frontmatter

# Dev / validation / logging
import hypothesis

# Type-contract stack (the load-bearing libraries for HYP-02)
import phantom
import polars
import pyarrow
import pydantic
import pydantic_settings
import scipy.stats
import structlog

# The Berakah package itself (PEP 561 + __init__.py marker)
import berakah


def test_python_is_3_12() -> None:
    """Pin: Python 3.12 per STACK.md / .python-version."""
    assert sys.version_info[:2] == (3, 12), (
        f"Expected Python 3.12, got {sys.version_info[:3]}. "
        f"Check .python-version and pyproject.toml requires-python."
    )


def test_core_data_stack_importable() -> None:
    """STACK.md core technologies must import cleanly and expose version metadata."""
    # Touch each module so the import isn't culled by a future linter pass;
    # this also guards against the package shape changing under us.
    assert hasattr(polars, "__version__")
    assert hasattr(duckdb, "__version__")
    assert hasattr(pyarrow, "__version__")
    assert hasattr(ccxt, "__version__")


def test_type_contract_stack_importable() -> None:
    """The load-bearing type-contract libraries for HYP-02."""
    # Pyright reads pydantic v2.10+ static type emission natively; pin 2.13.x.
    assert pydantic.VERSION.startswith("2.13"), f"Expected pydantic 2.13.x, got {pydantic.VERSION}."
    # phantom-types exposes a `Phantom` base class used by PointInTimeBars.
    assert hasattr(phantom, "Phantom")
    # pydantic-settings exposes BaseSettings (the BaseSettings half of v2).
    assert hasattr(pydantic_settings, "BaseSettings")


def test_dev_stack_importable() -> None:
    """Validation + logging + testing libraries."""
    assert hasattr(hypothesis, "given")
    assert hasattr(scipy.stats, "norm")
    assert hasattr(structlog, "get_logger")


def test_vault_libraries_importable() -> None:
    """Vault read/write stack. obsidiantools is the yellow flag — see STACK.md."""
    # python-frontmatter exposes the `load`/`loads`/`dumps` round-trip surface.
    assert hasattr(frontmatter, "loads")
    assert hasattr(frontmatter, "dumps")


def test_berakah_package_importable() -> None:
    """The empty `berakah` package itself must import (PEP 561 + __init__.py)."""
    # The package is intentionally empty in Phase 1 Plan 01 (Pitfall 23 defense).
    # All we verify is that the import succeeded and the module object exists.
    assert berakah is not None
