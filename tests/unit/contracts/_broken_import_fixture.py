"""DELIBERATELY BROKEN IMPORT FIXTURE — for testing import-linter rejection.

This file is named with a leading underscore so pytest does NOT collect it.
Test code (test_import_linter_contracts.py) copies its content into
a temporary file under berakah/strategy/ to demonstrate that import-linter
rejects the violation. The fixture is reverted after the test.

Per CONFIG-02: this is the deliberate-broken-test-commit demonstration.
"""

# The illegal import — strategy MUST NOT import data
from berakah import data as _data  # this line is the violation

_ = _data  # silence "unused import" if a strict linter wants it
