"""Release D contract: distribution runs, the calibration gate, decision policy, execution.

Separate from `RunSpec` on purpose: adding a field there, even a null one, would change
the hash of every published Release C run. A `DistRunSpec` names its Release C run by id
and carries its own hash (`dist-<hash12>`). Defaults are the values declared in
docs/superpowers/specs/2026-09-23-tuning-lab-release-d-design.md before any scoring.
"""
from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import Field, field_validator, model_validator

from models.tuning.spec import _as_set, _sha256, _Spec, canonical_json

Candidate = Literal["normal_const", "empirical_total", "joint_bootstrap"]


class DistributionSpec(_Spec):
    # Defaults are not validated, so they are written already sorted, as _as_set would.
    candidates: tuple[Candidate, ...] = ("empirical_total", "joint_bootstrap", "normal_const")
    baseline: Literal["normal_const"] = "normal_const"
    window_seasons: int = Field(3, ge=1)
    early_min_prior_games: int = Field(3, ge=1)   # below this, a game uses the early pool
    support_max: int = Field(150, ge=100)          # integer totals 0..support_max
    quantiles: tuple[float, ...] = (0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95)
    interval_levels: tuple[float, ...] = (0.5, 0.8, 0.9)

    _sets = field_validator("candidates", "quantiles", "interval_levels")(_as_set)

    @model_validator(mode="after")
    def _baseline_is_scored(self):
        if self.baseline not in self.candidates:
            raise ValueError("the baseline must be one of the candidates")
        return self


class CalibrationGate(_Spec):
    pooled_coverage_tol: float = Field(0.03, gt=0)
    season_coverage_level: float = Field(0.8, gt=0, lt=1)
    season_coverage_tol: float = Field(0.06, gt=0)
    pit_decile_tol: float = Field(0.02, gt=0)


class DistRunSpec(_Spec):
    PROVENANCE: ClassVar[frozenset[str]] = frozenset({"created_at", "created_by", "notes"})

    schema_version: Literal[1] = 1
    spec_id: str
    created_at: str
    created_by: str
    notes: str = ""
    base_run_id: str = Field(pattern=r"^run-[0-9a-f]{12}(-r\d+)?$")
    selection_seasons: tuple[int, ...] = Field(min_length=1)
    distribution: DistributionSpec = DistributionSpec()
    gate: CalibrationGate = CalibrationGate()
    open_label_pushes: Literal["exclude"] = "exclude"

    _sets = field_validator("selection_seasons")(_as_set)

    @property
    def config_hash(self) -> str:
        return _sha256(canonical_json(self, exclude=self.PROVENANCE))

    def run_id(self) -> str:
        return f"dist-{self.config_hash[:12]}"


class DecisionPolicySpec(_Spec):
    """A betting rule, versioned apart from the forecast model (plan §31.4)."""

    policy_id: str
    version: int = Field(ge=1)
    kind: Literal["no_bet", "point_edge", "min_ev", "prob_edge"]
    threshold: float = Field(0.0, ge=0)            # points, EV per unit, or probability
    min_prior_games: int = Field(0, ge=0)          # abstain when a team has fewer
    max_selective_score: float | None = None       # abstain when predicted error is higher

    @model_validator(mode="after")
    def _no_bet_has_no_threshold(self):
        if self.kind == "no_bet" and self.threshold != 0:
            raise ValueError("no_bet takes no threshold")
        return self


class ExecutionSpec(_Spec):
    """How a decision meets a quote, and the degradations applied to it (plan §31.6)."""

    quote_rule: Literal["best", "median", "named"] = "best"
    book: str | None = None
    max_quote_age_minutes: float = Field(24 * 60, gt=0)
    decision_delay_minutes: float = Field(0.0, ge=0)
    line_degradation: float = Field(0.0, ge=0)     # points moved against the bettor
    price_degradation_cents: int = Field(0, ge=0)  # American cents taken from the bettor
    missed_fill_rate: float = Field(0.0, ge=0, lt=1)
    fill_seed: int = 0
    stake: float = 1.0

    @model_validator(mode="after")
    def _consistent(self):
        if (self.quote_rule == "named") != (self.book is not None):
            raise ValueError("book is required for the named rule and forbidden otherwise")
        if self.stake != 1.0:
            raise ValueError("research reports use flat one-unit stakes (plan §31.5)")
        return self
