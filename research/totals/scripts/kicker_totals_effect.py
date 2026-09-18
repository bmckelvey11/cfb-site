"""Does kicker quality or kicker volatility move a game's total past the closing book line?

Question. Two channels, tested separately:

  A (mean)       Prior-season kicker *quality* shifts realized points relative to the
                 closing book total -- i.e. the market misprices teams by their kicker.
  B (dispersion) Prior-season kicker *volatility* widens the spread of that residual --
                 i.e. streaky kickers make a game less predictable around the number.

Both features are built from the PRIOR season only, so no information from the game
being predicted enters the feature. That is the leakage gate.

Market price. Closing total is the median `total_close` across REAL SPORTSBOOKS only.
`core.fact_game_line` also carries teamrankings and numberfire, which are projection
sites, not prices; including them would make this model-vs-model. `fact_game.selected_total`
is NOT used for the same reason -- it resolves to teamrankings for 3,079 games.

Features (prior season, per team):
  quality    Primary kicker's PAAR (CFBD points-above-average, distance/situation
             adjusted) per game, empirical-Bayes shrunk on attempts. Primary kicker =
             most FG attempts that season.
  volatility Overdispersion phi of per-game FG makes vs the binomial expectation at the
             kicker's own season rate. phi = 1 is exactly binomial; phi > 1 is streaky.
             Raw per-game FG-points SD reported as a secondary, volume-contaminated measure.

Per game both kickers matter, so the regressors are the SUMS (home + away), standardized.

Estimator. OLS of the residual on the two standardized sums, two-way cluster-robust on
home-team-season and away-team-season (a team's feature is constant across its ~12 games).

Reported. Coefficients with 95% CIs, the pre-run MDE, and the mechanical effect ceiling
implied by the year-over-year persistence of PAAR. The cover-rate tercile tables are
DESCRIPTIVE -- thresholding throws away power; they are not the decision.

Run from repo root:
    python research/totals/scripts/kicker_totals_effect.py
    python research/totals/scripts/kicker_totals_effect.py --self-check
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

SKILL = Path.home() / ".claude" / "skills" / "econometrics"
if SKILL.exists():
    sys.path.insert(0, str(SKILL))

DB = ROOT / "data" / "cfb.duckdb"

# Real sportsbooks in core.dim_lines_provider. teamrankings and numberfire are
# projection sites and are deliberately excluded. `consensus` is an aggregate whose
# constituents are not recorded, so it is a sensitivity, not the primary price.
BOOKS = (
    "bovada", "caesars", "draftkings", "fanduel", "betmgm", "circa", "pinnacle",
    "bet365", "william hill (new jersey)", "espn bet",
    "caesars sportsbook (colorado)", "caesars (pennsylvania)", "sugarhouse",
)

SEASON_MIN, SEASON_MAX = 2018, 2025  # book totals start 2018; PAAR starts 2016


# --------------------------------------------------------------------------- loading

def connect(db: Path = DB):
    import duckdb
    return duckdb.connect(str(db), read_only=True)


def load_games(con) -> pd.DataFrame:
    """One row per game: season, teams, realized points, median book closing total."""
    books = ",".join("'" + b + "'" for b in BOOKS)
    return con.execute(f"""
        select g.game_id, g.season, g.week, g.home_team, g.away_team,
               g.home_points + g.away_points as points,
               median(l.total_close)          as total,
               count(*)                       as n_books
        from core.fact_game g
        join core.fact_game_line l on l.game_id = g.game_id
        where l.provider_key in ({books})
          and l.total_close is not null
          and g.season between {SEASON_MIN} and {SEASON_MAX}
          and g.home_points is not null and g.away_points is not null
        group by 1,2,3,4,5,6
    """).df()


def load_paar(con) -> pd.DataFrame:
    """Primary kicker's season PAAR per team-season (most attempts wins the slot)."""
    return con.execute("""
        with ranked as (
          select team, season, athleteName, attempts, paar,
                 row_number() over (partition by team, season
                                    order by attempts desc, paar desc) rn
          from stg.kicker_paar
        )
        select team, season, athleteName as kicker, attempts, paar
        from ranked where rn = 1
    """).df()


def load_fg_games(con) -> pd.DataFrame:
    """Per game-team field-goal makes and attempts, from the kicking box score.

    Rows are per kicker; a team-game with two kickers is summed. `stat` is "made/att".
    """
    return con.execute("""
        select cat.season, cat.gameId as game_id, cat.teams_team as team,
               sum(try_cast(split_part(a.stat, '/', 1) as integer)) as fgm,
               sum(try_cast(split_part(a.stat, '/', 2) as integer)) as fga
        from stg.game_player_stats__teams__teams_categories cat,
             unnest(cat.teams_categories_types) as u(t),
             unnest(u.t.athletes) as v(a)
        where cat.teams_categories_name = 'kicking'
          and t.name = 'FG'
          and cat.season between 2016 and 2025
          and a.stat like '%/%'
        group by 1,2,3
    """).df()


# -------------------------------------------------------------------------- features

def eb_shrink_paar(paar: pd.DataFrame) -> pd.DataFrame:
    """Shrink PAAR-per-attempt toward the season mean, weighting by attempts.

    Empirical Bayes: w = n / (n + n0), with the noise and signal components of the
    cross-kicker spread separated per season.
    """
    out = []
    for season, g in paar.groupby("season"):
        g = g.copy()
        n = g["attempts"].clip(lower=1).to_numpy(float)
        rate = g["paar"].to_numpy(float) / n            # PAAR per attempt
        mu = float(np.average(rate, weights=n))
        total_var = float(np.average((rate - mu) ** 2, weights=n))
        # a per-attempt mean has noise var s2/n; recover s2 from the n-weighted spread
        s2 = float(np.average((rate - mu) ** 2 * n, weights=n))
        noise_var = s2 / float(np.mean(n))
        signal_var = max(total_var - noise_var, 1e-9)
        n0 = s2 / signal_var
        w = n / (n + n0)
        g["paar_rate_shrunk"] = mu + w * (rate - mu)
        g["shrink_w"] = w
        out.append(g)
    return pd.concat(out, ignore_index=True)


def kicker_features(paar: pd.DataFrame, fg: pd.DataFrame) -> pd.DataFrame:
    """Per team-season: quality (pts/game above average) and volatility (overdispersion)."""
    fg = fg.dropna(subset=["fgm", "fga"]).copy()
    fg["fgm"] = fg["fgm"].astype(float)
    fg["fga"] = fg["fga"].astype(float)

    # games played per team-season (the box score covers every game, attempts or not)
    gp = fg.groupby(["team", "season"]).size().rename("games").reset_index()

    agg = fg.groupby(["team", "season"])[["fgm", "fga"]].sum().reset_index()
    agg["fg_rate"] = np.where(agg["fga"] > 0, agg["fgm"] / agg["fga"], np.nan)
    league = fg.groupby("season")[["fgm", "fga"]].sum()
    league["league_rate"] = league["fgm"] / league["fga"]

    # Pearson overdispersion phi of per-game makes vs Binomial(fga, team season rate).
    # Only games with at least one attempt carry information.
    m = fg.merge(agg[["team", "season", "fg_rate"]], on=["team", "season"])
    m = m[m["fga"] > 0].copy()
    p = m["fg_rate"].clip(0.02, 0.98)
    m["chi"] = (m["fgm"] - m["fga"] * p) ** 2 / (m["fga"] * p * (1 - p))
    disp = m.groupby(["team", "season"]).agg(
        chi_sum=("chi", "sum"), n_att_games=("chi", "size")
    ).reset_index()
    # phi = chi2 / dof; dof loses 1 for estimating the team rate on the same games
    disp["phi"] = disp["chi_sum"] / (disp["n_att_games"] - 1).clip(lower=1)

    # secondary, volume-contaminated: SD of FG points per game over all games
    fg["fg_pts"] = 3.0 * fg["fgm"]
    sdpts = fg.groupby(["team", "season"])["fg_pts"].std().rename("fg_pts_sd").reset_index()

    feat = (
        agg.merge(gp, on=["team", "season"])
           .merge(disp[["team", "season", "phi", "n_att_games"]],
                  on=["team", "season"], how="left")
           .merge(sdpts, on=["team", "season"], how="left")
           .merge(league[["league_rate"]], left_on="season", right_index=True)
    )

    shr = eb_shrink_paar(paar)
    feat = feat.merge(
        shr[["team", "season", "kicker", "attempts", "paar",
             "paar_rate_shrunk", "shrink_w"]],
        on=["team", "season"], how="inner",
    )
    # quality in points per game above an average kicker at this team's attempt volume
    feat["quality"] = feat["paar_rate_shrunk"] * feat["attempts"] / feat["games"]
    feat["quality_raw"] = feat["paar"] / feat["games"]
    return feat


def build_panel(games: pd.DataFrame, feat: pd.DataFrame) -> pd.DataFrame:
    """Attach each team's PRIOR-season kicker features. This is the leakage gate."""
    prior = feat.copy()
    prior["season"] = prior["season"] + 1  # feature from season s applies to games in s+1

    keep = ["team", "season", "quality", "quality_raw", "phi", "fg_pts_sd",
            "attempts", "games", "kicker", "n_att_games"]
    h = prior[keep].add_suffix("_h").rename(
        columns={"team_h": "home_team", "season_h": "season"})
    a = prior[keep].add_suffix("_a").rename(
        columns={"team_a": "away_team", "season_a": "season"})

    df = (games.merge(h, on=["home_team", "season"], how="inner")
                .merge(a, on=["away_team", "season"], how="inner"))

    df["resid"] = df["points"] - df["total"]
    df["q_sum"] = df["quality_h"] + df["quality_a"]
    df["v_sum"] = df["phi_h"] + df["phi_a"]
    df["sd_sum"] = df["fg_pts_sd_h"] + df["fg_pts_sd_a"]
    df["ts_home"] = df["home_team"] + "|" + df["season"].astype(str)
    df["ts_away"] = df["away_team"] + "|" + df["season"].astype(str)
    df = df.dropna(subset=["resid", "q_sum", "v_sum"])
    assert_prior_season(df, feat)
    return df


def assert_prior_season(df: pd.DataFrame, feat: pd.DataFrame) -> None:
    """The leakage gate, checked rather than assumed.

    Every game's attached feature must equal the one computed from season s-1, and must
    differ from the same-season one wherever the two exist. A dropped or flipped `+1` in
    `build_panel` would otherwise produce a leaked result that looks entirely plausible.
    """
    idx = feat.set_index(["team", "season"])["quality"]
    checked = 0
    for _, g in df.head(400).iterrows():
        key_prior = (g["home_team"], int(g["season"]) - 1)
        if key_prior not in idx.index:
            continue
        want = float(idx.loc[key_prior])
        assert abs(want - float(g["quality_h"])) < 1e-9, (
            f"LEAKAGE: {g['home_team']} {g['season']} carries {g['quality_h']:.6f}, "
            f"prior season holds {want:.6f}")
        key_same = (g["home_team"], int(g["season"]))
        if key_same in idx.index:
            same = float(idx.loc[key_same])
            assert abs(same - float(g["quality_h"])) > 1e-12 or abs(same - want) < 1e-12, (
                f"LEAKAGE: {g['home_team']} {g['season']} matches the SAME season")
        checked += 1
    if checked == 0:
        raise AssertionError("leakage gate never ran -- no game matched a prior season")


# ------------------------------------------------------------------------ estimation

def z(x: pd.Series) -> np.ndarray:
    v = x.to_numpy(float)
    return (v - v.mean()) / v.std(ddof=1)


def twoway_ols(df: pd.DataFrame, y: str, regressors: list):
    """OLS with two-way cluster-robust SEs on home-team-season and away-team-season."""
    import statsmodels.api as sm
    X = np.column_stack([z(df[r]) for r in regressors])
    X = sm.add_constant(X)
    groups = np.column_stack([
        pd.factorize(df["ts_home"])[0],
        pd.factorize(df["ts_away"])[0],
    ])
    fit = sm.OLS(df[y].to_numpy(float), X).fit(
        cov_type="cluster", cov_kwds={"groups": groups, "use_correction": True})
    return fit, ["const"] + list(regressors)


def report_fit(fit, names, label: str, unit: str) -> list:
    rows = []
    ci = fit.conf_int()
    print(f"\n  {label}   (n={int(fit.nobs)}, {unit} per 1 SD of regressor)")
    print(f"    {'term':<10} {'coef':>8} {'se':>7} {'95% CI':>21} {'p':>7}")
    for i, nm in enumerate(names):
        lo, hi = ci[i]
        print(f"    {nm:<10} {fit.params[i]:>8.4f} {fit.bse[i]:>7.4f} "
              f"[{lo:>8.4f}, {hi:>8.4f}] {fit.pvalues[i]:>7.3f}")
        rows.append(dict(model=label, term=nm, coef=fit.params[i], se=fit.bse[i],
                         lo=lo, hi=hi, p=fit.pvalues[i]))
    return rows


def wilson(k: int, n: int, zc: float = 1.959963985):
    if n == 0:
        return (np.nan, np.nan, np.nan)
    p = k / n
    d = 1 + zc ** 2 / n
    c = (p + zc ** 2 / (2 * n)) / d
    h = zc * np.sqrt(p * (1 - p) / n + zc ** 2 / (4 * n ** 2)) / d
    return p, c - h, c + h


def tercile_table(df: pd.DataFrame, col: str, label: str) -> list:
    """Descriptive over-rate by tercile. Pushes excluded from the rate, counted separately."""
    q = pd.qcut(df[col], 3, labels=["low", "mid", "high"])
    print(f"\n  Over rate by {label} tercile (pushes excluded from the rate)")
    print(f"    {'tercile':<8} {'n':>6} {'push':>5} {'over%':>7} {'95% CI':>18} {'mean resid':>11}")
    rows = []
    for t in ["low", "mid", "high"]:
        g = df[q == t]
        dec = g[g["resid"] != 0]
        k = int((dec["resid"] > 0).sum())
        n = len(dec)
        p, lo, hi = wilson(k, n)
        print(f"    {t:<8} {len(g):>6} {len(g) - n:>5} {100 * p:>6.1f}% "
              f"[{100 * lo:>5.1f}%,{100 * hi:>5.1f}%] {g['resid'].mean():>10.2f}")
        rows.append(dict(feature=label, tercile=t, n=n, pushes=len(g) - n, over=k,
                         rate=p, lo=lo, hi=hi, mean_resid=g["resid"].mean()))
    return rows


def persistence(paar: pd.DataFrame) -> dict:
    """Year-over-year correlation of a team's primary-kicker PAAR. Bounds the effect."""
    a = paar.rename(columns={"paar": "paar_prior"})[["team", "season", "paar_prior"]].copy()
    a["season"] = a["season"] + 1
    m = paar.merge(a, on=["team", "season"], how="inner")
    r = float(np.corrcoef(m["paar_prior"], m["paar"])[0, 1])
    return dict(r=r, n=len(m), sd_prior=float(m["paar_prior"].std()),
                sd_cur=float(m["paar"].std()))


def mechanical_ceiling(feat: pd.DataFrame, sd_q_sum: float) -> dict:
    """Largest mean effect the feature could have, per 1 SD of the two-kicker sum.

    Estimated directly, not assumed: regress a team's CURRENT-season kicker value
    (raw PAAR per game) on its PRIOR-season shrunk `quality`. The slope is how many
    points per game one unit of the feature actually buys. Using the shrunk feature
    on the right-hand side avoids the attenuation that a raw-PAAR-on-raw-PAAR
    correlation would carry.

    This is a ceiling on the *mean* channel: it assumes the market prices none of it.
    """
    prior = feat[["team", "season", "quality"]].copy()
    prior["season"] = prior["season"] + 1
    m = feat[["team", "season", "quality_raw"]].merge(prior, on=["team", "season"])
    x = m["quality"].to_numpy(float)
    y = m["quality_raw"].to_numpy(float)
    slope, intercept = np.polyfit(x, y, 1)
    resid = y - (slope * x + intercept)
    se = float(np.sqrt((resid ** 2).sum() / (len(x) - 2) / ((x - x.mean()) ** 2).sum()))
    return dict(slope=float(slope), slope_se=se, n=len(m),
                pts_per_game_per_sd=float(slope) * sd_q_sum,
                hi_pts_per_game_per_sd=(float(slope) + 1.96 * se) * sd_q_sum)


def dispersion_ceiling(fg: pd.DataFrame, sd_resid: float, sd_v_sum: float,
                       seasons: range) -> dict:
    """Largest effect kicker volatility could have on the width of the residual.

    Field-goal points are 3 * Binomial(attempts, rate), so their per-game variance is
    9 * a * p * (1-p) * phi. One unit of phi therefore adds 9*a*p*(1-p) to the variance
    of a game's total; `v_sum` is the two kickers' phi, so one SD of it adds that much
    times sd_v_sum. Convert the resulting change in residual SD into the units model B
    actually regresses -- E|resid| = sqrt(2/pi) * SD for a centred normal.
    """
    f = fg[fg["season"].isin(list(seasons))]
    a_bar = float(f["fga"].mean())                      # attempts per team-game
    p_bar = float(f["fgm"].sum() / max(f["fga"].sum(), 1))
    var_per_unit_phi = 9.0 * a_bar * p_bar * (1 - p_bar)
    d_var = var_per_unit_phi * sd_v_sum
    sd1 = float(np.sqrt(sd_resid ** 2 + d_var))
    return dict(att_per_game=a_bar, make_rate=p_bar,
                var_per_unit_phi=var_per_unit_phi, d_var=d_var,
                d_sd=sd1 - sd_resid,
                d_mean_abs=np.sqrt(2 / np.pi) * (sd1 - sd_resid))


# ------------------------------------------------------------------------------ main

def load_all(cache: Path | None):
    """Load the three source frames, caching to parquet so a locked warehouse
    (a concurrent `core` rebuild holds an exclusive handle) does not block a re-run."""
    if cache and (cache / "games.parquet").exists():
        print(f"(reading cached frames from {cache})")
        return tuple(pd.read_parquet(cache / f"{n}.parquet")
                     for n in ("games", "paar", "fg"))
    con = connect()
    frames = (load_games(con), load_paar(con), load_fg_games(con))
    con.close()
    if cache:
        cache.mkdir(parents=True, exist_ok=True)
        for n, f in zip(("games", "paar", "fg"), frames):
            f.to_parquet(cache / f"{n}.parquet")
        print(f"(cached frames to {cache})")
    return frames


def run(args) -> int:
    games, paar, fg = load_all(Path(args.cache) if args.cache else None)

    feat = kicker_features(paar, fg)
    df = build_panel(games, feat)

    print("=" * 78)
    print("Kicker quality and volatility vs the closing book total")
    print("=" * 78)
    print(f"\nSample  seasons {SEASON_MIN}-{SEASON_MAX}   games {len(df):,}   "
          f"team-seasons {df['ts_home'].nunique():,}")
    print(f"        market = median closing total across real books only "
          f"(median {df['n_books'].median():.0f} books/game)")
    print(f"        residual (points - total): mean {df['resid'].mean():+.2f}, "
          f"SD {df['resid'].std():.2f}")

    print("\nFeature spread (prior season, home side shown)")
    for c, lab in [("quality_h", "quality   pts/game above avg kicker"),
                   ("phi_h", "volatility  overdispersion phi"),
                   ("fg_pts_sd_h", "secondary   FG pts/game SD")]:
        s = df[c]
        print(f"    {lab:<38} mean {s.mean():>6.2f}  SD {s.std():>5.2f}  "
              f"p10 {s.quantile(.1):>6.2f}  p90 {s.quantile(.9):>6.2f}")

    # ---- how much of a game's total is even kickable
    fgp = fg.copy()
    fgp["pts"] = 3 * fgp["fgm"].astype(float)
    tot_fg = fgp.groupby(["season", "game_id"])["pts"].sum()
    print(f"\nScoring context  mean FG points per game {tot_fg.mean():.2f} "
          f"of a {df['points'].mean():.1f}-point game "
          f"({100 * tot_fg.mean() / df['points'].mean():.1f}%)")

    # ---- power, computed BEFORE reading the estimates
    pers = persistence(paar)
    ceil = mechanical_ceiling(feat, df["q_sum"].std())
    print("\n" + "-" * 78)
    print("PRE-RUN POWER  (from persistence, not from the fitted coefficients)")
    print("-" * 78)
    print(f"  Raw PAAR year-over-year r = {pers['r']:.3f}  "
          f"(n={pers['n']} team-season pairs)")
    print(f"  Prior shrunk quality -> current PAAR/game: slope {ceil['slope']:.3f} "
          f"+/- {ceil['slope_se']:.3f}  (n={ceil['n']})")
    print(f"  -> mechanical ceiling on the MEAN effect: "
          f"{ceil['pts_per_game_per_sd']:.3f} pts/game per 1 SD of q_sum "
          f"(upper 95%: {ceil['hi_pts_per_game_per_sd']:.3f})")
    print("     a ceiling: it assumes the market prices none of the kicker's value")

    try:
        from toolkit.power import mde as mde_fn, deff
        n_clusters = df["ts_home"].nunique()
        cl = len(df) / n_clusters
        sd_r = float(df["resid"].std())
        m_iid = mde_fn(sd=sd_r, n=len(df))
        de = deff(cluster_size=cl, icc=0.02)
        m_cl = mde_fn(sd=sd_r, n=len(df), d_eff=de)
        print(f"  MDE (80% power, a=0.05) iid                      : {m_iid:.3f} pts")
        print(f"  MDE clustered (m={cl:.1f}, ICC=0.02, d_eff={de:.2f})  : {m_cl:.3f} pts")
        ratio = m_cl / max(ceil["hi_pts_per_game_per_sd"], 1e-9)
        verdict = ("UNDERPOWERED -- cannot see an effect of the ceiling size"
                   if ratio > 1 else "powered for a ceiling-sized effect")
        print(f"  MDE / ceiling(upper 95%) = {ratio:.0f}x  ->  {verdict}")
    except Exception as exc:  # toolkit not on path
        print(f"  (power toolkit unavailable: {exc})")

    # ---- primary A: mean shift
    print("\n" + "-" * 78)
    print("PRIMARY A  mean shift -- does kicker quality move the residual?")
    print("-" * 78)
    fit_a, names_a = twoway_ols(df, "resid", ["q_sum", "v_sum"])
    rows = report_fit(fit_a, names_a, "A: resid ~ quality + volatility", "points")

    # Economic translation: what over-rate would the most favourable value the data
    # permits actually buy?
    #
    # Anchor on the EMPIRICAL over rate, not Phi(0). The residual is right-skewed
    # (blowouts pull the mean above the median), so a normal model evaluated at the
    # sample mean overstates the over rate by ~1.6pp and would flatter the result.
    # The local slope is the kernel density of the residual at zero -- pp of over rate
    # bought per point of mean shift.
    from scipy.stats import gaussian_kde
    r = df["resid"].to_numpy(float)
    dec = r[r != 0]
    base = float((dec > 0).mean())
    slope = float(gaussian_kde(r)(0.0)[0])       # per point; x100 for pp
    breakeven = 110 / 210                        # -110 both sides
    print(f"\n  Economic bound: over rate ~ {100 * base:.2f}% (empirical base) "
          f"+ shift x {100 * slope:.2f}pp/pt (density at 0)")
    print(f"  break-even at -110 is {100 * breakeven:.2f}%")
    for lab, d in [("mechanical ceiling (upper 95%)", ceil["hi_pts_per_game_per_sd"]),
                   ("fitted coefficient", float(fit_a.params[1])),
                   ("CI UPPER BOUND on the coefficient", float(fit_a.conf_int()[1][1]))]:
        rate = base + d * slope
        verdict = "beats the vig" if rate > breakeven else "below break-even"
        print(f"    {lab:<36} {d:+.3f} pts -> {100 * rate:.2f}% over  ({verdict})")
    need = (breakeven - base) / slope
    print(f"    {'shift needed to break even':<36} {need:+.3f} pts "
          f"({need / max(ceil['hi_pts_per_game_per_sd'], 1e-9):.0f}x the ceiling)")

    # ---- primary B: dispersion
    print("\n" + "-" * 78)
    print("PRIMARY B  dispersion -- does kicker volatility widen the residual?")
    print("-" * 78)
    df = df.assign(abs_resid=df["resid"].abs())
    dc = dispersion_ceiling(fg, float(df["resid"].std()), float(df["v_sum"].std()),
                            range(SEASON_MIN, SEASON_MAX + 1))
    print(f"  Ceiling: at {dc['att_per_game']:.2f} FG attempts/team-game and a "
          f"{100 * dc['make_rate']:.1f}% make rate, 1 SD of v_sum adds "
          f"{dc['d_var']:.2f} to the residual VARIANCE")
    print(f"           = {dc['d_sd']:+.3f} pts of residual SD "
          f"= {dc['d_mean_abs']:+.3f} pts of E|resid|, the units of model B")

    fit_b, names_b = twoway_ols(df, "abs_resid", ["v_sum", "q_sum"])
    rows += report_fit(fit_b, names_b, "B: |resid| ~ volatility + quality", "points")

    z_sum = 1.959963985 + 0.8416212336  # alpha=0.05 two-sided, 80% power
    mde_b = z_sum * float(fit_b.bse[1])
    print(f"\n  MDE for model B (80% power from the clustered SE): {mde_b:.3f} pts")
    print(f"  MDE / ceiling = {mde_b / max(dc['d_mean_abs'], 1e-9):.0f}x  ->  "
          f"{'UNDERPOWERED -- cannot see a ceiling-sized effect' if mde_b > dc['d_mean_abs'] else 'powered'}")

    from scipy import stats as sps
    tv = pd.qcut(df["v_sum"], 3, labels=["low", "mid", "high"])
    grp = [df.loc[tv == t, "resid"].to_numpy() for t in ["low", "mid", "high"]]
    lev = sps.levene(*grp, center="median")
    sds = [g.std(ddof=1) for g in grp]
    print(f"\n  Residual SD by volatility tercile: "
          f"low {sds[0]:.2f}  mid {sds[1]:.2f}  high {sds[2]:.2f}")
    print(f"  Levene (median-centred): W={lev.statistic:.3f}, p={lev.pvalue:.3f}")

    # ---- descriptive cover rates (NOT the decision)
    print("\n" + "-" * 78)
    print("DESCRIPTIVE  cover rates by tercile (thresholded, lower power than the above)")
    print("-" * 78)
    trows = tercile_table(df, "q_sum", "quality")
    trows += tercile_table(df, "v_sum", "volatility")

    pvals = [sps.binomtest(r["over"], r["n"], 0.5).pvalue if r["n"] else 1.0
             for r in trows]
    try:
        from toolkit.multiplicity import holm
        h = holm(pvals, alpha=0.05)
        print(f"\n  Holm across the {len(pvals)} tercile tests vs 50%: "
              f"{int(np.sum(h['reject']))} reject at a=0.05 (raw min p={min(pvals):.3f})")
    except Exception:
        print(f"\n  raw min p across {len(pvals)} tercile tests = {min(pvals):.3f} "
              f"(Bonferroni threshold {0.05 / len(pvals):.4f})")

    # ---- sensitivity: the secondary volatility measure
    print("\n" + "-" * 78)
    print("SENSITIVITY  secondary volatility measure (raw FG-points SD, volume-contaminated)")
    print("-" * 78)
    dfc = df.dropna(subset=["sd_sum"])
    fit_c, names_c = twoway_ols(dfc, "abs_resid", ["sd_sum", "q_sum"])
    rows += report_fit(fit_c, names_c, "C: |resid| ~ fg_pts_sd + quality", "points")

    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_csv(out / "kicker_totals_coefs.csv", index=False)
        pd.DataFrame(trows).to_csv(out / "kicker_totals_terciles.csv", index=False)
        print(f"\nwrote {out}/kicker_totals_coefs.csv and kicker_totals_terciles.csv")
    return 0


def self_check() -> int:
    """Synthetic panel with a KNOWN injected effect -- does the estimator recover it?"""
    rng = np.random.default_rng(7)
    n_teams, seasons, gpt = 130, range(2018, 2026), 12
    qual = {(t, s): rng.normal(0, 0.30) for s in seasons for t in range(n_teams)}
    beta = 0.50  # points per unit of q_sum
    rows = []
    for s in seasons:
        for t in range(n_teams):
            for _ in range(gpt):
                o = int(rng.integers(0, n_teams))
                qs = qual[(t, s)] + qual[(o, s)]
                rows.append(dict(
                    season=s, home_team=f"T{t}", away_team=f"T{o}",
                    quality_h=qual[(t, s)], quality_a=qual[(o, s)],
                    phi_h=rng.normal(1, .2), phi_a=rng.normal(1, .2),
                    resid=beta * qs + rng.normal(0, 16),
                ))
    df = pd.DataFrame(rows)
    df["q_sum"] = df["quality_h"] + df["quality_a"]
    df["v_sum"] = df["phi_h"] + df["phi_a"]
    df["ts_home"] = df["home_team"] + "|" + df["season"].astype(str)
    df["ts_away"] = df["away_team"] + "|" + df["season"].astype(str)
    fit, _ = twoway_ols(df, "resid", ["q_sum", "v_sum"])
    truth = beta * df["q_sum"].std(ddof=1)  # coefficient is per 1 SD of q_sum
    est, (lo, hi) = fit.params[1], fit.conf_int()[1]
    ok = lo <= truth <= hi
    print(f"self-check  injected {truth:.3f} pts/SD, recovered {est:.3f} "
          f"[{lo:.3f},{hi:.3f}] -> {'PASS' if ok else 'FAIL'}")

    p, lo2, hi2 = wilson(50, 100)
    ok2 = abs(p - .5) < 1e-12 and lo2 < .5 < hi2
    print(f"self-check  wilson(50,100) = {p:.3f} [{lo2:.3f},{hi2:.3f}] "
          f"-> {'PASS' if ok2 else 'FAIL'}")

    # a truly null effect must NOT be flagged
    df2 = df.assign(resid=rng.normal(0, 16, len(df)))
    fit2, _ = twoway_ols(df2, "resid", ["q_sum", "v_sum"])
    ok3 = fit2.pvalues[1] > 0.05
    print(f"self-check  null panel p={fit2.pvalues[1]:.3f} -> {'PASS' if ok3 else 'FAIL'}")
    return 0 if (ok and ok2 and ok3) else 1


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=None, help="directory for the coefficient/tercile CSVs")
    ap.add_argument("--cache", default=None,
                    help="parquet cache dir for the loaded frames (survives a locked warehouse)")
    ap.add_argument("--self-check", action="store_true",
                    help="recover a known injected effect on synthetic data")
    args = ap.parse_args()
    return self_check() if args.self_check else run(args)


if __name__ == "__main__":
    raise SystemExit(main())
