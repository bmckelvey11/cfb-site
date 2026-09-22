"""Can team-level PFF stats filter the Greenline unders? Not yet — the power gate says no.

The feature family is new (PFF team quality and tendency, which no prior look has touched),
the harness is `under_filters.py`'s. What stops it is the join: `stg.pff_*` covers seasons
2025 and 2026 only, and of the 267 Greenline-only unders, exactly the **88 in the 2026 flag
era** can carry a PFF feature. The 2020 PFF_hist (122) and 2022-23 export (57) eras have no
PFF data at all. MDE at n=88 is **65.6%** against a 52.38% break-even — a filter would have
to hit two-thirds of its kept games before this sample could tell it from noise. So this
script computes the gate, reports it, and does not run the feature search.

The personal 2023-25 book unders are deliberately NOT pooled in to lift n. Pooling them
would put this at n=180 and MDE 61.6%, which clears the gate — and it is exactly the premise
`under_filters.py` retracted on 2026-09-22 after `pool_totals_record.overlap()` measured
that 3 of 12 checkable personal bets took the side Greenline flagged *against*. A sample
that disagrees with the vendor on a quarter of checkable picks cannot be borrowed to make a
statement about the vendor's picks.

The feature builder below is written, self-checked, and left ready for the rerun. The five
features are registered here, 2026-09-22, before any result was seen. Each requires **both**
relevant teams on the under side of the FBS median for that window — the conjunctive form
`under_filters.slow` already uses. Holm would run across all five; a sixth may not be added.

    pass_rush   both defenses' pressure rate, total_pressures / pass_rush_opp.
                High pressure suppresses passing efficiency, so high is the under side.
    run_heavy   both offenses' pass-snap rate. Run-heavy offenses bleed clock and take
                possessions out of the game, so low is the under side.
    no_deep     both offenses' deep-attempt share of targeted attempts. Fewer shots
                downfield is fewer cheap scores, so low is the under side.
    weak_qb     both offenses' dropback-weighted PFF passing grade. Bad quarterback play
                stalls drives, so low is the under side.
    coverage    both defenses' coverage-snap-weighted PFF coverage grade. Good coverage
                takes away the explosive pass, so high is the under side.

Feature construction, and why 2026 cannot use season-to-date:

    PFF 2026 is loaded through week 2 and the graded flags are weeks 2-3, so a to-date
    window would be one or two games. The 2026 rows therefore take the **2025 full regular
    season** (weeks 0-14) for both teams — a complete, published fact months before kickoff,
    and what a bettor actually knew. Season-to-date is implemented and used for any row in a
    season PFF covers from its start; it needs two games of volume to qualify.

No lookahead: a to-date window ends strictly before the game's own week and is capped at
week 14, so a postseason game (CFBD week >= 15, PFF week 17-18) cannot see itself. PFF and
CFBD regular-season week numbering was checked to agree on three teams' bye fingerprints.
Medians come from the same window as the value they threshold, never from the bet sample.

Run from repo root:
    python research/totals/scripts/pff_under_filters.py
    python research/totals/scripts/pff_under_filters.py --self-check
"""
from __future__ import annotations

import argparse
import math
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research" / "totals" / "scripts"))
sys.path.insert(0, str(ROOT / "research" / "bankroll" / "scripts"))

from cfb_paths import DB_PATH  # noqa: E402
from greenline_season_review import BREAK_EVEN, mde, wilson  # noqa: E402
from under_filters import evaluate, greenline_unders, rec  # noqa: E402

# The only era PFF can reach. `stg.pff_*` starts at 2025.
PFF_ERA = "2026 flags"
# Above this, a filter cannot be told from noise on the kept rows, so the search is not run.
MDE_GATE = 0.65

# name, side of the median that is the under side, description
FEATURES = [
    ("pass_rush", "high", "both defenses' pressure rate at or above the FBS median"),
    ("run_heavy", "low", "both offenses' pass-snap rate at or below the FBS median"),
    ("no_deep", "low", "both offenses' deep-attempt rate at or below the FBS median"),
    ("weak_qb", "low", "both offenses' passing grade at or below the FBS median"),
    ("coverage", "high", "both defenses' coverage grade at or above the FBS median"),
]

FILTERS = [(n, d, (lambda n: lambda f: f.get(n))(n)) for n, _, d in FEATURES]

# Two games of volume before a to-date value counts. Below this the team falls out of the
# median distribution too, so one blowout cannot move the threshold.
MIN_DROPBACKS = 30
MIN_DEF_SNAPS = 100
LAST_REGULAR_WEEK = 14

# NaN, not NULL, is how an absent PFF numeric arrives -- see docs/pff-scheme-inventory-2026-09-16.md.
_FIN = "case when {c} is null or isnan({c}) then 0 else {c} end"

QUALITY_SQL = f"""
with pr as (
    select franchise_id,
           sum(total_pressures) as pressures,
           sum(pass_rush_opp)   as opps
    from stg.pff_defense_pass_rush
    where season = ? and week between ? and ? and split = 'all'
    group by 1
),
cov as (
    select franchise_id,
           sum({_FIN.format(c='grades_coverage_defense')} * snap_counts_coverage) as g,
           sum(case when grades_coverage_defense is null or isnan(grades_coverage_defense)
                    then 0 else snap_counts_coverage end)                         as w
    from stg.pff_defense_coverage
    where season = ? and week between ? and ? and split = 'all'
    group by 1
),
qb as (
    select franchise_id,
           sum({_FIN.format(c='grades_pass')} * dropbacks) as g,
           sum(case when grades_pass is null or isnan(grades_pass) then 0 else dropbacks end) as w
    from stg.pff_passing
    where season = ? and week between ? and ? and split = 'all'
    group by 1
)
select f.cfbd_team_id,
       case when pr.opps > 0 then pr.pressures::double / pr.opps end as pass_rush,
       case when cov.w > 0 then cov.g / cov.w end                    as coverage,
       case when qb.w >= ? then qb.g / qb.w end                      as weak_qb,
       cov.w as def_cov_snaps, qb.w as dropbacks
from pr
join cov using (franchise_id)
join qb using (franchise_id)
join stg.pff_franchise f using (franchise_id)
where f.cfbd_team_id is not null
"""


def _nan(x) -> bool:
    return isinstance(x, float) and math.isnan(x)


def team_window(con, season: int, weeks: tuple[int, int]) -> dict[int, dict]:
    """The five team-level values for one season and week window, keyed by cfbd_team_id.

    A team below either volume floor is dropped entirely: it has no usable value and it
    does not enter the median."""
    from scripts.pff_scheme_profile import profile

    params = []
    for _ in range(3):
        params += [season, weeks[0], weeks[1]]
    params.append(MIN_DROPBACKS)
    out = {}
    for tid, pass_rush, coverage, weak_qb, cov_snaps, dropbacks in con.execute(QUALITY_SQL, params).fetchall():
        if tid is None or cov_snaps is None or cov_snaps < MIN_DEF_SNAPS:
            continue
        if None in (pass_rush, coverage, weak_qb) or (dropbacks or 0) < MIN_DROPBACKS:
            continue
        out[int(tid)] = {"pass_rush": pass_rush, "coverage": coverage, "weak_qb": weak_qb}

    for row in profile(con, season, weeks).itertuples():
        tid = row.cfbd_team_id
        if tid is None or int(tid) not in out:
            continue
        pace, deep = row.off_pass_snap_rate, row.off_deep_attempt_rate
        if pace is None or deep is None or any(map(_nan, (pace, deep))):
            out.pop(int(tid))
            continue
        out[int(tid)].update(run_heavy=float(pace), no_deep=float(deep))
    return {t: v for t, v in out.items() if "run_heavy" in v}


def medians(window: dict[int, dict]) -> dict[str, float]:
    return {n: statistics.median([v[n] for v in window.values()]) for n, _, _ in FEATURES}


def tag(home: dict | None, away: dict | None, med: dict[str, float]) -> dict[str, bool | None]:
    """One game's five booleans. Both teams must be on the under side of the median."""
    if not home or not away:
        return {n: None for n, _, _ in FEATURES}
    out = {}
    for name, side, _ in FEATURES:
        h, a = home[name], away[name]
        out[name] = (h >= med[name] and a >= med[name]) if side == "high" \
            else (h <= med[name] and a <= med[name])
    return out


def build(rows: list[dict]) -> tuple[dict[int, dict], dict[str, int]]:
    """Feature booleans per game_id, plus how each row's features were constructed."""
    import duckdb

    con = duckdb.connect(str(DB_PATH), read_only=True)
    con.execute("create temp table ids (game_id integer)")
    con.executemany("insert into ids values (?)", [(r["game_id"],) for r in rows])
    meta = {int(g): (int(s), int(w), int(h), int(a)) for g, s, w, h, a in con.execute(
        "select game_id, season, week, home_team_id, away_team_id from core.fact_game "
        "where game_id in (select game_id from ids)").fetchall()}

    windows: dict[tuple[int, int, int], tuple[dict, dict]] = {}

    def window(season: int, weeks: tuple[int, int]):
        key = (season, *weeks)
        if key not in windows:
            w = team_window(con, season, weeks)
            windows[key] = (w, medians(w) if w else {})
        return windows[key]

    feats, how = {}, {"to_date": 0, "prior_season": 0, "missing": 0}
    for r in rows:
        m = meta.get(r["game_id"])
        if not m:
            how["missing"] += 1
            feats[r["game_id"]] = {n: None for n, _, _ in FEATURES}
            continue
        season, week, home, away = m
        if season == 2026:  # PFF 2026 is one to two games deep -- use the completed 2025 season
            teams, med = window(2025, (0, LAST_REGULAR_WEEK))
            kind = "prior_season"
        else:
            teams, med = window(season, (0, min(week, LAST_REGULAR_WEEK + 1) - 1))
            kind = "to_date"
        f = tag(teams.get(home), teams.get(away), med) if med else {n: None for n, _, _ in FEATURES}
        how[kind if f[FEATURES[0][0]] is not None else "missing"] += 1
        feats[r["game_id"]] = f
    con.close()
    return feats, how


# ---------------------------------------------------------------- entry

def self_check() -> None:
    med = {n: 0.5 for n, _, _ in FEATURES}
    hi = {n: 0.9 for n, _, _ in FEATURES}
    lo = {n: 0.1 for n, _, _ in FEATURES}
    t = tag(hi, hi, med)
    assert t["pass_rush"] is True and t["coverage"] is True, t
    assert t["run_heavy"] is False and t["no_deep"] is False and t["weak_qb"] is False, t
    assert tag(lo, hi, med)["pass_rush"] is False, "both teams are required, either way"
    assert all(v is None for v in tag(None, hi, med).values())
    assert medians({1: {n: 1.0 for n, _, _ in FEATURES}, 2: {n: 3.0 for n, _, _ in FEATURES}})["no_deep"] == 2.0

    rows = [{"era": PFF_ERA, "game_id": i, "date": f"2026-09-{12 + i % 2:02d}", "line": 48.5,
             "result": "win" if i % 2 else "loss"} for i in range(40)]
    feats = {r["game_id"]: tag(hi if r["game_id"] % 2 else lo, hi if r["game_id"] % 2 else lo, med)
             for r in rows}
    res = evaluate(rows, feats, FILTERS)
    by = {r["name"]: r for r in res}
    assert len(res) == 5 and by["pass_rush"]["n_tagged"] == 40
    assert sum(by["pass_rush"]["pooled_on"]) == 20
    assert all(0 <= r["p_holm"] <= 1 for r in res if not math.isnan(r["p_holm"]))
    assert mde(88) > MDE_GATE, "the gate this script reports must still bind at n=88"
    print("self-check ok")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--self-check", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="run the feature search even when the gate fails (prints the MDE anyway)")
    a = ap.parse_args()
    if a.self_check:
        self_check()
        return

    rows = [r for r in greenline_unders() if r["era"] == PFF_ERA]
    w, l = rec(rows)
    n = w + l
    lo, hi = wilson(w, n)
    print(f"PFF-joinable Greenline unders: {n} ({PFF_ERA} only; the 2020 and 2022-23 eras "
          f"predate the PFF tables)\n"
          f"  record {w}-{l} ({w / n * 100:.1f}%, 95% Wilson {lo * 100:.0f}-{hi * 100:.0f}%)\n"
          f"  MDE {mde(n) * 100:.1f}% vs break-even {BREAK_EVEN * 100:.2f}%, gate {MDE_GATE * 100:.0f}%")
    if mde(n) > MDE_GATE and not a.force:
        print(f"\nGATE FAILED: {mde(n) * 100:.1f}% > {MDE_GATE * 100:.0f}%. The feature search is not run.\n"
              "A filter keeping half these games would need roughly 70% on what it keeps before this\n"
              "sample could tell it from noise. Rerun when the 2026 flag board has graded enough unders\n"
              "to bring the MDE under the gate, or when PFF data reaches another graded era.")
        return

    feats, how = build(rows)
    print(f"construction: {how}")
    res = evaluate(rows, feats, FILTERS)
    print(f"\n{'feature':<11} {'on':>9} {'off':>9} {'CMH p':>7} {'Holm p':>7} {'MDE on':>7}")
    for r in res:
        on, off = r["pooled_on"], r["pooled_off"]
        print(f"{r['name']:<11} {on[0]:>4}-{on[1]:<4} {off[0]:>4}-{off[1]:<4} "
              f"{r['cmh_p']:>7.3f} {r['p_holm']:>7.3f} {r['mde_on'] * 100:>6.0f}%")


if __name__ == "__main__":
    main()
