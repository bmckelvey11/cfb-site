"""Weekly as-of team points-per-possession and pace ratings (Release B).

Implements research/totals/docs/totals-modeling-guide.md §7.1-7.3 without priors:

    points per possession  y = mu + O_team + D_opponent + h*H      (H = +1/-1/0)
    possessions per team   N = nu + P_home + P_away
    total                  T = N * (PPP_home + PPP_away) + c       (c = mean OT points)

`ridge_v1` fits both by weighted least squares with a ridge penalty toward 0 (league
average); `raw_v1` is season-to-date means with no opponent adjustment. Every rating is
frozen at a cutoff and sees only games that kicked off strictly before it, through
`snapshot()` from the Release A replay.

Points are Q1-Q4 line scores, not drive score fields: from 2021 on, 19-58 FBS games a
season have drive points above the final score. Drives supply possession counts only.
So O is a *team* rate: a team's own defensive and return touchdowns are in it.

See docs/superpowers/specs/2026-09-22-weekly-ratings-design.md.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import numpy as np
import pandas as pd

from scripts.pregame_replay_audit import snapshot

# Possessions alternate, so a wider gap between the two teams' regulation drive counts
# means drives are missing from the feed (~2% of games).
MAX_DRIVE_GAP = 2


@dataclass(frozen=True)
class Ratings:
    """One frozen snapshot. `table` is indexed by team: O, D, P (+ evidence counts)."""
    mu: float
    nu: float
    h: float
    c: float
    table: pd.DataFrame
    unrated: float  # rating for a team with no games: 0.0 (ridge) or NaN (raw)


def build_games(games_payload: list[dict], drives_payload: list[dict]
                ) -> tuple[pd.DataFrame, dict[str, int]]:
    """One row per completed FBS-vs-FBS regular-season game, plus drop counts.

    Gated games (no drives, or drive counts too far apart) stay in the frame with
    `gated=True`: their evidence is withheld from fits, but they can still be scored.
    """
    poss: Counter = Counter()
    for d in drives_payload:
        if 1 <= (d.get("startPeriod") or 0) <= 4:
            poss[(d["gameId"], bool(d.get("isHomeOffense")))] += 1

    rows, drops = [], Counter()
    for g in games_payload:
        if g.get("seasonType") != "regular":
            drops["not_regular_season"] += 1
            continue
        if not g.get("completed"):
            drops["not_completed"] += 1
            continue
        if g.get("homeClassification") != "fbs" or g.get("awayClassification") != "fbs":
            drops["not_fbs_vs_fbs"] += 1
            continue
        hls, als = g.get("homeLineScores") or [], g.get("awayLineScores") or []
        if (len(hls) < 4 or len(als) < 4 or sum(hls) != g.get("homePoints")
                or sum(als) != g.get("awayPoints")):
            drops["line_scores_do_not_sum_to_final"] += 1
            continue
        kickoff = pd.to_datetime(g.get("startDate"), errors="coerce", utc=True)
        if pd.isna(kickoff):
            drops["no_kickoff"] += 1
            continue
        hp, ap = poss[(g["id"], True)], poss[(g["id"], False)]
        home_reg, away_reg = sum(hls[:4]), sum(als[:4])
        total = g["homePoints"] + g["awayPoints"]
        rows.append({
            "game_id": g["id"], "season": g["season"], "week": g["week"],
            "kickoff": kickoff, "home": g["homeTeam"], "away": g["awayTeam"],
            "neutral": bool(g.get("neutralSite")),
            "home_reg": home_reg, "away_reg": away_reg,
            "home_poss": hp, "away_poss": ap, "N": (hp + ap) / 2,
            "ot": total - home_reg - away_reg, "total": total,
            "gated": hp == 0 or ap == 0 or abs(hp - ap) > MAX_DRIVE_GAP,
        })
    return pd.DataFrame(rows), dict(drops)


def fit_set(games: pd.DataFrame, cutoff: pd.Timestamp) -> pd.DataFrame:
    """Evidence at `cutoff`: games kicked off strictly before it, minus gated games."""
    seen = snapshot(games, cutoff)
    return seen[~seen["gated"]]


def _team_rows(games: pd.DataFrame) -> pd.DataFrame:
    """Two rows per game: each side's points per possession against the other defense."""
    hh = np.where(games["neutral"], 0, 1)
    home = pd.DataFrame({"team": games["home"], "opp": games["away"], "H": hh,
                         "pts": games["home_reg"], "w": games["home_poss"]})
    away = pd.DataFrame({"team": games["away"], "opp": games["home"], "H": -hh,
                         "pts": games["away_reg"], "w": games["away_poss"]})
    rows = pd.concat([home, away], ignore_index=True)
    rows["y"] = rows["pts"] / rows["w"]
    return rows


def _solve(x: np.ndarray, y: np.ndarray, w: np.ndarray, penalty: np.ndarray) -> np.ndarray:
    """Weighted ridge: (X'WX + diag(penalty)) b = X'Wy."""
    a = x.T @ (x * w[:, None]) + np.diag(penalty)
    # ponytail: lstsq, not solve -- an all-neutral early fit leaves the h column empty,
    # and the min-norm answer (h = 0) is the right one there.
    return np.linalg.lstsq(a, x.T @ (w * y), rcond=None)[0]


def _evidence(games: pd.DataFrame, teams: list[str]) -> pd.DataFrame:
    rows = _team_rows(games)
    return pd.DataFrame({
        "n_games": rows.groupby("team").size(),
        "n_possessions": rows.groupby("team")["w"].sum(),
    }).reindex(teams).fillna(0).astype(int)


def fit_ppp(games: pd.DataFrame, lam: float,
            prior: pd.DataFrame | None = None) -> tuple[float, float, pd.DataFrame]:
    """(mu, h, O/D table) by possession-weighted ridge; mu and h unpenalized.

    With `prior` (columns O0, D0), each rating is prior + deviation and only the
    deviation is penalized: guide §7.5's shrink-toward-the-prior fit.
    """
    rows = _team_rows(games)
    teams = sorted(set(rows["team"]) | set(rows["opp"]))
    idx = {t: i for i, t in enumerate(teams)}
    k = len(teams)
    o0 = _prior_col(prior, "O0", teams)
    d0 = _prior_col(prior, "D0", teams)
    x = np.zeros((len(rows), 2 + 2 * k))
    x[:, 0] = 1.0
    x[:, 1] = rows["H"]
    x[np.arange(len(rows)), 2 + rows["team"].map(idx)] = 1.0
    x[np.arange(len(rows)), 2 + k + rows["opp"].map(idx)] = 1.0
    y = rows["y"].to_numpy(float) - rows["team"].map(o0).to_numpy() - rows["opp"].map(d0).to_numpy()
    b = _solve(x, y, rows["w"].to_numpy(float), np.r_[0.0, 0.0, np.full(2 * k, lam)])
    return b[0], b[1], pd.DataFrame({"O": b[2:2 + k] + o0.to_numpy(),
                                     "D": b[2 + k:] + d0.to_numpy()}, index=teams)


def fit_pace(games: pd.DataFrame, lam: float,
             prior: pd.DataFrame | None = None) -> tuple[float, pd.Series]:
    """(nu, P) by ridge on game possession counts; each game weight 1, nu unpenalized."""
    teams = sorted(set(games["home"]) | set(games["away"]))
    idx = {t: i for i, t in enumerate(teams)}
    p0 = _prior_col(prior, "P0", teams)
    x = np.zeros((len(games), 1 + len(teams)))
    x[:, 0] = 1.0
    x[np.arange(len(games)), 1 + games["home"].map(idx)] = 1.0
    x[np.arange(len(games)), 1 + games["away"].map(idx)] = 1.0
    y = games["N"].to_numpy(float) - games["home"].map(p0).to_numpy() - games["away"].map(p0).to_numpy()
    b = _solve(x, y, np.ones(len(games)), np.r_[0.0, np.full(len(teams), lam)])
    return b[0], pd.Series(b[1:] + p0.to_numpy(), index=teams, name="P")


def _prior_col(prior: pd.DataFrame | None, col: str, teams: list[str]) -> pd.Series:
    """Prior values for `teams`; 0 (league average) where there is no prior."""
    if prior is None:
        return pd.Series(0.0, index=teams)
    return prior[col].reindex(teams).fillna(0.0).astype(float)


def fit_ridge(games: pd.DataFrame, lam_ppp: float, lam_pace: float,
              prior: pd.DataFrame | None = None) -> Ratings:
    """`prior=None` is Release B's ridge_v1; a prior (O0, D0, P0 by team) is prior_v1.

    Teams with a prior but no games yet are rated at their prior.
    """
    mu, h, od = fit_ppp(games, lam_ppp, prior)
    nu, p = fit_pace(games, lam_pace, prior)
    table = od.join(p, how="outer")
    if prior is not None:
        idle = prior.index.difference(table.index)
        table = pd.concat([table, prior.loc[idle, ["O0", "D0", "P0"]].set_axis(
            ["O", "D", "P"], axis=1)]).sort_index()
    table = table.join(_evidence(games, list(table.index)))
    return Ratings(mu=float(mu), nu=float(nu), h=float(h), c=float(games["ot"].mean()),
                   table=table, unrated=0.0)


def fit_raw(games: pd.DataFrame) -> Ratings:
    """Season-to-date means minus the league mean. No adjustment, no shrinkage, h = 0."""
    rows = _team_rows(games)
    mu = rows["pts"].sum() / rows["w"].sum()
    off = rows.groupby("team")[["pts", "w"]].sum()
    allowed = rows.groupby("opp")[["pts", "w"]].sum()
    n_by_team = pd.concat([games[["home", "N"]].rename(columns={"home": "team"}),
                           games[["away", "N"]].rename(columns={"away": "team"})])
    nu = float(games["N"].mean())
    table = pd.DataFrame({
        "O": off["pts"] / off["w"] - mu,
        "D": allowed["pts"] / allowed["w"] - mu,
        "P": n_by_team.groupby("team")["N"].mean() - nu,
    })
    table = table.join(_evidence(games, list(table.index)))
    return Ratings(mu=float(mu), nu=nu, h=0.0, c=float(games["ot"].mean()),
                   table=table, unrated=float("nan"))


def forecast_total(r: Ratings, home: str, away: str, neutral: bool) -> float:
    """Guide §7.3. Home field moves the two rates in opposite directions, so it cancels
    in the total; it matters only for fitting O and D without home/away bias."""
    def get(team: str, col: str) -> float:
        return float(r.table.at[team, col]) if team in r.table.index else r.unrated

    hh = 0 if neutral else 1
    n = r.nu + get(home, "P") + get(away, "P")
    ppp_home = r.mu + get(home, "O") + get(away, "D") + r.h * hh
    ppp_away = r.mu + get(away, "O") + get(home, "D") - r.h * hh
    return n * (ppp_home + ppp_away) + r.c
