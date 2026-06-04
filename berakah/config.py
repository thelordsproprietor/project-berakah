"""BerakahConfig — the single frozen Pydantic Settings object for the project.

Per CONFIG-01: loaded once at CLI entry (Phase 6); frozen=True; extra="forbid";
no scattered env-var reads in the code.

Per ARCHITECTURE.md §7: this is the Phase 1 subset. Subsystem configs
(BacktestConfig, ValidationConfig) land in their respective phases.

Per Pitfall 11: annualization_factor lives here as the single source of truth.
Phase 4's validation engine imports cfg.annualization_factor — there is no other
constant named ANNUALIZATION_FACTOR_5MIN_CRYPTO anywhere in the codebase.

Per Pitfall 23: this config carries only what Phase 1 needs. Do not add
BacktestConfig / ValidationConfig fields prematurely.

Per Pitfall 28: this config does NOT expose `created_ts` or `frozen_ts` — those
are per-hypothesis frontmatter concerns, handled in Phase 5.
"""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, ValidationInfo, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_PREFIX = "BERAKAH_"


class BerakahConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix=_ENV_PREFIX,
        env_nested_delimiter="__",
        frozen=True,
        extra="forbid",
        case_sensitive=False,
    )

    @model_validator(mode="before")
    @classmethod
    def _reject_unknown_env_vars(cls, data: Any) -> Any:
        """Reject any BERAKAH_-prefixed env var that does not map to a declared field.

        Per CONFIG-01: "unknown env vars raise at startup (catches typos like
        BERAKAH_VALT_ROOT vs BERAKAH_VAULT_ROOT)." `extra="forbid"` alone does NOT
        catch this in pydantic-settings v2 — it only forbids unknown kwargs at
        direct construction, not unknown env-var sources. This validator closes
        the gap by reading os.environ ONCE at construction time and raising a
        ValidationError if any BERAKAH_-prefixed var is not a declared field.

        This is the ONLY direct env-var read in the entire codebase; the
        CONFIG-01 codebase-wide grep test (test_no_direct_env_var_reads_in_codebase_outside_config)
        explicitly exempts berakah/config.py.
        """
        declared_fields = set(cls.model_fields.keys())
        unknown: list[str] = []
        for key in os.environ:
            if not key.upper().startswith(_ENV_PREFIX):
                continue
            field_name = key[len(_ENV_PREFIX) :].lower()
            # Strip nested delimiter to recover the top-level field name
            if "__" in field_name:
                field_name = field_name.split("__", maxsplit=1)[0]
            if field_name not in declared_fields:
                unknown.append(key)
        if unknown:
            raise ValueError(
                f"Unknown {_ENV_PREFIX} environment variable(s): {sorted(unknown)}. "
                f"Known fields: {sorted(declared_fields)}. "
                f"This likely indicates a typo (e.g., BERAKAH_VALT_ROOT vs BERAKAH_VAULT_ROOT)."
            )
        return data

    # Paths
    project_root: Path = Field(default_factory=Path.cwd)
    data_root: Path = Field(default=Path("data"))
    artifacts_root: Path = Field(default=Path("artifacts"))
    vault_root: Path = Field(default=Path("berakah_KB"))
    regime_manifest_path: Path = Field(default=Path("berakah/data/regimes.toml"))

    # Universe (PROJECT.md constraints)
    exchanges: tuple[str, ...] = Field(default=("kraken", "coinbase", "binance"))
    pairs: tuple[str, ...] = Field(default=("BTC/USDT", "ETH/USDT"))
    timeframe_floor: Literal["5m", "15m", "1h", "1d"] = Field(default="5m")

    # Crypto Sharpe constant — Pitfall 11; single source of truth
    annualization_factor: float = Field(default_factory=lambda: math.sqrt(365 * 24 * 12))

    @field_validator(
        "data_root",
        "artifacts_root",
        "vault_root",
        "regime_manifest_path",
        mode="after",
    )
    @classmethod
    def _resolve_relative_to_project_root(cls, v: Path, info: ValidationInfo) -> Path:
        """Resolve relative paths to be absolute under `project_root`.

        Per checker Issue 2: strict-clean signature. `info: ValidationInfo` is the
        pydantic-typed validator context (NOT untyped `info`). `info.data` is
        `dict[str, Any] | None`; we defensively coerce the looked-up project_root via
        `isinstance` to avoid pyright's `reportUnknownArgumentType` under strict mode.
        """
        if v.is_absolute():
            return v
        project_root_raw = info.data.get("project_root") if info.data else None
        project_root = project_root_raw if isinstance(project_root_raw, Path) else Path.cwd()
        return (project_root / v).resolve()


__all__ = ["BerakahConfig"]
