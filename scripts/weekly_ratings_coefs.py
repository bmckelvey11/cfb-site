"""Fitted coefficients behind docs/weekly-ratings-2026-09-23.md, printed as Markdown tables.

    python -m scripts.weekly_ratings_coefs

Reads the outputs of `scripts.weekly_ratings_eval` (run that first): tuning losses and
pooled biases from weekly_ratings_eval.json; mu, nu, h, c and team O, D, P from
weekly_ratings_snapshots.csv. Season tables use each season's last cutoff (the most
evidence), with the in-season min-max beside it.
"""
from __future__ import annotations

import json

import pandas as pd

TEAM_SEASON = 2025
MIN_GAMES = 3
LEAGUE = ["mu", "nu", "h", "c"]


def md(df: pd.DataFrame) -> str:
    head = [df.index.name or ""] + [str(c) for c in df.columns]
    rows = ["| " + " | ".join(head) + " |", "|" + " --- |" * len(head)]
    rows += ["| " + " | ".join([str(i)] + [str(v) for v in r]) + " |"
             for i, r in zip(df.index, df.itertuples(index=False))]
    return "\n".join(rows)


def main() -> int:
    from cfb_paths import PROCESSED

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
    print(md(t))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
