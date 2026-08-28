"""Coach playstyle analysis: cluster validity, prevalence, and a walk-forward market test.

Re-runnable study behind docs/coach-playstyle-analysis.md. Needs pandas, numpy,
scikit-learn, scipy, matplotlib (none are runtime deps of the package). Imports the
committed label generator so the feature matrix has exactly one definition.

Writes eight charts to docs/img/coach-style-*.png and prints every number quoted in
the note. Reads data/ only; changes nothing else.

Usage: python scripts/analyze_coach_styles.py [--data-dir data]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from scipy import stats as sps
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

parser = argparse.ArgumentParser()
parser.add_argument("--data-dir", default="data")
args = parser.parse_args()
DATA = (REPO / args.data_dir) if not Path(args.data_dir).is_absolute() else Path(args.data_dir)
RAW = DATA / "raw"
OUT = REPO / "docs" / "img"
OUT.mkdir(parents=True, exist_ok=True)

spec = importlib.util.spec_from_file_location(
    "bcsc", REPO / "scripts" / "build_coach_style_clusters.py"
)
bcsc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bcsc)

from cfb_system_maker.backtest import _icc_one_way, _wilson_interval
from cfb_system_maker.coach_style import COACH_STYLE_CLUSTERS

FEATS = bcsc.FEATS
STYLES = ["option_ground", "attack_defense", "bend_dont_break",
          "pass_first_efficient", "balanced_spread"]
# two-line variants for tick labels on narrow axes
PRETTY = {"option_ground": "Option /\nGround", "attack_defense": "Attack\nDefense",
          "bend_dont_break": "Bend-Don't-\nBreak",
          "pass_first_efficient": "Pass-First\nEfficient",
          "balanced_spread": "Balanced\nSpread"}
FLAT = {"option_ground": "Option / Ground", "attack_defense": "Attack Defense",
        "bend_dont_break": "Bend-Don't-Break", "pass_first_efficient": "Pass-First Efficient",
        "balanced_spread": "Balanced Spread"}
COLORS = {"option_ground": "#2E7D5B", "attack_defense": "#B3402F",
          "bend_dont_break": "#3F6DA8", "pass_first_efficient": "#8B5FA8",
          "balanced_spread": "#8A8A8A"}
FEAT_LABEL = {
    "tempo": "Tempo (plays/game)", "off_pass_rate": "Pass rate",
    "off_expl": "Off explosiveness", "off_sr": "Off success rate",
    "off_line_yds": "Off line yards", "off_pts_per_opp": "Points per opportunity",
    "off_havoc_allowed": "Havoc allowed (off)", "off_pd_rate": "Passing-down rate",
    "def_havoc": "Def havoc", "def_sr": "Def success rate allowed",
    "def_expl": "Def explosiveness allowed", "def_stuff": "Def stuff rate",
    "def_line_yds": "Def line yards allowed",
}
BREAK_EVEN = 0.5238  # -110 pricing
PLUM = "#5B4B8A"
INK = "#1C1C1E"
GRID = "#D8D6D1"
R: dict = {}

# ---------------------------------------------------------------- build base
ts_all = bcsc.attach_coaches(bcsc.build_team_seasons(RAW), RAW)
print(f"team-seasons: {len(ts_all)}  coaches: {ts_all.coach.nunique()}")


def zresid(ts: pd.DataFrame) -> pd.DataFrame:
    """Within-season z-score, then residualize on same-season SP+ (strip quality)."""
    z = ts.copy()
    for f in FEATS + ["sp_overall"]:
        z[f] = ts.groupby("season")[f].transform(lambda s: (s - s.mean()) / s.std(ddof=0))
    q = z["sp_overall"].values
    for f in FEATS:
        b = np.polyfit(q, z[f].values, 1)
        z[f] = z[f].values - np.polyval(b, q)
    return z


z_all = zresid(ts_all)
career = bcsc.coach_matrix(ts_all)
X = StandardScaler().fit_transform(career[FEATS].astype(float).values)
km = KMeans(n_clusters=bcsc.K, n_init=25, random_state=0).fit(X)
career["cluster"] = km.labels_
names = bcsc.name_clusters(career.groupby("cluster")[FEATS].mean())
career["style_label"] = career.cluster.map(names)
assert dict(career.style_label) == {k: v for k, v in COACH_STYLE_CLUSTERS.items()}, "drift vs shipped module"

R["n_team_seasons"] = int(len(ts_all))
R["n_coaches_all"] = int(ts_all.coach.nunique())
R["n_coaches_labeled"] = int(len(career))
R["style_counts"] = career.style_label.value_counts().to_dict()

# --------------------------------------------------- 1. cluster profiles
prof = career.groupby("style_label")[FEATS].mean().reindex(STYLES)
R["profiles"] = prof.round(3).to_dict("index")

# separation: how far apart are centroids vs within-cluster spread
cent = career.groupby("style_label")[FEATS].mean()
within = career.groupby("style_label")[FEATS].std().mean(axis=1).mean()
between = np.mean([np.linalg.norm(cent.loc[a] - cent.loc[b])
                   for i, a in enumerate(STYLES) for b in STYLES[i + 1:]])
R["separation"] = {"mean_within_sd": round(float(within), 3),
                   "mean_between_dist": round(float(between), 3)}

# --------------------------------------------------- 2. PCA
pca = PCA()
P = pca.fit_transform(X)
career["pc1"], career["pc2"] = P[:, 0], P[:, 1]
R["pca_evr"] = [round(float(v), 4) for v in pca.explained_variance_ratio_[:5]]
R["pca_loadings"] = pd.DataFrame(
    pca.components_[:2].T, index=FEATS, columns=["PC1", "PC2"]
).round(3).to_dict("index")

# --------------------------------------------------- 3. season stability
# assign each coach-season to its nearest CAREER centroid, then ask how often a
# coach's individual seasons land in that coach's own career cluster.
scaler = StandardScaler().fit(career[FEATS].astype(float).values)
cent_s = scaler.transform(cent.reindex(STYLES).values)
seasons_lab = z_all[z_all.coach.isin(career.index)].copy()
Sx = scaler.transform(seasons_lab[FEATS].astype(float).values)
d = np.linalg.norm(Sx[:, None, :] - cent_s[None, :, :], axis=2)
seasons_lab["season_style"] = [STYLES[i] for i in d.argmin(axis=1)]
seasons_lab["career_style"] = seasons_lab.coach.map(career.style_label)
seasons_lab["match"] = seasons_lab.season_style == seasons_lab.career_style

overall_stab = float(seasons_lab.match.mean())
by_style_stab = seasons_lab.groupby("career_style").match.mean().reindex(STYLES)
# chance baseline = sum of squared style shares among coach-seasons
shares = seasons_lab.career_style.value_counts(normalize=True)
chance = float((shares ** 2).sum())
R["stability"] = {
    "overall": round(overall_stab, 3),
    "chance_baseline": round(chance, 3),
    "by_style": by_style_stab.round(3).to_dict(),
    "n_coach_seasons": int(len(seasons_lab)),
}
# per-coach: fraction of own seasons in own career cluster
per_coach = seasons_lab.groupby("coach").match.mean()
R["stability"]["coaches_fully_consistent"] = int((per_coach == 1.0).sum())
R["stability"]["coaches_majority_consistent"] = int((per_coach > 0.5).sum())
R["stability"]["n_coaches"] = int(len(per_coach))

# --------------------------------------------------- 4. prevalence over time
prev = (seasons_lab.groupby(["season", "season_style"]).size()
        .unstack(fill_value=0).reindex(columns=STYLES, fill_value=0))
prev_pct = prev.div(prev.sum(axis=1), axis=0)
R["prevalence"] = prev_pct.round(4).to_dict("index")
# trend test per style: Spearman of share vs season
from scipy import stats as sps
R["prevalence_trend"] = {
    s: {"rho": round(float(sps.spearmanr(prev_pct.index, prev_pct[s]).statistic), 3),
        "p": round(float(sps.spearmanr(prev_pct.index, prev_pct[s]).pvalue), 4)}
    for s in STYLES
}

# --------------------------------------------------- 5. conference composition
conf_map = {}
for y in bcsc.SEASONS:
    for r in json.loads((RAW / f"advanced_season_stats_{y}.json").read_text(encoding="utf-8")):
        conf_map[(y, r["team"])] = r.get("conference")
seasons_lab["conference"] = [conf_map.get((y, t)) for y, t in zip(seasons_lab.season, seasons_lab.team)]
P5 = {"SEC", "Big Ten", "ACC", "Big 12", "Pac-12"}
seasons_lab["tier"] = np.where(seasons_lab.conference.isin(P5), "Power 5",
                               np.where(seasons_lab.conference == "FBS Independents", "Independent", "Group of 5"))
conf_tab = pd.crosstab(seasons_lab.career_style, seasons_lab.tier, normalize="index").reindex(STYLES)
R["conference_mix"] = conf_tab.round(4).to_dict("index")
chi2, chi_p, _, _ = sps.chi2_contingency(pd.crosstab(seasons_lab.career_style, seasons_lab.tier))
R["conference_chi2"] = {"chi2": round(float(chi2), 2), "p": float(chi_p)}

# --------------------------------------------------- 6. WALK-FORWARD labels
# For season S: fit on seasons < S only (>=3 seasons per coach in that window),
# so a season-S game reads a label built entirely from prior years.
wf_rows = []
wf_agree = []
for S in range(2019, 2025):
    win = ts_all[ts_all.season < S]
    zw = zresid(win)

    def agg(gr):
        out = {f: np.average(gr[f], weights=gr.games) for f in FEATS}
        out["seasons"] = len(gr)
        return pd.Series(out)

    cm = zw.groupby("coach").apply(agg, include_groups=False)
    cm = cm[cm.seasons >= 3]
    if len(cm) < 20:
        continue
    sc = StandardScaler().fit(cm[FEATS].astype(float).values)
    Xw = sc.transform(cm[FEATS].astype(float).values)
    kmw = KMeans(n_clusters=bcsc.K, n_init=25, random_state=0).fit(Xw)
    cm["cluster"] = kmw.labels_
    nm = bcsc.name_clusters(cm.groupby("cluster")[FEATS].mean())
    cm["style_label"] = cm.cluster.map(nm)
    for coach, style in cm.style_label.items():
        wf_rows.append({"season": S, "coach": coach, "wf_style": style})
        if coach in career.index:
            wf_agree.append(style == career.style_label[coach])

wf = pd.DataFrame(wf_rows)
R["walk_forward"] = {
    "seasons": [int(s) for s in sorted(wf.season.unique())],
    "n_coach_seasons": int(len(wf)),
    "agreement_with_career_label": round(float(np.mean(wf_agree)), 3),
}
print("walk-forward labels:", len(wf), "agreement:", R["walk_forward"]["agreement_with_career_label"])

# map (season, team) -> walk-forward style via the coach of that team-season
coach_of = {(y, t): c for y, t, c in zip(ts_all.season, ts_all.team, ts_all.coach)}
wf_lookup = {(r.season, r.coach): r.wf_style for r in wf.itertuples()}

# --------------------------------------------------- 7. games + outcomes
g = pd.read_csv(DATA / "processed" / "games.csv")
g = g[(g.season >= 2019) & (g.season <= 2024)].copy()
g = g[g.home_points.notna() & g.away_points.notna()]


def style_for(season, team):
    c = coach_of.get((season, team))
    return wf_lookup.get((season, c)) if c else None


g["home_style"] = [style_for(s, t) for s, t in zip(g.season, g.home_team)]
g["away_style"] = [style_for(s, t) for s, t in zip(g.season, g.away_team)]
g["home_coach"] = [coach_of.get((s, t)) for s, t in zip(g.season, g.home_team)]
g["away_coach"] = [coach_of.get((s, t)) for s, t in zip(g.season, g.away_team)]
g["margin"] = g.home_points - g.away_points
g["total_points"] = g.home_points + g.away_points

R["games"] = {
    "n_2019_2024": int(len(g)),
    "n_home_labeled": int(g.home_style.notna().sum()),
    "n_either_labeled": int((g.home_style.notna() | g.away_style.notna()).sum()),
}

# ---- team-slot ATS rows (each game contributes home row + away row; the two
# are exact mirrors on cover, so the pooled base rate is 50% by identity --
# style splits are still informative, the mirror is disclosed).
rows = []
sp = g[g.spread.notna()]
for r in sp.itertuples():
    for side in ("home", "away"):
        style = r.home_style if side == "home" else r.away_style
        coach = r.home_coach if side == "home" else r.away_coach
        if style is None or (isinstance(style, float) and math.isnan(style)):
            continue
        side_spread = r.spread if side == "home" else -r.spread
        pts = r.home_points if side == "home" else r.away_points
        opp = r.away_points if side == "home" else r.home_points
        cover = pts + side_spread - opp
        if cover == 0:
            continue  # push
        rows.append({"season": r.season, "style_label": style, "coach": coach,
                     "win": int(cover > 0), "side": side,
                     "spread": side_spread, "fav": side_spread < 0})
ats = pd.DataFrame(rows)
R["ats"] = {"n_decided_team_slots": int(len(ats))}


def clustered_test(sub: pd.DataFrame, p0: float) -> dict:
    """Hit rate with coach-clustered inference: Wilson CI widened by DEFF from
    the coach-level ICC, plus a z-test on the effective n."""
    n = len(sub)
    if n == 0:
        return {}
    hits = int(sub.win.sum())
    p = hits / n
    groups = [list(gr.win.astype(float)) for _, gr in sub.groupby("coach") if len(gr) > 0]
    icc = _icc_one_way(groups)
    m = n / max(1, len(groups))
    deff = 1 + (m - 1) * max(0.0, icc)
    n_eff = n / deff if deff > 0 else n
    lo, hi = _wilson_interval(p, max(1, int(round(n_eff))))
    se = math.sqrt(p0 * (1 - p0) / n_eff) if n_eff > 0 else float("inf")
    zsc = (p - p0) / se if se > 0 else 0.0
    pval = 2 * (1 - sps.norm.cdf(abs(zsc)))
    return {"n": n, "hits": hits, "rate": round(p, 4), "icc": round(icc, 4),
            "deff": round(deff, 2), "n_eff": round(n_eff, 1),
            "ci": [lo, hi], "z": round(float(zsc), 3), "p": round(float(pval), 4),
            "n_coaches": len(groups)}


ats_by_style = {s: clustered_test(ats[ats.style_label == s], BREAK_EVEN) for s in STYLES}
R["ats_by_style"] = ats_by_style

# ---- totals: game-level, one row per game (no mirror problem)
tot = g[g.total.notna() & (g.home_style.notna() | g.away_style.notna())].copy()
tot = tot[tot.total_points != tot.total]  # drop pushes
tot["over"] = (tot.total_points > tot.total).astype(int)
tot["n_option"] = ((tot.home_style == "option_ground").astype(int)
                   + (tot.away_style == "option_ground").astype(int))

R["totals"] = {"n_decided_games": int(len(tot)),
               "pooled_over_rate": round(float(tot.over.mean()), 4)}

# market pricing check: raw scoring environment vs the posted number vs over rate
mk = []
for s in STYLES:
    sub = tot[(tot.home_style == s) | (tot.away_style == s)].copy()
    if len(sub) < 50:
        continue
    sub2 = sub.rename(columns={"over": "win"})
    sub2["coach"] = np.where(sub2.home_style == s, sub2.home_coach, sub2.away_coach)
    t = clustered_test(sub2, BREAK_EVEN)
    mk.append({"style": s, "n": int(len(sub)),
               "mean_total_line": round(float(sub.total.mean()), 2),
               "mean_points_scored": round(float(sub.total_points.mean()), 2),
               "over_rate": round(float(sub.over.mean()), 4),
               "test": t})
R["totals_by_style"] = mk
R["totals_market_baseline"] = {"mean_total_line": round(float(tot.total.mean()), 2),
                              "mean_points": round(float(tot.total_points.mean()), 2)}

# ---- 5x5 matchup grid (exploratory): home-slot cover rate by (home, away) style
grid_n = pd.DataFrame(0, index=STYLES, columns=STYLES, dtype=int)
grid_r = pd.DataFrame(np.nan, index=STYLES, columns=STYLES)
hs = ats[ats.side == "home"].copy()
hs = hs.merge(sp[["game_id", "home_style", "away_style"]],
              left_index=True, right_index=True, how="left") if False else hs
# rebuild directly from games for the grid
gg = sp[sp.home_style.notna() & sp.away_style.notna()].copy()
gg["cover"] = gg.home_points + gg.spread - gg.away_points
gg = gg[gg.cover != 0]
gg["hwin"] = (gg.cover > 0).astype(int)
for a in STYLES:
    for b in STYLES:
        sub = gg[(gg.home_style == a) & (gg.away_style == b)]
        grid_n.loc[a, b] = len(sub)
        if len(sub) >= 30:
            grid_r.loc[a, b] = sub.hwin.mean()
R["matchup_grid_n"] = grid_n.to_dict("index")
R["matchup_grid_rate"] = grid_r.round(4).where(grid_r.notna(), None).to_dict("index")

# ---- multiple comparison correction over the primary family
fam = [("ats", s, ats_by_style[s]["p"]) for s in STYLES if ats_by_style[s]]
fam += [("totals", m["style"], m["test"]["p"]) for m in mk if m["test"]]
pv = np.array([f[2] for f in fam])
order = np.argsort(pv)
holm = np.empty_like(pv)
running = 0.0
for rank, idx in enumerate(order):
    adj = (len(pv) - rank) * pv[idx]
    running = max(running, adj)
    holm[idx] = min(1.0, running)
R["multiplicity"] = {
    "n_tests": len(pv),
    "results": [{"family": f[0], "style": f[1], "p_raw": round(float(f[2]), 4),
                 "p_holm": round(float(h), 4)} for f, h in zip(fam, holm)],
    "any_significant_after_holm": bool((holm < 0.05).any()),
}



# ================================================================= CHARTS
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10,
    "axes.edgecolor": "#3A3A3C", "axes.labelcolor": INK, "text.color": INK,
    "xtick.color": "#3A3A3C", "ytick.color": "#3A3A3C",
    "axes.spines.top": False, "axes.spines.right": False,
    "figure.facecolor": "white", "axes.facecolor": "white",
})
DIVERGE = LinearSegmentedColormap.from_list("dv", ["#2C6E8F", "#EDEAE3", "#B3402F"])


def save(fig, name):
    path = OUT / f"coach-style-{name}.png"
    fig.savefig(path, format="png", dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  {path.relative_to(REPO)}  ({path.stat().st_size // 1024} KB)")


# ---- 1. profile heatmap
prof = pd.DataFrame(R["profiles"]).T.reindex(STYLES)[FEATS]
fig, ax = plt.subplots(figsize=(10.5, 5.4))
v = np.abs(prof.values).max()
im = ax.imshow(prof.values, cmap=DIVERGE, vmin=-v, vmax=v, aspect="auto")
ax.set_xticks(range(len(FEATS)))
ax.set_xticklabels([FEAT_LABEL[f] for f in FEATS], rotation=42, ha="right", fontsize=9)
ax.set_yticks(range(len(STYLES)))
ax.set_yticklabels([FLAT[s] for s in STYLES], fontsize=10)
for i in range(len(STYLES)):
    for j in range(len(FEATS)):
        val = prof.values[i, j]
        ax.text(j, i, f"{val:+.1f}", ha="center", va="center", fontsize=8,
                color="white" if abs(val) > v * 0.55 else INK)
ax.set_title("Cluster profiles — mean quality-stripped z-score per feature",
             fontsize=12, pad=12, loc="left")
cb = fig.colorbar(im, ax=ax, fraction=0.02, pad=0.015)
cb.set_label("SD vs league average (quality removed)", fontsize=8)
cb.ax.tick_params(labelsize=8)
save(fig, "profiles")

# ---------------------------------------------------- 2. PCA scatter
notable = ["Nick Saban", "Kirby Smart", "Lincoln Riley", "Mike Leach", "Jeff Monken",
           "Ken Niumatalolo", "Jim Harbaugh", "Pat Narduzzi", "Kirk Ferentz",
           "Lane Kiffin", "Mike Gundy", "Dabo Swinney", "Gary Patterson",
           "Kyle Whittingham", "P.J. Fleck", "Sonny Dykes", "Gus Malzahn",
           "David Shaw", "Paul Johnson", "Jamey Chadwell"]
fig, ax = plt.subplots(figsize=(10, 7))
for s in STYLES:
    sub = career[career.style_label == s]
    ax.scatter(sub.pc1, sub.pc2, s=42, color=COLORS[s], alpha=0.72,
               edgecolor="white", linewidth=0.6, label=f"{FLAT[s]} (n={len(sub)})")
for n in notable:
    if n in career.index:
        r = career.loc[n]
        ax.annotate(n, (r.pc1, r.pc2), fontsize=7.5, alpha=0.9,
                    xytext=(4, 3), textcoords="offset points")
ax.axhline(0, color=GRID, lw=0.8, zorder=0)
ax.axvline(0, color=GRID, lw=0.8, zorder=0)
ax.set_xlabel("PC1 (31.7%)  —  chaotic / behind-schedule  →  methodical / efficient")
ax.set_ylabel("PC2 (25.0%)  —  stout front  →  soft front")
ax.set_title("Style space: 189 coaches, quality stripped out",
             fontsize=12, pad=10, loc="left")
ax.legend(fontsize=8.5, frameon=False, loc="upper left")
ax.grid(alpha=0.13)
save(fig, "pca")

# ---------------------------------------------------- 3. stability
st = R["stability"]
fig, ax = plt.subplots(figsize=(8.6, 4.4))
vals = [st["by_style"][s] for s in STYLES]
bars = ax.bar([FLAT[s] for s in STYLES], vals,
              color=[COLORS[s] for s in STYLES], width=0.62)
ax.axhline(st["chance_baseline"], color="#B3402F", ls="--", lw=1.4)
ax.text(4.42, st["chance_baseline"] + 0.012, f"chance {st['chance_baseline']:.0%}",
        color="#B3402F", fontsize=8.5, ha="right")
ax.axhline(st["overall"], color=INK, ls=":", lw=1.3)
ax.text(4.42, st["overall"] + 0.012, f"overall {st['overall']:.0%}",
        color=INK, fontsize=8.5, ha="right")
for b, v in zip(bars, vals):
    ax.text(b.get_x() + b.get_width() / 2, v + 0.014, f"{v:.0%}",
            ha="center", fontsize=9.5)
ax.set_ylim(0, 0.75)
ax.set_ylabel("Share of a coach's seasons landing\nin that coach's own career cluster")
ax.set_title("How stable is a coach's style season to season?",
             fontsize=12, pad=10, loc="left")
ax.tick_params(axis="x", labelsize=9)
ax.grid(axis="y", alpha=0.16)
save(fig, "stability")

# ---------------------------------------------------- 4. prevalence
prev = pd.DataFrame(R["prevalence"]).T
prev.index = prev.index.astype(int)
prev = prev.sort_index()[STYLES]
fig, ax = plt.subplots(figsize=(9, 4.6))
for s in STYLES:
    ax.plot(prev.index, prev[s] * 100, marker="o", ms=4.5, lw=2,
            color=COLORS[s], label=FLAT[s])
    ax.annotate(FLAT[s], (prev.index[-1], prev[s].iloc[-1] * 100), fontsize=8.5,
                color=COLORS[s], xytext=(6, -3), textcoords="offset points")
ax.set_xlim(2015.8, 2025.9)
ax.set_ylabel("Share of FBS coach-seasons (%)")
ax.set_xlabel("Season")
ax.set_title("Style prevalence, 2016–2024 — no significant trend in any group",
             fontsize=12, pad=10, loc="left")
ax.grid(alpha=0.16)
save(fig, "prevalence")

# ---------------------------------------------------- 5. conference mix
cm = pd.DataFrame(R["conference_mix"]).T.reindex(STYLES)
fig, ax = plt.subplots(figsize=(8.6, 4.2))
order = ["Power 5", "Group of 5", "Independent"]
tier_c = {"Power 5": PLUM, "Group of 5": "#C9A227", "Independent": "#9A9A9A"}
left = np.zeros(len(STYLES))
for t in order:
    vals = cm[t].values * 100
    ax.barh([FLAT[s] for s in STYLES], vals, left=left, color=tier_c[t],
            label=t, height=0.6)
    for i, (v, l) in enumerate(zip(vals, left)):
        if v > 7:
            ax.text(l + v / 2, i, f"{v:.0f}%", ha="center", va="center",
                    color="white", fontsize=9)
    left += vals
ax.set_xlim(0, 100)
ax.set_xlabel("Share of coach-seasons (%)")
ax.invert_yaxis()
ax.legend(frameon=False, fontsize=9, ncol=3, loc="lower center",
          bbox_to_anchor=(0.5, -0.32))
ax.set_title("Where each style lives — conference tier mix",
             fontsize=12, pad=10, loc="left")
ax.tick_params(axis="y", labelsize=9)
ax.grid(axis="x", alpha=0.16)
save(fig, "conference")

# ---------------------------------------------------- 6. ATS forest
fig, ax = plt.subplots(figsize=(9, 4.6))
ys = np.arange(len(STYLES))[::-1]
for y, s in zip(ys, STYLES):
    t = R["ats_by_style"][s]
    lo, hi = t["ci"]
    ax.plot([lo, hi], [y, y], color=COLORS[s], lw=2.6, solid_capstyle="round")
    ax.plot(t["rate"], y, "o", ms=9, color=COLORS[s], mec="white", mew=1.2)
    ax.text(0.605, y, f"{t['rate']:.1%}   n={t['n']:,}", va="center", fontsize=9)
ax.axvline(0.5, color=GRID, lw=1.2)
ax.text(0.478, 4.55, "coin flip", ha="center", fontsize=8.5, color="#6A6A6A")
ax.axvline(BREAK_EVEN, color="#B3402F", lw=1.6, ls="--")
ax.text(BREAK_EVEN + 0.004, 4.55, "break-even at −110", ha="left", fontsize=8.5, color="#B3402F")
ax.set_yticks(ys)
ax.set_yticklabels([FLAT[s] for s in STYLES], fontsize=9.5)
ax.set_xlim(0.40, 0.665)
ax.set_xlabel("ATS cover rate, walk-forward labels (95% CI, coach-clustered)")
ax.set_ylim(-0.7, 5.0)
ax.set_title("Against the spread: every style is a coin flip",
             fontsize=12, pad=10, loc="left")
ax.grid(axis="x", alpha=0.16)
save(fig, "ats")

# ---------------------------------------------------- 7. totals / market pricing
tb = {m["style"]: m for m in R["totals_by_style"]}
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.6, 4.6),
                               gridspec_kw={"width_ratios": [1.25, 1]})
x = np.arange(len(STYLES))
w = 0.36
lines = [tb[s]["mean_total_line"] for s in STYLES]
pts = [tb[s]["mean_points_scored"] for s in STYLES]
ax1.bar(x - w / 2, lines, w, color=PLUM, label="Posted total (market)")
ax1.bar(x + w / 2, pts, w, color="#C9A227", label="Actual points scored")
for i, (a, b_) in enumerate(zip(lines, pts)):
    ax1.text(i - w / 2, a + 0.35, f"{a:.1f}", ha="center", fontsize=8.5)
    ax1.text(i + w / 2, b_ + 0.35, f"{b_:.1f}", ha="center", fontsize=8.5)
ax1.set_xticks(x)
ax1.set_xticklabels([PRETTY[s] for s in STYLES], fontsize=8.5)
ax1.set_ylim(45, 60)
ax1.set_ylabel("Points")
ax1.legend(frameon=False, fontsize=9, loc="upper left")
ax1.set_title("The market already knows: posted total tracks\nactual scoring style for style",
              fontsize=11.5, pad=10, loc="left")
ax1.grid(axis="y", alpha=0.16)

ys = np.arange(len(STYLES))[::-1]
for y, s in zip(ys, STYLES):
    t = tb[s]["test"]
    lo, hi = t["ci"]
    ax2.plot([lo, hi], [y, y], color=COLORS[s], lw=2.6, solid_capstyle="round")
    ax2.plot(t["rate"], y, "o", ms=9, color=COLORS[s], mec="white", mew=1.2)
    ax2.text(0.605, y, f"{t['rate']:.1%}", va="center", fontsize=9)
ax2.axvline(0.5, color=GRID, lw=1.2)
ax2.axvline(BREAK_EVEN, color="#B3402F", lw=1.6, ls="--")
ax2.text(BREAK_EVEN + 0.004, 4.55, "break-even", ha="left", fontsize=8.5, color="#B3402F")
ax2.set_yticks(ys)
ax2.set_yticklabels([FLAT[s] for s in STYLES], fontsize=9)
ax2.set_xlim(0.40, 0.655)
ax2.set_ylim(-0.7, 5.0)
ax2.set_xlabel("Over rate (95% CI, coach-clustered)")
ax2.set_title("…so the over rate carries no signal", fontsize=11.5, pad=10, loc="left")
ax2.grid(axis="x", alpha=0.16)
save(fig, "totals")

# ---------------------------------------------------- 8. matchup grid
gn = pd.DataFrame(R["matchup_grid_n"]).T.reindex(STYLES)[STYLES]
gr = pd.DataFrame(R["matchup_grid_rate"]).T.reindex(STYLES)[STYLES].astype(float)
fig, ax = plt.subplots(figsize=(7.6, 5.4))
im = ax.imshow(gr.values, cmap=DIVERGE, vmin=0.38, vmax=0.62, aspect="auto")
ax.set_xticks(range(5)); ax.set_xticklabels([PRETTY[s] for s in STYLES], fontsize=8.5)
ax.set_yticks(range(5)); ax.set_yticklabels([FLAT[s] for s in STYLES], fontsize=9)
for i in range(5):
    for j in range(5):
        n = gn.values[i, j]
        r = gr.values[i, j]
        txt = f"{r:.0%}\nn={n}" if not np.isnan(r) else f"—\nn={n}"
        ax.text(j, i, txt, ha="center", va="center", fontsize=8,
                color="white" if (not np.isnan(r) and abs(r - 0.5) > 0.055) else INK)
ax.set_xlabel("Away coach style")
ax.set_ylabel("Home coach style")
ax.set_title("Matchup grid — home-side cover rate (exploratory, uncorrected)",
             fontsize=12, pad=12, loc="left")
cb = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
cb.set_label("Home cover rate", fontsize=8)
cb.ax.tick_params(labelsize=8)
save(fig, "matchup")


print("\n=== KEY RESULTS ===")
print(f"team-seasons {R['n_team_seasons']}  coaches {R['n_coaches_all']}  labeled {R['n_coaches_labeled']}")
print(f"style counts: {R['style_counts']}")
print(f"PCA evr (style space): {R['pca_evr'][:3]}")
print(f"stability: {R['stability']['overall']:.3f} vs chance {R['stability']['chance_baseline']:.3f}"
      f"  ({R['stability']['coaches_fully_consistent']}/{R['stability']['n_coaches']} fully consistent)")
print(f"walk-forward agreement with career label: {R['walk_forward']['agreement_with_career_label']:.3f}")
print(f"conference chi2 {R['conference_chi2']['chi2']} p={R['conference_chi2']['p']:.2e}")
print(f"ATS by style: " + ", ".join(f"{s}={R['ats_by_style'][s]['rate']:.3f}(p={R['ats_by_style'][s]['p']})" for s in STYLES))
print(f"totals: " + ", ".join(f"{m['style']} line={m['mean_total_line']} pts={m['mean_points_scored']} over={m['over_rate']:.3f}" for m in R["totals_by_style"]))
print(f"market baseline: line {R['totals_market_baseline']['mean_total_line']} vs points {R['totals_market_baseline']['mean_points']}")
print(f"Holm over {R['multiplicity']['n_tests']} tests -- any significant: {R['multiplicity']['any_significant_after_holm']}"
      f"  (min adjusted p = {min(r['p_holm'] for r in R['multiplicity']['results'])})")
