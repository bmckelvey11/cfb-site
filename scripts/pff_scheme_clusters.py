"""Exploratory clustering of the PFF scheme rates -- do offensive/defensive "types" exist?

Consumes scripts/pff_scheme_profile.py output. Clusters offense and defense
separately, and reports the evidence for and against the clusters being real
types rather than arbitrary cuts through a continuum:

  * correlation of each rate with team quality (SP+), to decide whether the
    quality-residualization that coach_style_cluster needed is needed here
  * silhouette across k = 2..8
  * bootstrap-resample ARI at the chosen k (label stability)
  * PCA variance -- how much of the shape is one or two axes
  * k-means vs a median split on the single most-loaded feature
  * face validity: do the option academies land together?

Usage:
    python scripts/pff_scheme_clusters.py                     # 2025
    python scripts/pff_scheme_clusters.py --season 2025 --k-offense 4 --k-defense 3

Writes <processed>/pff_scheme_clusters_<season>.csv when --k-* are given.
See docs/pff-scheme-inventory-2026-09-16.md.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.preprocessing import StandardScaler

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
from cfb_paths import PROCESSED, RAW  # noqa: E402

# Own play-calling only. The two `_faced` rates are opponent behaviour, not this
# team's type, so they are excluded from both feature sets.
OFFENSE_FEATS = [
    "off_pass_snap_rate",
    "off_gap_run_rate",
    "off_play_action_rate",
    "off_screen_rate",
    "off_quick_game_rate",
    "off_deep_attempt_rate",
    "off_behind_los_rate",
    "off_wr_slot_rate",
    "off_te_inline_rate",
    "off_qb_designed_run_rate",
    "off_run_interior_rate",
]

# def_corner_snap_share (sd .005) and def_slot_db_share (sd .009) are constant
# across FBS -- in a distance metric they are noise, so they are dropped.
DEFENSE_FEATS = [
    "def_man_rate",
    "def_dl_snap_share",
    "def_box_snap_share",
    "def_fs_snap_share",
    "def_dl_a_gap_share",
    "def_dl_outside_t_share",
]

ACADEMIES = ["Army Black Knights", "Navy Midshipmen", "Air Force Falcons"]
AIR_RAID = ["Hawaii Warriors", "Middle Tennessee Blue Raiders", "Florida Atlantic Owls"]
# Long-running 3-down / odd-front programs -- the defensive equivalent of the
# academies check. If a defensive partition is real these land together.
ODD_FRONT = ["Iowa State Cyclones", "TCU Horned Frogs", "Cincinnati Bearcats"]

FACE_CHECKS = {
    "offense": (("academies", ACADEMIES), ("air-raid", AIR_RAID)),
    "defense": (("odd-front", ODD_FRONT),),
}

# Above this, a feature is carrying team quality rather than style and gets
# reported as such. Prior art (docs/coach-playstyle-analysis.md) saw style
# features at |r| <= 0.10 and quality features at 0.47-0.67.
QUALITY_R_THRESHOLD = 0.25

SEED = 0


def load_sp_overall(season: int) -> pd.Series:
    """Team -> SP+ overall for the season, from the coaches feed."""
    path = RAW / f"coaches_{season}.json"
    best: dict[str, tuple[int, float]] = {}
    for coach in json.loads(path.read_text(encoding="utf-8")):
        for s in coach.get("seasons") or []:
            if s.get("year") != season or s.get("spOverall") is None:
                continue
            games = s.get("games") or 0
            school = s["school"]
            if school not in best or games > best[school][0]:
                best[school] = (games, s["spOverall"])
    return pd.Series({k: v[1] for k, v in best.items()}, name="sp_overall")


def quality_correlations(df: pd.DataFrame, feats: list[str], sp: pd.Series) -> pd.Series:
    """|r| between each rate and SP+ overall, on the teams that join."""
    joined = df.set_index("team_short").join(sp, how="inner")
    return joined[feats].corrwith(joined["sp_overall"]).rename("r_with_sp")


def sweep_k(x: np.ndarray, kmax: int = 8) -> pd.DataFrame:
    rows = []
    for k in range(2, kmax + 1):
        labels = KMeans(n_clusters=k, n_init=25, random_state=SEED).fit_predict(x)
        rows.append({"k": k, "silhouette": silhouette_score(x, labels),
                     "inertia": KMeans(n_clusters=k, n_init=25, random_state=SEED).fit(x).inertia_})
    return pd.DataFrame(rows)


def stability(x: np.ndarray, k: int, n_boot: int = 100) -> float:
    """Mean ARI between the full-sample partition and bootstrap refits, scored
    out-of-bag.

    Scoring on the full sample would compare nearest-centroid assignments, which
    measures centroid drift rather than whether the partition holds -- and the
    duplicated rows in a resample pull centroids toward dense regions, inflating
    it. Held-out teams are the ones the refit never saw, so agreement there is
    the honest number. Low ARI means the cut lines move under resampling, i.e.
    the clusters are regions of a continuum.
    """
    rng = np.random.default_rng(SEED)
    base = KMeans(n_clusters=k, n_init=25, random_state=SEED).fit(x)
    scores = []
    for _ in range(n_boot):
        idx = rng.choice(len(x), len(x), replace=True)
        oob = np.setdiff1d(np.arange(len(x)), idx)
        if len(oob) < k:
            continue
        refit = KMeans(n_clusters=k, n_init=25, random_state=SEED).fit(x[idx])
        scores.append(adjusted_rand_score(base.labels_[oob], refit.predict(x[oob])))
    return float(np.mean(scores))


def single_axis_baseline(x: np.ndarray, feats: list[str], k: int) -> tuple[float, str]:
    """ARI between k-means and a cut on the single highest-loading PC1 feature.

    The cut points reproduce k-means' own cluster sizes rather than equal
    quantiles -- k-means is free to produce a 100/36 split, so scoring it
    against a forced 68/68 split would penalise the baseline for nothing.
    If these agree, k-means found one axis, not k types.
    """
    pca = PCA().fit(x)
    lead = int(np.argmax(np.abs(pca.components_[0])))
    km = KMeans(n_clusters=k, n_init=25, random_state=SEED).fit_predict(x)
    # order the clusters along the lead axis before taking their sizes, so the
    # cut points land where k-means' own boundaries fall on that axis
    by_axis = pd.DataFrame({"c": km, "v": x[:, lead]}).groupby("c")["v"].mean().sort_values()
    sizes = pd.Series(km).value_counts().reindex(by_axis.index).to_numpy()
    cuts = np.cumsum(sizes)[:-1] / len(x)
    axis_labels = pd.qcut(x[:, lead], [0, *cuts, 1], labels=False, duplicates="drop")
    return float(adjusted_rand_score(km, axis_labels)), feats[lead]


def analyze(df: pd.DataFrame, feats: list[str], side: str, sp: pd.Series,
            k: int | None, drop_quality: bool = False) -> tuple[pd.DataFrame, np.ndarray | None]:
    corr = quality_correlations(df, feats, sp)
    if drop_quality:
        feats = [f for f in feats if abs(corr[f]) <= QUALITY_R_THRESHOLD]

    x = StandardScaler().fit_transform(df[feats].to_numpy())

    tag = "  [SP+-loaded features dropped]" if drop_quality else ""
    print(f"\n{'=' * 72}\n{side.upper()}{tag}  ({len(feats)} features, {len(df)} teams)\n{'=' * 72}")

    print("\n-- correlation with SP+ overall (is this style, or quality in costume?)")
    print(corr.abs().sort_values(ascending=False).round(3).to_string())
    loaded = corr[corr.abs() > QUALITY_R_THRESHOLD]
    if len(loaded):
        print(f"   {len(loaded)} feature(s) above |r| = {QUALITY_R_THRESHOLD}: {list(loaded.index)}")
    else:
        print(f"   none above |r| = {QUALITY_R_THRESHOLD} -- no quality residualization needed")

    pca = PCA().fit(x)
    var = pca.explained_variance_ratio_
    print(f"\n-- PCA: PC1 {var[0]:.1%}, PC2 {var[1]:.1%}, PC1+PC2 {var[:2].sum():.1%}")

    sweep = sweep_k(x)
    print("\n-- k sweep")
    print(sweep.round(3).to_string(index=False))
    best_k = int(sweep.loc[sweep.silhouette.idxmax(), "k"])
    best_sil = sweep.silhouette.max()
    print(f"   best silhouette {best_sil:.3f} at k={best_k}"
          f"   ({'structure' if best_sil >= 0.5 else 'weak/continuum' if best_sil < 0.25 else 'moderate'})")

    k = k or best_k
    ari_boot = stability(x, k)
    ari_axis, lead_feat = single_axis_baseline(x, feats, k)
    print(f"\n-- at k={k}: bootstrap ARI {ari_boot:.3f}  |  "
          f"ARI vs a {k}-quantile cut on {lead_feat} alone: {ari_axis:.3f}")

    labels = KMeans(n_clusters=k, n_init=25, random_state=SEED).fit_predict(x)
    out = df[["team_name"] + feats].copy()
    out[f"{side}_cluster"] = labels

    print(f"\n-- cluster means (z-scored), n per cluster")
    prof = pd.DataFrame(x, columns=feats).groupby(labels).mean()
    prof.insert(0, "n", pd.Series(labels).value_counts().sort_index())
    print(prof.round(2).to_string())

    col = f"{side}_cluster"
    for name, teams in FACE_CHECKS[side]:
        got = out[out.team_name.isin(teams)][["team_name", col]]
        same = got[col].nunique() == 1
        print(f"\n-- face validity, {name}: {'TOGETHER' if same else 'SPLIT'} -> "
              + ", ".join(f"{r.team_name.split()[0]}={getattr(r, col)}" for r in got.itertuples()))

    return out, labels


def persistence(h1: pd.DataFrame, h2: pd.DataFrame, feats: list[str],
                side: str, k: int) -> None:
    """Does a label describe the team, or the sample it was fit on?

    PFF's warehouse starts at 2025, so a season-over-season test is impossible.
    This is the strongest substitute the data allows: fit the same clustering
    independently on weeks 0-7 and weeks 8+, and see whether the same teams end
    up together. It cannot see coaching turnover between seasons -- it only
    rules out the partition being an artifact of one sample.
    """
    both = h1[["team_name"] + feats].merge(h2[["team_name"] + feats], on="team_name",
                                           suffixes=("_h1", "_h2"))
    print(f"\n-- split-half persistence, {side} (n={len(both)} teams)")
    rs = pd.Series({f: both[f"{f}_h1"].corr(both[f"{f}_h2"]) for f in feats})
    print("   per-feature r(first half, second half):")
    print(rs.sort_values(ascending=False).round(3).to_string().replace("\n", "\n     "))

    labs = []
    for half, frame in (("h1", h1), ("h2", h2)):
        x = StandardScaler().fit_transform(frame.set_index("team_name").loc[both.team_name, feats])
        labs.append(KMeans(n_clusters=k, n_init=25, random_state=SEED).fit_predict(x))
    print(f"   label ARI between halves at k={k}: {adjusted_rand_score(*labs):.3f}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--season", type=int, default=2025)
    ap.add_argument("--profile", default=None, help="scheme profile CSV")
    ap.add_argument("--k-offense", type=int, default=None)
    ap.add_argument("--k-defense", type=int, default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--drop-quality", action="store_true",
                    help="also re-run each side with the SP+-loaded features removed")
    ap.add_argument("--split-half", action="store_true",
                    help="split-half persistence test; needs the _h1/_h2 profiles "
                         "from pff_scheme_profile.py --week-min/--week-max")
    args = ap.parse_args()

    src = Path(args.profile or PROCESSED / f"pff_scheme_profile_{args.season}.csv")
    df = pd.read_csv(src)
    # coaches feed keys on school name; the PFF team_name is "School Mascot"
    df["team_short"] = df.team_name
    sp = load_sp_overall(args.season)
    df["team_short"] = [_match_school(n, sp.index) for n in df.team_name]

    off, _ = analyze(df, OFFENSE_FEATS, "offense", sp, args.k_offense)
    dfn, _ = analyze(df, DEFENSE_FEATS, "defense", sp, args.k_defense)
    if args.drop_quality:
        # the SP+-clean run is the one worth keeping labels from
        off, _ = analyze(df, OFFENSE_FEATS, "offense", sp, args.k_offense, drop_quality=True)
        dfn, _ = analyze(df, DEFENSE_FEATS, "defense", sp, args.k_defense, drop_quality=True)

    if args.split_half:
        h1 = pd.read_csv(PROCESSED / f"pff_scheme_profile_{args.season}_h1.csv")
        h2 = pd.read_csv(PROCESSED / f"pff_scheme_profile_{args.season}_h2.csv")
        clean_def = [f for f in DEFENSE_FEATS
                     if abs(quality_correlations(df, DEFENSE_FEATS, sp)[f]) <= QUALITY_R_THRESHOLD]
        persistence(h1, h2, OFFENSE_FEATS, "offense", args.k_offense or 2)
        persistence(h1, h2, clean_def, "defense", args.k_defense or 2)

    if args.k_offense and args.k_defense:
        merged = off[["team_name", "offense_cluster"]].merge(
            dfn[["team_name", "defense_cluster"]], on="team_name")
        out = Path(args.out or PROCESSED / f"pff_scheme_clusters_{args.season}.csv")
        merged.to_csv(out, index=False)
        print(f"\nwrote {len(merged)} rows -> {out}")


def _match_school(pff_name: str, schools) -> str | None:
    """Longest school name that prefixes the PFF "School Mascot" string."""
    hits = [s for s in schools if pff_name.startswith(s)]
    return max(hits, key=len) if hits else None


if __name__ == "__main__":
    main()
