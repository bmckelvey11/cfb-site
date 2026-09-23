"""Season-holdout folds, game-grouped and chronological (Release C, C3).

A fold tests one season and trains on every earlier usable season, minus any training
game that kicks off within `embargo_days` of the test block's first decision time. Inner
folds (tuning) come first, then outer folds (evaluation); RunSpec has already checked
that no outer season is used by any inner fold.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd

from models.tuning.spec import FoldSpec


@dataclass(frozen=True)
class Fold:
    fold_id: str
    role: Literal["inner", "outer"]
    test_season: int
    train_idx: np.ndarray = field(repr=False)
    test_idx: np.ndarray = field(repr=False)
    bounds: dict = field(default_factory=dict)


def make_folds(fold_spec: FoldSpec, frame: pd.DataFrame) -> list[Fold]:
    usable = frame[~frame["season"].isin(fold_spec.exclude_seasons)]
    folds = []
    for role, seasons in (("inner", fold_spec.inner_test_seasons),
                          ("outer", fold_spec.outer_test_seasons)):
        for season in seasons:
            test = usable[usable["season"] == season]
            if test.empty:
                raise ValueError(f"no rows for test season {season}")
            limit = test["decision_ts"].min() - pd.Timedelta(days=fold_spec.embargo_days)
            train = usable[(usable["season"] < season) & (usable["kickoff"] < limit)]
            if train.empty:
                raise ValueError(f"fold {role}-{season} has no training rows")
            shared = set(train[fold_spec.group_key]) & set(test[fold_spec.group_key])
            if shared:
                raise ValueError(f"fold {role}-{season}: games on both sides: {sorted(shared)[:5]}")
            folds.append(Fold(
                fold_id=f"{role}-{season}", role=role, test_season=int(season),
                train_idx=train.index.to_numpy(), test_idx=test.index.to_numpy(),
                bounds={"train_seasons": sorted(int(s) for s in train["season"].unique()),
                        "train_rows": len(train), "test_rows": len(test),
                        "train_first_kickoff": train["kickoff"].min().isoformat(),
                        "train_last_kickoff": train["kickoff"].max().isoformat(),
                        "test_first_kickoff": test["kickoff"].min().isoformat(),
                        "test_last_kickoff": test["kickoff"].max().isoformat(),
                        "embargo_days": fold_spec.embargo_days}))
    return folds
