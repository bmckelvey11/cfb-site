"""Previous-season priors for the weekly ratings (guide §7.4, restricted to CFBD inputs).

    O0 = (b + c * RP) * O_prev      RP = offensive returning production (percentPPA)
    D0 = b_D * D_prev               CFBD has no defensive returning production
    P0 = a * P_prev

O_prev, D_prev, P_prev are last season's final ridge ratings, fit on its whole regular
season; that season ended before this one began, so they are legal inputs. Each season's
priors are centered to sum to 0 so the ridge penalty never competes with mu or nu.

See docs/superpowers/specs/2026-09-23-weekly-priors-design.md.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.weekly_ratings import Ratings, fit_ridge


def final_ratings(games: pd.DataFrame, season: int, lam_ppp: float, lam_pace: float) -> Ratings:
    """Whole-regular-season ridge ratings for `season` (drive gate on)."""
    sg = games[(games["season"] == season) & ~games["gated"]]
    return fit_ridge(sg, lam_ppp, lam_pace)


def load_rp(root: Path, season: int, sources: list[Path]) -> pd.Series:
    """Offensive returning production (`percentPPA`, 0-1) by team."""
    path = root / "raw" / f"returning_production_{season}.json"
    sources.append(path)
    rows = json.loads(path.read_text(encoding="utf-8"))
    return pd.Series({r["team"]: r["percentPPA"] for r in rows
                      if r.get("percentPPA") is not None}, dtype=float)


def season_teams(games: pd.DataFrame, season: int) -> list[str]:
    """The season's FBS teams: known from the schedule before any game is played."""
    sg = games[games["season"] == season]
    return sorted(set(sg["home"]) | set(sg["away"]))


def carryover_pairs(prev: Ratings, cur: Ratings, rp: pd.Series) -> pd.DataFrame:
    """Teams rated in both seasons, with last season's and this season's final ratings."""
    teams = prev.table.index.intersection(cur.table.index)
    out = pd.DataFrame({
        "team": teams,
        "O_prev": prev.table.loc[teams, "O"].to_numpy(), "O_cur": cur.table.loc[teams, "O"].to_numpy(),
        "D_prev": prev.table.loc[teams, "D"].to_numpy(), "D_cur": cur.table.loc[teams, "D"].to_numpy(),
        "P_prev": prev.table.loc[teams, "P"].to_numpy(), "P_cur": cur.table.loc[teams, "P"].to_numpy(),
    })
    out["rp"] = out["team"].map(rp)
    return out.dropna(subset=["rp"])


def _ols_no_intercept(x: np.ndarray, y: np.ndarray, groups: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Coefficients and team-clustered (CR0) standard errors."""
    xtx_inv = np.linalg.inv(x.T @ x)
    beta = xtx_inv @ x.T @ y
    e = y - x @ beta
    meat = np.zeros((x.shape[1], x.shape[1]))
    for g in np.unique(groups):
        s = x[groups == g].T @ e[groups == g]
        meat += np.outer(s, s)
    return beta, np.sqrt(np.diag(xtx_inv @ meat @ xtx_inv))


def fit_carryover(pairs: pd.DataFrame) -> dict:
    """b, c (offense), b_D (defense), a (pace) by no-intercept OLS, clustered by team."""
    g = pairs["team"].to_numpy()
    xo = np.column_stack([pairs["O_prev"], pairs["rp"] * pairs["O_prev"]])
    (b, c), (se_b, se_c) = _ols_no_intercept(xo, pairs["O_cur"].to_numpy(), g)
    (b_d,), (se_bd,) = _ols_no_intercept(pairs[["D_prev"]].to_numpy(), pairs["D_cur"].to_numpy(), g)
    (a,), (se_a,) = _ols_no_intercept(pairs[["P_prev"]].to_numpy(), pairs["P_cur"].to_numpy(), g)
    n = {"n_pairs": int(len(pairs)), "n_teams": int(pairs["team"].nunique())}
    return {"b": {"value": float(b), "se": float(se_b), **n},
            "c": {"value": float(c), "se": float(se_c), **n},
            "b_D": {"value": float(b_d), "se": float(se_bd), **n},
            "a": {"value": float(a), "se": float(se_a), **n}}


def build_priors(prev: Ratings, rp: pd.Series, teams: list[str], coefs: dict,
                 scale: float = 1.0) -> pd.DataFrame:
    """Centered O0, D0, P0 for `teams`. `scale` multiplies every coefficient (stress)."""
    b, c, b_d, a = (scale * coefs[k]["value"] for k in ("b", "c", "b_D", "a"))
    out = pd.DataFrame(index=pd.Index(teams, name=None))
    known = out.index.isin(prev.table.index)
    has_rp = out.index.isin(rp.index)
    out["rp"] = rp.reindex(out.index).fillna(rp.reindex(teams).mean() if has_rp.any() else rp.mean())
    out["prior_source"] = np.where(~known, "new_to_fbs", np.where(has_rp, "carryover", "rp_imputed"))
    last = prev.table.reindex(out.index)[["O", "D", "P"]].fillna(0.0)
    out["O0"] = (b + c * out["rp"]) * last["O"]
    out["D0"] = b_d * last["D"]
    out["P0"] = a * last["P"]
    for col in ("O0", "D0", "P0"):
        out[col] -= out[col].mean()
    return out


def priors_for_season(games: pd.DataFrame, season: int, rp: pd.Series, coefs: dict,
                      lam_ppp: float, lam_pace: float, scale: float = 1.0) -> pd.DataFrame:
    """Priors for `season` from season - 1's final ratings. Reads no season-`season` result."""
    prev = final_ratings(games, season - 1, lam_ppp, lam_pace)
    return build_priors(prev, rp, season_teams(games, season), coefs, scale)


def week1_ratings(prev: Ratings, priors: pd.DataFrame) -> Ratings:
    """Before any game: ratings are the priors, league levels are last season's final ones."""
    table = priors[["O0", "D0", "P0"]].set_axis(["O", "D", "P"], axis=1).assign(
        n_games=0, n_possessions=0)
    return Ratings(mu=prev.mu, nu=prev.nu, h=prev.h, c=prev.c, table=table, unrated=0.0)
