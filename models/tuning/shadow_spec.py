"""Release E contract: one declared shadow period and what is frozen for it.

Its own hash (`shadow-<hash12>`), apart from RunSpec and DistRunSpec, so declaring a
shadow period never changes a published run id. Defaults are the values declared in
docs/superpowers/specs/2026-09-23-tuning-lab-release-e-design.md.
"""
from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import Field, field_validator

from models.tuning.dist_spec import DecisionPolicySpec, ExecutionSpec
from models.tuning.spec import _as_set, _sha256, _Spec, canonical_json


class ShadowSpec(_Spec):
    PROVENANCE: ClassVar[frozenset[str]] = frozenset({"created_at", "created_by", "notes"})

    schema_version: Literal[1] = 1
    spec_id: str
    created_at: str
    created_by: str
    notes: str = ""
    season: int
    period_weeks: tuple[int, ...] = Field(min_length=1)
    rehearsal_weeks: tuple[int, ...] = ()          # snapshotted and scored, never counted
    champion: Literal["ridge_v1_total"] = "ridge_v1_total"
    ridge_lambda: tuple[float, float] = (40.0, 8.0)
    base_run_id: str = Field(pattern=r"^run-[0-9a-f]{12}(-r\d+)?$")
    dist_run_id: str = Field(pattern=r"^dist-[0-9a-f]{12}$")
    window_seasons: tuple[int, ...] = Field(min_length=1)
    first_season: int = 2014                        # past_mean and ratings load from here
    snapshot_grace_hours: float = Field(6.0, ge=0)  # a game this long past kickoff must be final
    force_before_cutoff_hours: float = Field(12.0, ge=0)  # then snapshot even with stale inputs
    no_action_after_days: float = Field(7.0, gt=0)  # never completed this long after kickoff
    policy: DecisionPolicySpec                      # frozen now; replayed after the period only
    execution: ExecutionSpec = ExecutionSpec()

    _sets = field_validator("period_weeks", "rehearsal_weeks", "window_seasons")(_as_set)

    @property
    def config_hash(self) -> str:
        return _sha256(canonical_json(self, exclude=self.PROVENANCE))

    def shadow_id(self) -> str:
        return f"shadow-{self.config_hash[:12]}"
