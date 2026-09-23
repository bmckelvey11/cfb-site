"""Weekly offense, defense and volume rankings from the `prior_v1` ratings.

    python -m scripts.weekly_rankings                 # latest season with a games file
    python -m scripts.weekly_rankings --season 2025
    python -m scripts.weekly_rankings --fit ridge_v1  # no carryover prior

For every week of the season with a completed FBS-vs-FBS game, fits `prior_v1` (the
`ridge_v1` ridge, lambda 40 possessions, 8 games, with each rating written as last season's
carryover prior plus a penalized deviation; docs/weekly-priors-2026-09-23.md) on the season's
completed, ungated FBS-vs-FBS regular-season games through that week, and ranks every team:

    offense  O descending   1 = most points per possession above average
    defense  D ascending    1 = fewest allowed (the most negative D)
    volume   P descending   1 = most possessions per game (labelled "Volume": a sustained-
                            drive offense has few of them, so this is not tempo)

The prior is O0 = (b + c * RP) * O_prev, D0 = b_D * D_prev, P0 = a * P_prev with the
carryover coefficients frozen in scripts/weekly_prior_v3.json; prior_v3 is the same prior at
lambda 80. A team is pulled toward its own last season instead of the league average, so a
2-game outlier does not top the table. Ratings only: no forecast is scored against a result,
so this never touches the 2026 prior_v3 confirmation.
Writes data/processed/ratings/rankings/<season>.csv (every week),
<season>/week_NN.md (one readable table per week), and a web page of every season's CSV there:
index.html to open locally, artifact.html (the same page without the document wrapper) to
publish. scripts/refresh_cfbd.cmd runs it after each daily fetch, so a week's rankings
appear once its games are on disk.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from scripts.weekly_priors import load_rp, priors_for_season
from scripts.weekly_ratings import Ratings, fit_ridge
from scripts.weekly_ratings_eval import load

RIDGE_V1 = (40, 8)  # Release B picks; docs/weekly-ratings-2026-09-23.md
FROZEN = Path(__file__).with_name("weekly_prior_v3.json")  # carryover coefficients
METHOD = {"prior_v1": "prior_v1, λ 40 possessions and 8 games, ratings pulled toward last "
                      "season's carryover prior",
          "ridge_v1": "ridge_v1, λ 40 possessions and 8 games, ratings pulled toward the "
                      "league average"}
RANK_ORDER = {"O": False, "D": True, "P": False}  # ascending? (D: lower allowed is better)
PAGE = Path(__file__).with_name("weekly_rankings_page.html")
PAGE_ROW = ["team", "n_games", "O", "O_rank", "D", "D_rank", "P", "P_rank"]
LOCAL_HEAD = ('<!doctype html>\n<html lang="en">\n<meta charset="utf-8">\n'
              '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n')


def rank_week(games: pd.DataFrame, lam_ppp: float = RIDGE_V1[0], lam_pace: float = RIDGE_V1[1],
              prior: pd.DataFrame | None = None) -> tuple[Ratings, pd.DataFrame]:
    """Fit on `games` (prior_v1 with `prior`, else ridge_v1) and add O_rank, D_rank, P_rank."""
    r = fit_ridge(games, lam_ppp, lam_pace, prior)
    t = r.table.copy()
    for col, ascending in RANK_ORDER.items():
        t[f"{col}_rank"] = t[col].rank(ascending=ascending, method="min").astype(int)
    return r, t


def season_rankings(games: pd.DataFrame, season: int, prior: pd.DataFrame | None = None, **lam
                    ) -> list[tuple[int, Ratings, pd.DataFrame]]:
    """(week, ratings, ranked table) through each week with a completed, ungated game."""
    sg = games[(games["season"] == season) & ~games["gated"]]
    return [(int(w), *rank_week(sg[sg["week"] <= w], prior=prior, **lam))
            for w in sorted(sg["week"].unique())]


def season_prior(games: pd.DataFrame, season: int, root: Path) -> pd.DataFrame:
    """prior_v1's O0/D0/P0 for `season`: frozen carryover coefficients on season-1's finals."""
    coefs = {k: {"value": v} for k, v in
             json.loads(FROZEN.read_text(encoding="utf-8"))["coefficients"].items()}
    rp = load_rp(root, season, [])
    return priors_for_season(games, season, rp, coefs, *RIDGE_V1)


def scheduled_through(payload: list[dict]) -> pd.Series:
    """FBS-vs-FBS regular-season games scheduled through each week, completed or not."""
    weeks = pd.Series([g["week"] for g in payload if g.get("seasonType") == "regular"
                       and g.get("homeClassification") == "fbs"
                       and g.get("awayClassification") == "fbs"], dtype=int)
    return weeks.value_counts().sort_index().cumsum()


def week_markdown(season: int, week: int, r: Ratings, t: pd.DataFrame,
                  fit: int, scheduled: int, method: str = "prior_v1") -> str:
    cols = {c: t.sort_values(c, ascending=a) for c, a in RANK_ORDER.items()}
    rows = [f"| {i + 1} | " + " | ".join(f"{cols[c].index[i]} | {cols[c][c].iloc[i]:+.2f}"
                                         for c in RANK_ORDER) + " |" for i in range(len(t))]
    pulled = ("its own last season (carryover prior)" if method == "prior_v1"
              else "0 (league average)")
    return "\n".join([
        f"# {season} offense, defense and volume rankings through week {week}", "",
        f"`{method}` (λ 40 possessions, 8 games) fit on {fit} of the {scheduled} FBS-vs-FBS "
        f"regular-season games scheduled through week {week}; the rest are not completed or "
        f"failed the drive-count gate. League average: {r.mu:.2f} points per possession, "
        f"{r.nu:.1f} possessions per team.", "",
        "- **Offense** $O$: points per possession above average. + is better.",
        "- **Defense** $D$: points per possession allowed vs average. − is better.",
        "- **Volume** $P$: possessions per team per game vs average. + is more. Long scoring "
        "drives use up possessions, so an efficient offense can rank low here.", "",
        f"Each rating is pulled toward {pulled} until a team has several games, so early "
        "weeks rank thin evidence. Method: `docs/weekly-ratings-2026-09-23.md`, priors "
        "`docs/weekly-priors-2026-09-23.md`.", "",
        "| Rank | Offense | $O$ | Defense | $D$ | Volume | $P$ |",
        "| ---: | --- | ---: | --- | ---: | --- | ---: |",
        *rows, ""])


def page_data(out: Path) -> dict:
    """{season: {week: {fit, scheduled, mu, nu, rows}}} from every <season>.csv in `out`."""
    seasons = {}
    for csv in sorted(out.glob("*.csv")):
        if not csv.stem.isdigit():
            continue
        weeks = {}
        for week, g in pd.read_csv(csv).groupby("through_week"):
            r0 = g.iloc[0]
            weeks[int(week)] = {
                "method": str(r0["method"]) if "method" in g else "ridge_v1",
                "fit": int(r0["games_fit"]), "scheduled": int(r0["games_scheduled"]),
                "mu": round(float(r0["mu"]), 4), "nu": round(float(r0["nu"]), 4),
                "rows": [[t, int(n), round(o, 3), int(orank), round(d, 3), int(drank), round(p, 3), int(prank)]
                         for t, n, o, orank, d, drank, p, prank
                         in g.sort_values("O_rank")[PAGE_ROW].itertuples(index=False)]}
        seasons[csv.stem] = weeks
    return seasons


def write_page(out: Path) -> None:
    data = json.dumps({"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                       "seasons": page_data(out)}, separators=(",", ":"))
    body = PAGE.read_text(encoding="utf-8").replace("/*DATA*/null", data.replace("</", "<\\/"), 1)
    (out / "artifact.html").write_text(body, encoding="utf-8")
    (out / "index.html").write_text(LOCAL_HEAD + body, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--season", type=int, help="default: latest season with a games file")
    ap.add_argument("--top", type=int, default=10, help="rows to print for the latest week")
    ap.add_argument("--fit", choices=list(METHOD), default="prior_v1")
    args = ap.parse_args(argv)

    from cfb_paths import DATA_ROOT, PROCESSED

    raw = DATA_ROOT / "raw"
    season = args.season or max(int(m[1]) for p in raw.glob("games_*.json")
                                if (m := re.fullmatch(r"games_(\d{4})\.json", p.name)))
    payload = json.loads((raw / f"games_{season}.json").read_text(encoding="utf-8"))
    seasons = [season - 1, season] if args.fit == "prior_v1" else [season]
    games, _ = load(DATA_ROOT, seasons, [])
    prior = season_prior(games, season, DATA_ROOT) if args.fit == "prior_v1" else None
    weeks = season_rankings(games, season, prior)
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
            week_markdown(season, week, r, t, fit, int(sched[week]), args.fit), encoding="utf-8")
        frames.append(t.reset_index(names="team").assign(
            season=season, through_week=week, method=args.fit, mu=r.mu, nu=r.nu, h=r.h,
            lambda_ppp=RIDGE_V1[0], lambda_pace=RIDGE_V1[1],
            games_fit=fit, games_scheduled=int(sched[week])))
    pd.concat(frames, ignore_index=True).to_csv(out / f"{season}.csv", index=False)
    write_page(out)

    week, _, t = weeks[-1]
    print(f"{season} rankings through week {week}: wrote {len(weeks)} week(s) to {out}")
    for col, ascending in RANK_ORDER.items():
        top = t.sort_values(col, ascending=ascending)[col].head(args.top)
        print(f"  {col}: " + ", ".join(f"{team} {v:+.2f}" for team, v in top.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
