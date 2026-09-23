"""Fitted coefficients behind docs/weekly-ratings-2026-09-23.md, printed as Markdown tables.

    python -m scripts.weekly_ratings_coefs

Reads the outputs of `scripts.weekly_ratings_eval` (run that first): tuning losses and
pooled biases from weekly_ratings_eval.json; mu, nu, h, c and team O, D, P from
weekly_ratings_snapshots.csv. Season tables use each season's last cutoff (the most
evidence), with the in-season min-max beside it. The worked game also reads the raw
games, drives and lines files for its actual result and open.
"""
from __future__ import annotations

import json

import pandas as pd

from scripts.weekly_ratings import Ratings, build_games, forecast_total

TEAM_SEASON = 2025
MIN_GAMES = 3
LEAGUE = ["mu", "nu", "h", "c"]
# Navy vs Army, 2025 week 16: the only game forecast from the 2025 last-cutoff snapshot.
EXAMPLE_GAME = 401762521
SHRINK_GAMES = (1, 3, 6, 11)


def md(df: pd.DataFrame) -> str:
    head = [df.index.name or ""] + [str(c) for c in df.columns]
    rows = ["| " + " | ".join(head) + " |", "|" + " --- |" * len(head)]
    rows += ["| " + " | ".join([str(i)] + [str(v) for v in r]) + " |"
             for i, r in zip(df.index, df.itertuples(index=False))]
    return "\n".join(rows)


def ratings_at(snap: pd.DataFrame, season: int, week: int, method: str) -> Ratings:
    """Rebuild one frozen snapshot from its CSV rows."""
    s = snap[(snap["season"] == season) & (snap["as_of_week"] == week) & (snap["method"] == method)]
    r0 = s.iloc[0]
    return Ratings(mu=r0["mu"], nu=r0["nu"], h=r0["h"], c=r0["c"],
                   table=s.set_index("team")[["O", "D", "P", "n_games", "n_possessions"]],
                   unrated=0.0 if method == "ridge_v1" else float("nan"))


def worked_game(snap: pd.DataFrame, data_root) -> None:
    from scripts.weekly_ratings_eval import load_opens

    raw = data_root / "raw"
    games, _ = build_games(json.loads((raw / f"games_{TEAM_SEASON}.json").read_text(encoding="utf-8")),
                           json.loads((raw / f"drives_{TEAM_SEASON}.json").read_text(encoding="utf-8")))
    g = games.set_index("game_id").loc[EXAMPLE_GAME]
    r = ratings_at(snap, TEAM_SEASON, int(g["week"]), "ridge_v1")
    t = r.table
    hh = 0 if g["neutral"] else 1
    n_hat = r.nu + t.at[g["home"], "P"] + t.at[g["away"], "P"]
    ppp_h = r.mu + t.at[g["home"], "O"] + t.at[g["away"], "D"] + r.h * hh
    ppp_a = r.mu + t.at[g["away"], "O"] + t.at[g["home"], "D"] - r.h * hh
    total = n_hat * (ppp_h + ppp_a) + r.c
    assert abs(total - forecast_total(r, g["home"], g["away"], g["neutral"])) < 1e-9

    print(f"## Worked game: {g['home']} vs {g['away']}, {TEAM_SEASON} week {g['week']}, "
          f"neutral={g['neutral']}, ridge_v1\n")
    tab = t.loc[[g["home"], g["away"]], ["O", "D", "P"]].T.apply(lambda col: col.map("{:+.3f}".format))
    tab.loc["n_games"] = t.loc[[g["home"], g["away"]], "n_games"].astype(int).astype(str).to_numpy()
    print(md(tab.rename_axis("rating")), "\n")
    print(f"mu={r.mu:.3f} nu={r.nu:.3f} h={r.h:.3f} (H={hh}) c={r.c:.3f}")
    print(f"N_hat = nu + P_home + P_away = {n_hat:.3f}")
    print(f"PPP_home = {ppp_h:.3f}   PPP_away = {ppp_a:.3f}")
    print(f"regulation points: home {n_hat * ppp_h:.2f}, away {n_hat * ppp_a:.2f}")
    print(f"Total_hat = N_hat * (PPP_home + PPP_away) + c = {total:.2f}")
    raw_r = ratings_at(snap, TEAM_SEASON, int(g["week"]), "raw_v1")
    print(f"raw_v1 total: {forecast_total(raw_r, g['home'], g['away'], g['neutral']):.2f}")
    print(f"Bovada open: {load_opens(data_root, [TEAM_SEASON], []).get(EXAMPLE_GAME)}")
    print(f"actual: {g['home_reg']}-{g['away_reg']} regulation, total {g['total']}; "
          f"possessions {g['home_poss']}/{g['away_poss']} (N={g['N']}); "
          f"PPP {g['home_reg'] / g['home_poss']:.3f} / {g['away_reg'] / g['away_poss']:.3f}\n")


def shrinkage(last: pd.DataFrame, lam_ppp: float, lam_pace: float) -> None:
    """Own-data weight n/(n + lambda) for one team in isolation, and the season-end check."""
    ridge = last[last["method"] == "ridge_v1"]
    per_game = ridge["nu"].mean()
    print(f"## Shrinkage: weight on a team's own adjusted average (possessions/game = {per_game:.2f})\n")
    t = pd.DataFrame({"PPP weight": [f"{g * per_game / (g * per_game + lam_ppp):.2f}"
                                     for g in SHRINK_GAMES],
                      "pace weight": [f"{g / (g + lam_pace):.2f}" for g in SHRINK_GAMES]},
                     index=pd.Index(SHRINK_GAMES, name="games played"))
    print(md(t), "\n")
    rated = last[last["n_games"] >= MIN_GAMES]
    r = rated[rated["method"] == "ridge_v1"]
    n_poss, n_games = r["n_possessions"].mean(), r["n_games"].mean()
    sd = rated.groupby("method")[["O", "D", "P"]].std()
    print(f"season end: mean {n_games:.1f} games, {n_poss:.0f} possessions per team")
    print(f"isolated-team weight: PPP {n_poss / (n_poss + lam_ppp):.2f}, "
          f"pace {n_games / (n_games + lam_pace):.2f}")
    print("ridge/raw SD, pooled score seasons: "
          + ", ".join(f"{c} {sd.at['ridge_v1', c] / sd.at['raw_v1', c]:.2f}" for c in "ODP") + "\n")


def main() -> int:
    from cfb_paths import DATA_ROOT, PROCESSED

    out = PROCESSED / "ratings"
    ev = json.loads((out / "weekly_ratings_eval.json").read_text(encoding="utf-8"))
    snap = pd.read_csv(out / "weekly_ratings_snapshots.csv")
    snap = snap[snap["season"].isin(ev["seasons"]["score"])]
    last = snap[snap["as_of_week"] == snap.groupby("season")["as_of_week"].transform("max")]

    print("## Tuning loss by penalty (tune seasons)\n")
    for k in ("ppp", "pace"):
        loss = pd.Series(ev["tuning"][k]["loss_by_lambda"], dtype=float)
        t = pd.DataFrame({"loss": loss.round(0).astype(int),
                          "above best": (100 * (loss / loss.min() - 1)).map("{:.1f}%".format)})
        print(md(t.rename_axis(f"lambda_{k}")), "\n")

    print("## League coefficients, ridge_v1: last cutoff (in-season min-max)\n")
    ridge = snap[snap["method"] == "ridge_v1"].drop_duplicates(["season", "as_of_week"])
    lo, hi = ridge.groupby("season")[LEAGUE].min(), ridge.groupby("season")[LEAGUE].max()
    end = ridge.loc[ridge.groupby("season")["as_of_week"].idxmax()].set_index("season")
    t = pd.DataFrame({c: [f"{end.at[s, c]:.3f} ({lo.at[s, c]:.2f}-{hi.at[s, c]:.2f})"
                          for s in end.index] for c in LEAGUE}, index=end.index)
    t.insert(0, "as_of_week", end["as_of_week"])
    print(md(t), "\n")

    print(f"## Team rating SD at last cutoff, teams with >= {MIN_GAMES} games\n")
    rated = last[last["n_games"] >= MIN_GAMES]
    sd = rated.groupby(["season", "method"])[["O", "D", "P"]].std().unstack("method")
    sd = sd.apply(lambda col: col.map("{:.3f}".format))
    sd.columns = [f"{r} {m.removesuffix('_v1')}" for r, m in sd.columns]
    sd.insert(0, "teams", rated[rated["method"] == "ridge_v1"].groupby("season").size())
    print(md(sd), "\n")

    print(f"## {TEAM_SEASON} ridge_v1 at last cutoff: three lowest and highest\n")
    tab = last[(last["season"] == TEAM_SEASON) & (last["method"] == "ridge_v1")].set_index("team")
    fmt = lambda s: ", ".join(f"{t} {v:+.2f}" for t, v in s.items())  # noqa: E731
    t = pd.DataFrame({"lowest": [fmt(tab[c].nsmallest(3)) for c in "ODP"],
                      "highest": [fmt(tab[c].nlargest(3)[::-1]) for c in "ODP"]},
                     index=pd.Index(list("ODP"), name="rating"))
    print(md(t), "\n")

    mu, nu, c = (float(end.at[TEAM_SEASON, k]) for k in ("mu", "nu", "c"))
    print(f"## Worked total, {TEAM_SEASON} last cutoff\n")
    print(f"two average teams: 2*mu*nu + c = 2*{mu:.3f}*{nu:.3f} + {c:.3f} = {2 * mu * nu + c:.2f}")
    print(f"+1 point per possession of O (or D): +nu = +{nu:.2f} points")
    print(f"+1 possession per team of P: +2*mu = +{2 * mu:.2f} points\n")

    # OLS identity a = mean(y) - b*mean(x), with y = T - L, x = F - L on the primary games:
    # mean(y) = -bias(open), mean(x) = bias(F) - bias(open). Point estimate; biases are
    # rounded to 3 decimals in the manifest.
    print("## Encompassing regression vs the open, primary population\n")
    acc = ev["results"]["primary"]["accuracy_pooled"]
    enc = ev["results"]["primary"]["encompassing_vs_open"]
    ybar = -acc["open"]["bias"]
    t = pd.DataFrame({f: {"a": f"{ybar - e['slope'] * (acc[f]['bias'] + ybar):+.2f}",
                          "b": f"{e['slope']:.2f}",
                          "b 95%": f"{e['ci95'][0]:.2f} to {e['ci95'][1]:.2f}"}
                      for f, e in enc.items()}).T.rename_axis("forecast")
    print(md(t), "\n")

    shrinkage(last, ev["tuning"]["ppp"]["lambda"], ev["tuning"]["pace"]["lambda"])
    worked_game(snap, DATA_ROOT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
