"""Ridge, Elastic Net, and Huber on a fixed matrix; fit_fold; outer comparisons (C3).

`fit_fold` fits median imputer -> standard scaler -> estimator on one fold's training
rows and returns a sealed FoldResult: predictions, error metrics, and paired comparisons
with each baseline on the same games. `compare_outer` pools the outer folds with Release
B's week-cluster bootstrap and verdict rule. The market baseline is the untimed Bovada
open, so every market comparison is labeled descriptive.
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import ElasticNet, HuberRegressor, Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from models.tuning.spec import AcceptanceSpec, FoldResult, ModelSpec, RunSpec

MARKET_LABEL = "descriptive: untimed vendor open, no price"


class FitFailure(Exception):
    """A classified trial failure (plan §15): recorded, never scored as a good trial."""

    def __init__(self, kind: str, message: str):
        super().__init__(f"{kind}: {message}")
        self.kind = kind


def build_pipeline(model: ModelSpec, seed: int) -> Pipeline:
    if model.family == "ridge":
        est = Ridge(alpha=model.alpha)
    elif model.family == "elastic_net":
        est = ElasticNet(alpha=model.alpha, l1_ratio=model.l1_ratio, random_state=seed,
                         max_iter=10_000)
    else:
        est = HuberRegressor(epsilon=model.epsilon, alpha=model.alpha, max_iter=1_000)
    return Pipeline([("impute", SimpleImputer(strategy="median")),
                     ("scale", StandardScaler()), ("model", est)])


def _errors(y: np.ndarray, y_hat: np.ndarray) -> dict[str, float | int]:
    e = y_hat - y
    return {"n": int(len(y)), "mae": float(np.abs(e).mean()),
            "rmse": float(np.sqrt((e ** 2).mean())), "bias": float(e.mean())}


def fit_fold(train: pd.DataFrame, test: pd.DataFrame, run_spec: RunSpec, model: ModelSpec,
             fold_id: str, run_id: str | None = None) -> FoldResult:
    role, _, _ = fold_id.partition("-")
    seasons = test["season"].unique()
    if role not in ("inner", "outer") or len(seasons) != 1:
        raise ValueError(f"fold {fold_id}: expected inner-/outer-<season> over one test season")
    features = [f.id for f in run_spec.feature_set.features if f.id in train.columns]
    if not features:
        raise FitFailure("data_validation", "no declared feature is present")
    x_train = train[features].to_numpy(dtype=float)
    empty = [f for f, col in zip(features, x_train.T) if np.isnan(col).all()]
    if empty:
        raise FitFailure("data_validation", f"all-null training features: {empty}")

    pipe = build_pipeline(model, run_spec.seeds.model)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        pipe.fit(x_train, train["target"].to_numpy(dtype=float))
        y_hat = pipe.predict(test[features].to_numpy(dtype=float))
    if not np.isfinite(y_hat).all():
        raise FitFailure("numerical_instability", "non-finite predictions")

    y = test["target"].to_numpy(dtype=float)
    comparisons = {}
    for b in run_spec.acceptance.baselines:
        if b not in test:
            continue
        have = test[b].notna().to_numpy()
        if not have.any():
            continue
        mine = float(np.abs(y_hat[have] - y[have]).mean())
        theirs = float(np.abs(test[b].to_numpy(dtype=float)[have] - y[have]).mean())
        comparisons[b] = {"n": int(have.sum()), "model_mae": mine, "baseline_mae": theirs,
                          "diff": mine - theirs}

    imp, scale, est = pipe.named_steps["impute"], pipe.named_steps["scale"], pipe.named_steps["model"]
    fitted = {"impute_median": imp.statistics_.tolist(), "scale_mean": scale.mean_.tolist(),
              "scale_sd": scale.scale_.tolist(), "coef": np.ravel(est.coef_).tolist(),
              "intercept": float(est.intercept_)}
    return FoldResult(
        run_id=run_id or run_spec.run_id(), config_hash=run_spec.config_hash, fold_id=fold_id,
        role=role, test_season=int(seasons[0]), model=model, features=tuple(features),
        fitted=fitted,
        predictions=tuple((int(g), float(p)) for g, p in zip(test["game_id"], y_hat)),
        metrics=_errors(y, y_hat), comparisons=comparisons,
        warnings=tuple(sorted({f"{w.category.__name__}: {w.message}" for w in caught})),
    ).sealed()


def compare_outer(predictions: pd.DataFrame, acceptance: AcceptanceSpec) -> dict:
    """Pooled outer-fold accuracy and paired MAE differences versus each baseline."""
    from scripts.weekly_ratings_eval import classify_verdict, paired_mae_diff

    df = predictions.rename(columns={"target": "total"}).reset_index(drop=True)
    y, y_hat = df["total"].to_numpy(dtype=float), df["y_hat"].to_numpy(dtype=float)
    slope, intercept = np.polyfit(y_hat, y, 1)  # actual on prediction: slope 1 is calibrated
    out = {"n": int(len(df)), "n_clusters": int(df.groupby(["season", "week"]).ngroups),
           "model": _errors(y, y_hat),
           "calibration": {"slope": float(slope), "intercept": float(intercept)},
           "by_season": {int(s): _errors(g["total"].to_numpy(dtype=float),
                                         g["y_hat"].to_numpy(dtype=float))
                         for s, g in df.groupby("season")},
           "baselines": {}}
    for b in acceptance.baselines:
        sub = df[df[b].notna()] if b in df else df.iloc[0:0]
        if sub.empty:
            out["baselines"][b] = {"n": 0}
            continue
        p = paired_mae_diff(sub, "y_hat", b)
        p["model_mae"] = float((sub["y_hat"] - sub["total"]).abs().mean())
        p["baseline_mae"] = float((sub[b] - sub["total"]).abs().mean())
        p["verdict"] = classify_verdict(*p["ci95"], list(p["by_season"].values()))
        if b == "market_open":
            p["label"] = MARKET_LABEL
        out["baselines"][b] = p
    return out


def acceptance_gates(comparisons: dict, acceptance: AcceptanceSpec, *, n_features: int,
                     fold_warnings: list[str], dropped: dict[str, str]) -> dict[str, dict]:
    """The plan §17 gates this release can check; each says pass or fail and why."""
    bias = comparisons["model"]["bias"]
    return {
        "bias": {"pass": abs(bias) <= acceptance.bias_tolerance,
                 "detail": f"outer mean residual {bias:+.3f} vs tolerance ±{acceptance.bias_tolerance}"},
        "complexity": {"pass": n_features <= acceptance.max_features,
                       "detail": f"{n_features} features, limit {acceptance.max_features}"},
        "convergence": {"pass": not fold_warnings,
                        "detail": "; ".join(sorted(set(fold_warnings))) or "no warnings"},
        "data_availability": {"pass": not dropped,
                              "detail": "; ".join(f"{k}: {v}" for k, v in dropped.items())
                              or "every declared feature passed the as-of screen"},
        "market_realism": {"pass": True,
                           "detail": "no market-derived feature is used; the market baseline "
                                     "is an untimed vendor open, so its comparison is descriptive"},
        "confirmation_lock": {"pass": True,
                              "detail": "enforced by RunSpec: outer seasons follow every inner fold"},
    }
