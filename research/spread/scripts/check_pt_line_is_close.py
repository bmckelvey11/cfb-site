"""Is Prediction Tracker's `line` the closing spread? (review 2026-09-08 §1.4)

Every movement number treats PT's `line` as the close. This joins the 2024-25 archive rows to
Action Network's consensus close (book 15, scoreboard snapshot of a completed game) on
(season, home, road) -- rematched pairs dropped -- and reports how far apart they are.
`lineopen` is compared the same way for scale.

    python research/spread/scripts/check_pt_line_is_close.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_prediction_tracker_models as base  # noqa: E402
import eval_version_b as vb  # noqa: E402
from weekly_slate import norm  # noqa: E402

SEASONS = (2024, 2025)
OUT = base.OUT_DIR / "pt_line_vs_an_close.json"
PREDS_WF = base.OUT_DIR / "pt_movement_preds_decon_wf.csv"


def an_closes() -> pd.DataFrame:
    con = duckdb.connect(str(base.cfb_paths.DB_PATH), read_only=True)
    df = con.sql(f"""
        select sb.event_id, sb.season, sb.start_time, sb.teams, sb.home_team_id,
               m.line as close_an
        from stg.an_scoreboard sb join stg.an_market m using (event_id)
        where m.book_id = 15 and m.market_type = 'spread' and m.period = 'event'
          and m.side = 'home' and not coalesce(m.is_live, false)
          and coalesce(m.line_status, 'normal') = 'normal'
          and sb.status = 'complete' and sb.season in {SEASONS}
    """).df().drop_duplicates("event_id")
    home, road = [], []
    for teams, hid in zip(df.teams, df.home_team_id):
        t = {x["id"]: x.get("display_name", "") for x in json.loads(teams)}
        home.append(norm(t.get(hid, "")))
        road.append(norm(next((v for k, v in t.items() if k != hid), "")))
    df["key"], df["rkey"] = home, road
    df["season"] = df.season.astype(int)
    return df[["event_id", "season", "key", "rkey", "close_an"]]


def main() -> int:
    pt, _ = base.load()
    pt = pt[pt.season.isin(SEASONS) & pt.line.notna()].copy()
    pt["key"], pt["rkey"] = pt.home.map(norm), pt.road.map(norm)
    pt["pt_close"], pt["pt_open"] = -pt.line.astype(float), -pt.lineopen.astype(float)   # archive -> PT sign
    an = an_closes()
    an["an_close_pt"] = -an.close_an.astype(float)                                       # AN -> PT sign
    # The archive carries no date for these seasons, so a rematch (same pair twice in a
    # season) cannot be disambiguated; drop those pairs on both sides rather than guess.
    k = ["season", "key", "rkey"]
    pt = pt[~pt.duplicated(k, keep=False)]
    an = an[~an.duplicated(k, keep=False)]
    j = pt.merge(an, on=k)
    d = (j.pt_close - j.an_close_pt).abs()
    d_open = (j.pt_open - j.an_close_pt).abs()
    out = {"pt_rows": int(len(pt)), "an_rows": int(len(an)), "matched": int(len(j)),
           "line_vs_close": {"mean_abs": float(d.mean()), "median_abs": float(d.median()),
                             "exact": float((d == 0).mean()), "within_0.5": float((d <= 0.5).mean()),
                             "within_1": float((d <= 1).mean())},
           "open_vs_close": {"mean_abs": float(d_open.mean()), "within_0.5": float((d_open <= 0.5).mean())}}

    # Amendment A5: does E4's disagreement with PT's `line` predict the AN_close - PT_line move
    # that happens after PT's last capture? Walk-forward decontaminated predictions (amendment
    # A6) -- not the full-sample `_decon` file, whose screen saw its own test set. E4/E6/E14 are
    # themselves fitted first-stage predictions, so every interval below is conditional on the
    # fitted predictor (cluster_ols's SE does not propagate the first stage's uncertainty).
    # preds are -line (archive/margin sign) -- the same space eval_line_movement.py fits `y` in,
    # and the same space pt_close is already computed in below, so subtracting pt_close from
    # either side keeps both terms in one convention.
    preds = pd.read_csv(PREDS_WF)
    jj = j.merge(preds[["game_id", "E4", "E6", "E14"]], on="game_id")
    y = (jj.an_close_pt - jj.pt_close).to_numpy(float)
    cl = jj.wk.to_numpy(int)
    out["after_capture"] = {"note": "exploratory (not the tree's confirmatory hypothesis); every "
                             "slope below is conditional_on_fitted_predictor -- see amendment A5"}
    print("\nA5  slope of (AN close - PT line) on (pred - PT line), walk-forward decon (A6), "
          "season-week clusters -- CI conditional on the fitted predictor, exploratory")
    for p in ("E4", "E6", "E14"):
        x = (jj[p] - jj.pt_close).to_numpy(float)
        ok = np.isfinite(x) & np.isfinite(y)
        r = vb.cluster_ols(y[ok], x[ok], cl[ok], conditional_on_fitted_predictor=True)
        out["after_capture"][p] = r
        print(f"  {p:4s} slope {r['slope']:+.3f} [{r['lo']:+.3f}, {r['hi']:+.3f}]  n {r['n']}  "
              f"clusters {r['clusters']}  se_kind {r['se_kind']}")

    print(f"PT rows {len(pt)}, AN completed games with a consensus close {len(an)}, matched {len(j)}")
    print(f"|PT line - AN close|: mean {d.mean():.2f}  median {d.median():.2f}  exact {(d == 0).mean():.1%}  "
          f"within 0.5 {(d <= 0.5).mean():.1%}  within 1 {(d <= 1).mean():.1%}")
    print(f"|PT open - AN close|: mean {d_open.mean():.2f}  within 0.5 {(d_open <= 0.5).mean():.1%}   (scale)")
    worst = j.assign(d=d).nlargest(5, "d")[["season", "home", "road", "pt_close", "an_close_pt", "d"]]
    print("\nlargest gaps:\n" + worst.to_string(index=False))
    OUT.write_text(json.dumps(out, indent=2))
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
