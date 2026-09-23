"""Typed run specifications, the config hash, and sealed fold results (Release C, C0).

Every spec is frozen and rejects unknown fields, so an old worker cannot silently ignore
a new option. `RunSpec.config_hash` is the sha256 of the canonical JSON of everything
that determines results; `created_at` and `created_by` are provenance and are left out.
Set-like lists (seasons, baselines) are sorted so reordering them does not change the
hash; feature order is kept because it is the design matrix's column order.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

AvailabilityClass = Literal["historical_replayable", "snapshot_dependent", "prospective_only",
                            "retrospective_descriptive", "provider_opaque"]
Baseline = Literal["market_open", "past_mean", "ridge_v1_total"]

# Plan §14, profile cfb_regularized_regression_v1: (low, high, log scale).
SEARCH_PROFILES: dict[str, dict[str, dict[str, tuple[float, float, bool]]]] = {
    "cfb_regularized_regression_v1": {
        "ridge": {"alpha": (0.001, 1000.0, True)},
        "elastic_net": {"alpha": (0.0001, 20.0, True), "l1_ratio": (0.01, 0.99, False)},
    },
}
# The only bootstrap compare_outer implements: scripts.weekly_ratings_eval's.
RELEASE_B_BOOTSTRAP = {"unit": "season_week", "draws": 10_000, "seed": 20260922}


def canonical_json(model: BaseModel, exclude: set[str] | frozenset[str] = frozenset()) -> str:
    return json.dumps(model.model_dump(mode="json", exclude=set(exclude)), sort_keys=True,
                      separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class _Spec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _as_set(v: tuple) -> tuple:
    return tuple(sorted(set(v)))


class DatasetSpec(_Spec):
    source: Literal["cfb_release_b", "synthetic_v1"]
    snapshot: str
    grain: Literal["game"] = "game"
    target: Literal["total"] = "total"
    decision_time: Literal["week_cutoff"] = "week_cutoff"
    population: Literal["fbs_vs_fbs_week2plus"] = "fbs_vs_fbs_week2plus"
    seasons: tuple[int, ...] = Field(min_length=1)
    synthetic_seed: int | None = None

    _sets = field_validator("seasons")(_as_set)

    @model_validator(mode="after")
    def _seed_iff_synthetic(self):
        if (self.source == "synthetic_v1") != (self.synthetic_seed is not None):
            raise ValueError("synthetic_seed is required for synthetic_v1 and forbidden otherwise")
        return self


class FeatureRef(_Spec):
    id: str
    version: int = Field(ge=1)
    availability_class: AvailabilityClass


class FeatureSetSpec(_Spec):
    feature_set_id: str
    version: int = Field(ge=1)
    features: tuple[FeatureRef, ...] = Field(min_length=1)

    @field_validator("features")
    @classmethod
    def _unique(cls, v):
        ids = [f.id for f in v]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            raise ValueError(f"duplicate feature ids: {dupes}")
        return v


class FoldSpec(_Spec):
    profile: Literal["season_holdout"] = "season_holdout"
    inner_test_seasons: tuple[int, ...]
    outer_test_seasons: tuple[int, ...] = Field(min_length=1)
    exclude_seasons: tuple[int, ...] = ()
    group_key: Literal["game_id"] = "game_id"
    embargo_days: int = Field(0, ge=0)

    _sets = field_validator("inner_test_seasons", "outer_test_seasons", "exclude_seasons")(_as_set)


class SamplerSpec(_Spec):
    name: Literal["tpe"] = "tpe"
    multivariate: bool = True
    group: bool = True
    n_startup_trials: int = Field(20, ge=0)


class PrunerSpec(_Spec):
    name: Literal["median"] = "median"
    n_startup_trials: int = Field(20, ge=0)
    # Pruning compares running fold means; never before the second fold (plan §15).
    n_warmup_steps: int = Field(2, ge=1)
    interval_steps: int = Field(1, ge=1)


class SearchSpec(_Spec):
    profile_id: Literal["cfb_regularized_regression_v1"]
    n_trials: int = Field(ge=1)
    objective: Literal["mae", "rmse"] = "mae"
    sampler: SamplerSpec = SamplerSpec()
    pruner: PrunerSpec = PrunerSpec()
    max_retry: int = Field(2, ge=0)


class BootstrapSpec(_Spec):
    unit: Literal["season_week"] = "season_week"
    draws: int = 10_000
    seed: int = 20260922

    @model_validator(mode="after")
    def _release_b_only(self):
        if self.model_dump() != RELEASE_B_BOOTSTRAP:
            raise ValueError(f"only the Release B bootstrap is implemented: {RELEASE_B_BOOTSTRAP}")
        return self


class AcceptanceSpec(_Spec):
    baselines: tuple[Baseline, ...] = Field(min_length=1)
    bootstrap: BootstrapSpec = BootstrapSpec()
    verdict_rule: Literal["classify_verdict_v1"] = "classify_verdict_v1"
    bias_tolerance: float = Field(1.0, gt=0)
    max_features: int = Field(20, ge=1)

    _sets = field_validator("baselines")(_as_set)


class Seeds(_Spec):
    split: int = 0
    model: int = 0
    sampler: int = 42


class RunSpec(_Spec):
    PROVENANCE: ClassVar[frozenset[str]] = frozenset({"created_at", "created_by", "notes"})

    schema_version: Literal[1] = 1
    spec_id: str
    created_at: str
    created_by: str
    notes: str = ""  # free text for the card (e.g. holdout status); not hashed
    dataset: DatasetSpec
    feature_set: FeatureSetSpec
    folds: FoldSpec
    search: SearchSpec
    acceptance: AcceptanceSpec
    seeds: Seeds = Seeds()

    @model_validator(mode="after")
    def _folds_fit_the_dataset(self):
        f, usable = self.folds, [s for s in self.dataset.seasons if s not in self.folds.exclude_seasons]
        tests = f.inner_test_seasons + f.outer_test_seasons
        missing = sorted(s for s in tests if s not in usable)
        if missing:
            raise ValueError(f"fold test seasons not in dataset (or excluded): {missing}")
        if len(f.inner_test_seasons) < 2:
            raise ValueError("need at least two inner folds: the pruner compares from the second")
        if min(tests) <= min(usable):
            raise ValueError(f"fold testing {min(tests)} has no training season")
        if f.inner_test_seasons and min(f.outer_test_seasons) <= max(f.inner_test_seasons):
            raise ValueError("confirmation lock: every outer test season must follow all inner "
                             "folds, so no outer season is used in tuning")
        if len(self.feature_set.features) > self.acceptance.max_features:
            raise ValueError(f"{len(self.feature_set.features)} features exceed max_features "
                             f"{self.acceptance.max_features}")
        return self

    @property
    def config_hash(self) -> str:
        return _sha256(canonical_json(self, exclude=self.PROVENANCE))

    def run_id(self, replicate: int = 0) -> str:
        return f"run-{self.config_hash[:12]}" + (f"-r{replicate}" if replicate else "")


def load_run_spec(path: str | Path) -> RunSpec:
    return RunSpec.model_validate_json(Path(path).read_text(encoding="utf-8"))


class ModelSpec(_Spec):
    family: Literal["ridge", "elastic_net", "huber"]
    alpha: float = Field(gt=0)
    l1_ratio: float | None = Field(None, ge=0, le=1)   # elastic_net only
    epsilon: float | None = Field(None, gt=1)         # huber only

    @model_validator(mode="after")
    def _params_match_family(self):
        if (self.family == "elastic_net") != (self.l1_ratio is not None):
            raise ValueError("l1_ratio is required for elastic_net and forbidden otherwise")
        if (self.family == "huber") != (self.epsilon is not None):
            raise ValueError("epsilon is required for huber and forbidden otherwise")
        return self


class FoldResult(_Spec):
    """One fitted fold. `artifact_sha256` seals everything else in the record."""

    run_id: str
    config_hash: str
    fold_id: str
    role: Literal["inner", "outer"]
    test_season: int
    model: ModelSpec
    features: tuple[str, ...]
    fitted: dict[str, Any]
    predictions: tuple[tuple[int, float], ...]
    metrics: dict[str, float | int]
    comparisons: dict[str, dict[str, float | int]]
    warnings: tuple[str, ...] = ()
    artifact_sha256: str = ""

    def _digest(self) -> str:
        return _sha256(canonical_json(self, exclude={"artifact_sha256"}))

    def sealed(self) -> FoldResult:
        return self.model_copy(update={"artifact_sha256": self._digest()})

    def verify(self) -> bool:
        return self.artifact_sha256 == self._digest()
