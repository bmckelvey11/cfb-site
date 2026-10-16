"""Compare tie-free pace statistics against tempo_s (median of integer-second deltas).

    python -m scripts.pace_tiebreak <out_dir>                    # writes two CSVs
    python -m scripts.pace_tiebreak <out_dir> --mean-calibrated  # diagnostic, see below

tempo_s is a median of whole-second deltas, so many teams tie (2026 week 7: 29 distinct
values across 133 rated teams). Candidates per team-season, on neutral post-rush pairs
(scripts.pace_stats.neutral_mask):
  tempo_s     median of deltas (current)
  iqm_s       mean of deltas between the team's own 25th and 75th percentiles
  trim90_s    mean of deltas after dropping deltas > 90 s (and <= 0)
  hl_s        Hodges-Lehmann: median of all pairwise (Walsh) averages
  gmed_s      mean of per-game interpolated medians
  imed_s      interpolated (grouped) median: the median treated as continuous within its 1 s bin
Reliability: split-half (odd vs even games in a team-season, within-season z, Spearman-Brown)
and year-over-year r, on 2014-2026 team-seasons with >= MIN_NEUTRAL pairs.

--mean-calibrated re-shifts wallclock pairs by the trimmed-mean (not median) clock gap. It
showed that mean-based stats still read wallclock-heavy teams fast, which is why imed_s
(with trim90_s as a tiebreak only) is the pick. docs/pace-clock-gaps-2026-10-15.md.
"""
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from cfb_paths import DB_PATH, PROCESSED
from scripts.pace_stats import MIN_NEUTRAL, load_pairs, neutral_mask


def iqm(x):
    lo, hi = np.percentile(x, [25, 75])
    return x[(x >= lo) & (x <= hi)].mean()


def trim90(x):
    return x[(x > 0) & (x <= 90)].mean()


def hl(x):
    x = np.asarray(x, float)
    i, j = np.triu_indices(len(x))
    return np.median((x[i] + x[j]) / 2)


def imed(x):
    """Grouped median for data recorded to whole (or half) seconds, bin width 1 s."""
    x = np.asarray(x, float)
    m = np.median(x)
    lo = np.floor(m + 0.5) - 0.5  # lower edge of the 1 s bin holding the median
    below, inbin = (x < lo).sum(), ((x >= lo) & (x < lo + 1)).sum()
    return lo + (len(x) / 2 - below) / inbin if inbin else m


STATS = {"tempo_s": np.median, "iqm_s": iqm, "trim90_s": trim90, "hl_s": hl, "imed_s": imed}


def recalibrate_for_mean(p: pd.DataFrame) -> pd.DataFrame:
    """Shift wallclock pairs by the season's trimmed-mean clock gap instead of the median one."""
    both = p[p["clock_ok"] & p["wallclock_ok"]]
    keep = lambda s: s[(s > 0) & (s <= 90)].mean()  # noqa: E731
    gap_mean = both.groupby("season").apply(lambda g: keep(g["dwall"]) - keep(g["dclk"]))
    gap_med = (both["dwall"] - both["dclk"]).groupby(both["season"]).median()
    shift = (gap_mean - gap_med).rename("shift")
    print("extra wallclock shift for mean stats (s):", shift.round(2).to_dict())
    p = p.copy()
    wall = p["clock_source"] == "wallclock"
    p.loc[wall, "dclk"] = p.loc[wall, "dclk"] - p.loc[wall, "season"].map(shift).fillna(0)
    return p


def per_team(n: pd.DataFrame) -> pd.DataFrame:
    g = n.groupby(["season", "offense"])["dclk"]
    out = pd.DataFrame({k: g.apply(lambda s, f=f: f(s.to_numpy())) for k, f in STATS.items()})
    out["gmed_s"] = (n.groupby(["season", "offense", "game_id"])["dclk"]
                     .apply(lambda s: imed(s.to_numpy())).groupby(level=[0, 1]).mean())
    out["n_neutral"] = g.size()
    return out[out["n_neutral"] >= MIN_NEUTRAL]


def main(out_dir: Path, mean_calibrated: bool) -> None:
    with duckdb.connect(str(DB_PATH), read_only=True) as con:
        p = load_pairs(con)
    if mean_calibrated:
        p = recalibrate_for_mean(p)
    n = p[neutral_mask(p) & (p["season"] >= 2014)].copy()
    full = per_team(n)
    order = n.groupby(["season", "offense"])["week"].rank(method="dense").astype(int)
    halves = [per_team(n[order % 2 == k]) for k in (0, 1)]
    nxt = full.reset_index().assign(season=lambda d: d["season"] - 1).set_index(["season", "offense"])
    last = int(full.index.get_level_values(0).max())
    rows = {}
    for s in list(STATS) + ["gmed_s"]:
        a, b = halves[0][s].align(halves[1][s], join="inner")
        za = a.groupby(level=0).transform(lambda c: (c - c.mean()) / c.std())
        zb = b.groupby(level=0).transform(lambda c: (c - c.mean()) / c.std())
        r = za.corr(zb)
        cur, fut = full[s].align(nxt[s], join="inner")
        latest = full.loc[last, s]
        rows[s] = {"split_half_r": r, "full_season_r": 2 * r / (1 + r), "yoy_r": cur.corr(fut),
                   "r_with_tempo_s": full[s].corr(full["tempo_s"]),
                   f"teams_{last}": len(latest), f"distinct_{last}": latest.round(2).nunique(),
                   f"teams_in_ties_{last}": int(latest.round(2).duplicated(keep=False).sum())}
    rel = pd.DataFrame(rows).T
    print(rel.round(3).to_string())
    t = full.loc[last].copy()
    hurry = pd.read_csv(PROCESSED / "pace" / "pace_team_season.csv")
    t["hurry_rate"] = hurry[hurry["season"] == last].set_index("team")["hurry_rate"]
    t["pace_rank"] = t[["imed_s", "trim90_s"]].apply(tuple, axis=1).rank(method="first").astype(int)
    tag = "_meancal" if mean_calibrated else ""
    out_dir.mkdir(parents=True, exist_ok=True)
    t.round(2).to_csv(out_dir / f"pace_tiebreak_{last}{tag}.csv", index_label="team")
    rel.round(4).to_csv(out_dir / f"pace_tiebreak_reliability{tag}.csv")


if __name__ == "__main__":
    main(Path(sys.argv[1]), "--mean-calibrated" in sys.argv)
