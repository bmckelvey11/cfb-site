"""Weekly offense, defense and pace rankings from the `ridge_v1` ratings.

    python -m scripts.weekly_rankings                 # latest season with a games file
    python -m scripts.weekly_rankings --season 2025

For every week of the season with a completed FBS-vs-FBS game, fits `ridge_v1` (lambda 40
possessions, 8 games; docs/weekly-ratings-2026-09-23.md) on the season's completed, ungated
FBS-vs-FBS regular-season games through that week, and ranks every team:

    offense  O descending   1 = most points per possession above average
    defense  D ascending    1 = fewest allowed (the most negative D)
    pace     P descending   1 = most possessions per game

Ratings only: no forecast is scored against a result, so this never touches the 2026
prior_v3 confirmation. Writes data/processed/ratings/rankings/<season>.csv (every week) and
<season>/week_NN.md (one readable table per week). scripts/refresh_cfbd.cmd runs it after
each daily fetch, so a week's rankings appear once its games are on disk.
"""
from __future__ import annotations

import argparse
import json
import re

import pandas as pd

from scripts.weekly_ratings import Ratings, build_games, fit_ridge

RIDGE_V1 = (40, 8)  # Release B picks; docs/weekly-ratings-2026-09-23.md
RANK_ORDER = {"O": False, "D": True, "P": False}  # ascending? (D: lower allowed is better)


def rank_week(games: pd.DataFrame, lam_ppp: float = RIDGE_V1[0],
              lam_pace: float = RIDGE_V1[1]) -> tuple[Ratings, pd.DataFrame]:
    """Fit ridge_v1 on `games` and add O_rank, D_rank, P_rank (1 = best / fastest)."""
    r = fit_ridge(games, lam_ppp, lam_pace)
    t = r.table.copy()
    for col, ascending in RANK_ORDER.items():
        t[f"{col}_rank"] = t[col].rank(ascending=ascending, method="min").astype(int)
    return r, t


def season_rankings(games: pd.DataFrame, season: int, **lam
                    ) -> list[tuple[int, Ratings, pd.DataFrame]]:
    """(week, ratings, ranked table) through each week with a completed, ungated game."""
    sg = games[(games["season"] == season) & ~games["gated"]]
    return [(int(w), *rank_week(sg[sg["week"] <= w], **lam)) for w in sorted(sg["week"].unique())]


def scheduled_through(payload: list[dict]) -> pd.Series:
    """FBS-vs-FBS regular-season games scheduled through each week, completed or not."""
    weeks = pd.Series([g["week"] for g in payload if g.get("seasonType") == "regular"
                       and g.get("homeClassification") == "fbs"
                       and g.get("awayClassification") == "fbs"], dtype=int)
    return weeks.value_counts().sort_index().cumsum()


def week_markdown(season: int, week: int, r: Ratings, t: pd.DataFrame,
                  fit: int, scheduled: int) -> str:
    cols = {c: t.sort_values(c, ascending=a) for c, a in RANK_ORDER.items()}
    rows = [f"| {i + 1} | " + " | ".join(f"{cols[c].index[i]} | {cols[c][c].iloc[i]:+.2f}"
                                         for c in RANK_ORDER) + " |" for i in range(len(t))]
    return "\n".join([
        f"# {season} offense, defense and pace rankings through week {week}", "",
        f"`ridge_v1` (λ 40 possessions, 8 games) fit on {fit} of the {scheduled} FBS-vs-FBS "
        f"regular-season games scheduled through week {week}; the rest are not completed or "
        f"failed the drive-count gate. League average: {r.mu:.2f} points per possession, "
        f"{r.nu:.1f} possessions per team.", "",
        "- **Offense** $O$: points per possession above average. + is better.",
        "- **Defense** $D$: points per possession allowed vs average. − is better.",
        "- **Pace** $P$: possessions per team per game vs average. + is faster.", "",
        "Ratings are pulled toward 0 until a team has several games, so early weeks rank "
        "thin evidence. Method: `docs/weekly-ratings-2026-09-23.md`.", "",
        "| Rank | Offense | $O$ | Defense | $D$ | Pace | $P$ |",
        "| ---: | --- | ---: | --- | ---: | --- | ---: |",
        *rows, ""])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--season", type=int, help="default: latest season with a games file")
    ap.add_argument("--top", type=int, default=10, help="rows to print for the latest week")
    args = ap.parse_args(argv)

    from cfb_paths import DATA_ROOT, PROCESSED

    raw = DATA_ROOT / "raw"
    season = args.season or max(int(m[1]) for p in raw.glob("games_*.json")
                                if (m := re.fullmatch(r"games_(\d{4})\.json", p.name)))
    payload = json.loads((raw / f"games_{season}.json").read_text(encoding="utf-8"))
    games, _ = build_games(payload, json.loads((raw / f"drives_{season}.json").read_text(encoding="utf-8")))
    weeks = season_rankings(games, season)
    if not weeks:
        print(f"{season}: no completed FBS-vs-FBS games yet; nothing written")
        return 0

    sched = scheduled_through(payload)
    out = PROCESSED / "ratings" / "rankings"
    (out / str(season)).mkdir(parents=True, exist_ok=True)
    frames = []
    for week, r, t in weeks:
        fit = int(((games["season"] == season) & ~games["gated"] & (games["week"] <= week)).sum())
        (out / str(season) / f"week_{week:02d}.md").write_text(
            week_markdown(season, week, r, t, fit, int(sched[week])), encoding="utf-8")
        frames.append(t.reset_index(names="team").assign(
            season=season, through_week=week, mu=r.mu, nu=r.nu, h=r.h,
            lambda_ppp=RIDGE_V1[0], lambda_pace=RIDGE_V1[1],
            games_fit=fit, games_scheduled=int(sched[week])))
    pd.concat(frames, ignore_index=True).to_csv(out / f"{season}.csv", index=False)

    week, _, t = weeks[-1]
    print(f"{season} rankings through week {week}: wrote {len(weeks)} week(s) to {out}")
    for col, ascending in RANK_ORDER.items():
        top = t.sort_values(col, ascending=ascending)[col].head(args.top)
        print(f"  {col}: " + ", ".join(f"{team} {v:+.2f}" for team, v in top.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
