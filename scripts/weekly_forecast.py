"""Total forecasts for one week's FBS-vs-FBS games from the weekly possession ratings.

    python -m scripts.weekly_forecast                    # next week with an unplayed game
    python -m scripts.weekly_forecast --season 2026 --week 4

Fits `ridge_v1` (Release B, lambda 40/8; docs/weekly-ratings-2026-09-23.md) and `prior_v1`
(the same ridge centred on each team's carryover prior; docs/weekly-priors-2026-09-23.md) on
the season's completed, ungated FBS-vs-FBS games that kicked off before the week's first
kickoff -- the frozen snapshot the evaluation scored -- and prints every game of the week:
the ridge total with its possessions and implied regulation score, the prior_v1 total, and
the Bovada open and current total from lines_<season>.json.

Forecasts only: nothing is scored, so the sealed 2026 prior_v3 confirmation is untouched.
Release B found ridge_v1 0.33 points further from the total than the Bovada open, its gap to
the open uninformative (slope 0.03), and no better than the mean when a team had under three
games. The table is not a list of bets.
"""
from __future__ import annotations

import argparse
import json
import re

import pandas as pd

from scripts.weekly_rankings import RIDGE_V1, season_prior
from scripts.weekly_ratings import Ratings, fit_ridge, fit_set, forecast_total
from scripts.weekly_ratings_eval import MIN_PRIOR_GAMES, OPEN_PROVIDER, load


def week_schedule(payload: list[dict], week: int) -> pd.DataFrame:
    """The week's FBS-vs-FBS regular-season games, played or not, in kickoff order."""
    rows = [{"game_id": g["id"], "kickoff": pd.Timestamp(g["startDate"]).tz_convert("UTC"),
             "home": g["homeTeam"], "away": g["awayTeam"], "neutral": bool(g.get("neutralSite")),
             "completed": bool(g.get("completed"))}
            for g in payload if g.get("seasonType") == "regular" and g.get("week") == week
            and g.get("homeClassification") == "fbs" and g.get("awayClassification") == "fbs"]
    return pd.DataFrame(rows).sort_values(["kickoff", "home"], ignore_index=True)


def next_week(payload: list[dict]) -> int | None:
    """Earliest week with an unplayed FBS-vs-FBS regular-season game."""
    weeks = [g["week"] for g in payload if g.get("seasonType") == "regular" and not g.get("completed")
             and g.get("homeClassification") == "fbs" and g.get("awayClassification") == "fbs"]
    return min(weeks, default=None)


def book_totals(lines_payload: list[dict]) -> dict[int, tuple]:
    """(open, current) total from OPEN_PROVIDER, first row per game as in the evaluation."""
    out: dict[int, tuple] = {}
    for g in lines_payload:
        for ln in g.get("lines") or []:
            if ln.get("provider") == OPEN_PROVIDER and g["id"] not in out:
                out[g["id"]] = (ln.get("overUnderOpen"), ln.get("overUnder"))
    return out


def _parts(r: Ratings, home: str, away: str, neutral: bool) -> tuple[float, float, float]:
    """(possessions per team, home regulation points, away regulation points)."""
    def get(team: str, col: str) -> float:
        return float(r.table.at[team, col]) if team in r.table.index else r.unrated
    hh = 0 if neutral else 1
    n = r.nu + get(home, "P") + get(away, "P")
    return (n, n * (r.mu + get(home, "O") + get(away, "D") + r.h * hh),
            n * (r.mu + get(away, "O") + get(home, "D") - r.h * hh))


def forecast_week(games: pd.DataFrame, sched: pd.DataFrame, season: int,
                  prior: pd.DataFrame | None) -> tuple[pd.DataFrame, Ratings, int]:
    """One row per scheduled game, from the snapshot frozen at the week's first kickoff."""
    fs = fit_set(games[games["season"] == season], sched["kickoff"].min())
    ridge = fit_ridge(fs, *RIDGE_V1)
    pv1 = fit_ridge(fs, *RIDGE_V1, prior) if prior is not None else None
    n_games = ridge.table["n_games"]
    rows = []
    for g in sched.itertuples():
        n, pts_h, pts_a = _parts(ridge, g.home, g.away, g.neutral)
        total = forecast_total(ridge, g.home, g.away, g.neutral)
        assert abs(total - (pts_h + pts_a + ridge.c)) < 1e-9
        rows.append({"game_id": g.game_id, "kickoff": g.kickoff, "home": g.home, "away": g.away,
                     "neutral": g.neutral, "min_games": int(min(n_games.get(g.home, 0), n_games.get(g.away, 0))),
                     "poss": n, "home_pts": pts_h, "away_pts": pts_a, "ridge": total,
                     "prior_v1": forecast_total(pv1, g.home, g.away, g.neutral) if pv1 else None})
    return pd.DataFrame(rows), ridge, len(fs)


def _num(v, fmt="{:.1f}") -> str:
    return "—" if v is None or pd.isna(v) else fmt.format(v)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--season", type=int, help="default: latest season with a games file")
    ap.add_argument("--week", type=int, help="default: earliest week with an unplayed game")
    args = ap.parse_args(argv)

    from cfb_paths import DATA_ROOT

    raw = DATA_ROOT / "raw"
    season = args.season or max(int(m[1]) for p in raw.glob("games_*.json")
                                if (m := re.fullmatch(r"games_(\d{4})\.json", p.name)))
    payload = json.loads((raw / f"games_{season}.json").read_text(encoding="utf-8"))
    week = args.week or next_week(payload)
    sched = week_schedule(payload, week) if week else pd.DataFrame()
    if sched.empty:
        print(f"{season}: no FBS-vs-FBS regular-season games to forecast")
        return 0

    games, _ = load(DATA_ROOT, [season - 1, season], [])
    df, r, n_fit = forecast_week(games, sched, season, season_prior(games, season, DATA_ROOT))
    books = book_totals(json.loads((raw / f"lines_{season}.json").read_text(encoding="utf-8")))
    df["open"] = df["game_id"].map(lambda i: books.get(i, (None, None))[0])
    df["now"] = df["game_id"].map(lambda i: books.get(i, (None, None))[1])

    cut = sched["kickoff"].min().tz_convert("America/New_York")
    thin = int((df["min_games"] < MIN_PRIOR_GAMES).sum())
    print(f"# {season} week {week}: model totals\n")
    print(f"Ratings frozen at the week's first kickoff ({cut:%a %b %d %I:%M %p} ET), fit on {n_fit} "
          f"completed FBS-vs-FBS games. League {r.mu:.2f} points per possession, "
          f"{r.nu:.1f} possessions a team, {r.c:.2f} overtime points a game. Bovada lines as of "
          f"the last lines fetch. {thin} of {len(df)} games have a team with under "
          f"{MIN_PRIOR_GAMES} FBS games (marked *), where ridge_v1 matched the mean and trailed "
          f"the open by 0.65.\n")
    print("| Kickoff (ET) | Game | G | Poss | Implied (away–home) | ridge_v1 | prior_v1 "
          "| Bovada open | Bovada now | ridge − open |")
    print("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for g in df.itertuples():
        et = g.kickoff.tz_convert("America/New_York")
        game = f"{g.away} {'vs' if g.neutral else '@'} {g.home}"
        gap = None if g.open is None or pd.isna(g.open) else g.ridge - g.open
        print(f"| {et:%a %I:%M %p} | {game}{' *' if g.min_games < MIN_PRIOR_GAMES else ''} | {g.min_games} "
              f"| {g.poss:.1f} | {g.away_pts:.1f}–{g.home_pts:.1f} | {g.ridge:.1f} | {_num(g.prior_v1)} "
              f"| {_num(g.open)} | {_num(g.now)} | {_num(gap, '{:+.1f}')} |")
    print("\nG: fewer FBS-vs-FBS games of the two teams before the cutoff. Implied: regulation "
          "points, overtime excluded. Not a list of bets: ridge_v1 trailed the open in every "
          "scored season and its gap to the open carried no detectable information.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
