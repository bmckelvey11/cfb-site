"""Regenerate cfb_system_maker/coach_style.py from raw CFBD advanced season stats.

Offline generator — needs pandas, numpy, scikit-learn (not runtime deps of the
package). Method (see .planning/quick/260827-coach-style-cluster-feature/):

1. Load advanced_season_stats_{2016..2024}.json + coaches_{...}.json from data/raw.
   (Havoc splits are constant/broken pre-2016; 2025 lacks havoc entirely.)
2. 13 style features per team-season, z-scored within season (era-adjust).
3. Residualize each feature on same-season SP+ overall (strip team quality, so
   clusters group style, not "being good").
4. Aggregate per head coach, games-weighted, coaches with >= 3 seasons only.
5. k-means k=5 (random_state=0). Cluster names assigned by profile signature,
   not cluster index, so regeneration is label-stable:
   min pass rate -> option_ground; then max def stuff -> attack_defense; then
   min def explosiveness allowed -> bend_dont_break; then max off success rate
   -> pass_first_efficient; remainder -> balanced_spread.

Usage: python scripts/build_coach_style_clusters.py [--data-dir data]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

SEASONS = range(2016, 2025)
FEATS = [
    "tempo", "off_pass_rate", "off_expl", "off_sr", "off_line_yds",
    "off_pts_per_opp", "off_havoc_allowed", "off_pd_rate",
    "def_havoc", "def_sr", "def_expl", "def_stuff", "def_line_yds",
]
MIN_SEASONS = 3
K = 5


def _get(d, *path):
    for p in path:
        d = d.get(p) if isinstance(d, dict) else None
    return d


def build_team_seasons(raw: Path) -> pd.DataFrame:
    rows = []
    for y in SEASONS:
        for r in json.loads((raw / f"advanced_season_stats_{y}.json").read_text(encoding="utf-8")):
            o, d = r.get("offense") or {}, r.get("defense") or {}
            rows.append(dict(
                season=y, team=r["team"],
                off_plays=_get(o, "plays"),
                off_pass_rate=_get(o, "passingPlays", "rate"),
                off_expl=_get(o, "explosiveness"),
                off_sr=_get(o, "successRate"),
                off_line_yds=_get(o, "lineYards"),
                off_pts_per_opp=_get(o, "pointsPerOpportunity"),
                off_havoc_allowed=_get(o, "havoc", "total"),
                off_pd_rate=_get(o, "passingDowns", "rate"),
                def_havoc=_get(d, "havoc", "total"),
                def_sr=_get(d, "successRate"),
                def_expl=_get(d, "explosiveness"),
                def_stuff=_get(d, "stuffRate"),
                def_line_yds=_get(d, "lineYards"),
            ))
    return pd.DataFrame(rows)


def attach_coaches(ts: pd.DataFrame, raw: Path) -> pd.DataFrame:
    cmap: dict[tuple[int, str], tuple[str, int, float | None]] = {}
    for y in SEASONS:
        for c in json.loads((raw / f"coaches_{y}.json").read_text(encoding="utf-8")):
            name = f"{c.get('firstName', '')} {c.get('lastName', '')}".strip()
            for s in c.get("seasons") or []:
                if s.get("year") != y:
                    continue
                key = (y, s["school"])
                games = s.get("games") or 0
                if key not in cmap or games > cmap[key][1]:
                    cmap[key] = (name, games, s.get("spOverall"))
    ts = ts.copy()
    ts["coach"] = [(cmap.get((y, t)) or (None,))[0] for y, t in zip(ts.season, ts.team)]
    ts["games"] = [(cmap.get((y, t)) or (None, np.nan))[1] for y, t in zip(ts.season, ts.team)]
    ts["sp_overall"] = [(cmap.get((y, t)) or (None, None, None))[2] for y, t in zip(ts.season, ts.team)]
    ts = ts.dropna(subset=["coach", "sp_overall"])
    ts = ts[ts.games >= 6]  # drop interim-coach stubs
    ts["tempo"] = ts.off_plays / ts.games
    return ts.dropna(subset=FEATS)


def coach_matrix(ts: pd.DataFrame) -> pd.DataFrame:
    z = ts.copy()
    for f in FEATS + ["sp_overall"]:
        z[f] = ts.groupby("season")[f].transform(lambda s: (s - s.mean()) / s.std(ddof=0))
    q = z["sp_overall"].values
    for f in FEATS:  # strip quality
        b = np.polyfit(q, z[f].values, 1)
        z[f] = z[f].values - np.polyval(b, q)

    def agg(gr):
        out = {f: np.average(gr[f], weights=gr.games) for f in FEATS}
        out["seasons"] = len(gr)
        return pd.Series(out)

    coach = z.groupby("coach").apply(agg, include_groups=False)
    return coach[coach.seasons >= MIN_SEASONS]


def name_clusters(profiles: pd.DataFrame) -> dict[int, str]:
    remaining = list(profiles.index)
    names: dict[int, str] = {}
    for rule, label in [
        (lambda p: p.off_pass_rate.idxmin(), "option_ground"),
        (lambda p: p.def_stuff.idxmax(), "attack_defense"),
        (lambda p: p.def_expl.idxmin(), "bend_dont_break"),
        (lambda p: p.off_sr.idxmax(), "pass_first_efficient"),
    ]:
        pick = rule(profiles.loc[remaining])
        names[pick] = label
        remaining.remove(pick)
    names[remaining[0]] = "balanced_spread"
    return names


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data")
    args = parser.parse_args()
    raw = Path(args.data_dir) / "raw"

    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler

    coach = coach_matrix(attach_coaches(build_team_seasons(raw), raw))
    X = StandardScaler().fit_transform(coach[FEATS].astype(float).values)
    km = KMeans(n_clusters=K, n_init=25, random_state=0).fit(X)
    coach["cluster"] = km.labels_
    names = name_clusters(coach.groupby("cluster")[FEATS].mean())
    mapping = {c: names[k] for c, k in coach.cluster.sort_index().items()}

    module = Path(__file__).resolve().parent.parent / "cfb_system_maker" / "coach_style.py"
    lines = [
        '"""Coach playstyle cluster labels. GENERATED by scripts/build_coach_style_clusters.py',
        "",
        "k=5 k-means over quality-stripped advanced season stats, 2016-2024, coaches with",
        ">= 3 seasons. Career-level label (result_lookahead: early games see a label",
        'informed by later seasons). Do not edit by hand."""',
        "",
        "COACH_STYLE_CLUSTERS: dict[str, str] = {",
    ]
    lines += [f"    {name!r}: {label!r}," for name, label in mapping.items()]
    lines += ["}", ""]
    module.write_text("\n".join(lines), encoding="utf-8")
    counts = pd.Series(mapping).value_counts()
    print(f"wrote {module} ({len(mapping)} coaches)")
    print(counts.to_string())


if __name__ == "__main__":
    main()
