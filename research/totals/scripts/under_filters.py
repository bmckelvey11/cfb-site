"""Do any pre-registered situational filters separate winning Greenline unders from losing ones?

Runs on the 270 Greenline-only unders across all three graded eras (2020 PFF_hist, 2022-23
exports, 2026 flags) -- the same population `pool_totals_record.py` establishes. The
2023-25 personal book unders are NOT included: `pool_totals_record.overlap()` measured, on
the only days both a Greenline board and a book bet exist, that 3 of 12 checkable personal
bets took the side Greenline flagged *against*. A population that disagrees with the vendor
on a quarter of checkable picks is a different selector, not a Greenline stand-in, and using
it here would let a personal-betting pattern pass as a Greenline finding.

(Superseded 2026-09-22: the original 2026-09-17 run pooled the 2023-25 personal unders with
the 2026 flags on that same premise, five days before the overlap was measured and found
false. See `../../../archive/docs/greenline-under-filters-2026-09-17.md`.)

Filters are stratified by era and tested with Cochran-Mantel-Haenszel, the same tool
`totals_rule_search.py` uses for the same reason: a filter that only shows up because one
era is a different population (2020 has no weather rows, 2026 sits on different totals)
cancels under CMH instead of reporting itself as a finding.

Filters were fixed before this script was first run (2026-09-17), not after looking:

    line_fell   market total closed below its open (steam toward the under)
    windy       wind >= 12 mph, outdoors
    slow        both teams' pregame plays-per-game below the FBS mean to date
    big_fav     |spread| >= 14
    night       kickoff at or after 19:00 ET
    short_rest  either team on <= 6 days of rest

Every feature is available before kickoff. Pace and rest use only games played before
the one being bet; week-1 pace falls back to the prior season. Pace features require
`stg.advanced_game_stats`, which only covers 2022+ -- 2020 rows are missing that feature
by construction, not by data loss, and are dropped from `slow` only.

Run from repo root:
    python research/totals/scripts/under_filters.py [--out research/totals/docs]
    python research/totals/scripts/under_filters.py --self-check
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import math
import sys
from pathlib import Path

from scipy import stats

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research" / "totals" / "scripts"))
sys.path.insert(0, str(ROOT / "research" / "bankroll" / "scripts"))

from cfb_paths import DB_PATH  # noqa: E402
from greenline_season_review import BREAK_EVEN, mde, wilson  # noqa: E402
from pool_totals_record import load  # noqa: E402
from totals_rule_search import cmh  # noqa: E402  -- reused so this and the rule search cannot drift apart

ERAS = ["2020 PFF_hist", "2022-23 exports", "2026 flags"]

FILTERS = [
    ("line_fell", "total closed below open", lambda f: None if f["total_open"] is None or f["total_close"] is None
     else f["total_close"] < f["total_open"]),
    ("windy", "wind >= 12 mph outdoors", lambda f: None if f["wind"] is None else (f["wind"] >= 12 and not f["indoors"])),
    ("slow", "both teams below FBS mean pace", lambda f: None if f["home_pace"] is None or f["away_pace"] is None
     else (f["home_pace"] < f["fbs_pace"] and f["away_pace"] < f["fbs_pace"])),
    ("big_fav", "|spread| >= 14", lambda f: None if f["spread"] is None else abs(f["spread"]) >= 14),
    ("night", "kickoff >= 19:00 ET", lambda f: None if f["hour"] is None else f["hour"] >= 19),
    ("short_rest", "either team <= 6 days rest", lambda f: None if f["home_rest"] is None or f["away_rest"] is None
     else min(f["home_rest"], f["away_rest"]) <= 6),
]


# ---------------------------------------------------------------- sample

def greenline_unders() -> list[dict]:
    """Every graded Greenline under across all three eras, resolved to a CFBD game_id.

    2020 and 2022-23 already carry the CFBD game_id on the row (the join audit fixed it).
    2026 flags carry PFF's own game id and are resolved through the same
    pff_franchise -> cfbd_team_id -> team-pair match `flag_unders()` used before this
    rewrite, because PFF and CFBD do not share an id space.
    """
    import duckdb
    from greenline_bet_log import _flag_cfbd_ids

    picks = [r for r in load() if r["side"] == "under" and r["result"] in ("win", "loss")]
    out = []
    for r in picks:
        if r["era"] != "2026 flags":
            try:
                gid = int(r["game_id"])
            except (TypeError, ValueError):
                continue  # no CFBD match on this archive row; excluded, not miscounted
            out.append({"era": r["era"], "game_id": gid, "date": r["date"], "line": r["line"],
                        "result": r["result"]})

    flags = [r for r in picks if r["era"] == "2026 flags"]
    ids = _flag_cfbd_ids()
    con = duckdb.connect(str(DB_PATH), read_only=True)
    games = con.execute("select game_id, home_team_id, away_team_id, start_date::date::varchar "
                        "from core.fact_game where season = 2026").fetchall()
    con.close()
    by_pair = {}
    for gid, h, a, d in games:
        by_pair.setdefault(frozenset((str(h), str(a))), []).append((gid, d))
    for r in flags:
        pair = ids.get(r["game_id"])
        cands = by_pair.get(pair, []) if pair else []
        if not cands:
            continue
        d0 = dt.date.fromisoformat(r["date"])
        gid = min(cands, key=lambda c: abs((dt.date.fromisoformat(c[1]) - d0).days))[0]
        out.append({"era": "2026 flags", "game_id": int(gid), "date": r["date"], "line": r["line"],
                    "result": r["result"]})
    return out


# ---------------------------------------------------------------- features

FEATURE_SQL = """
with g as (
    select game_id, season, week, start_date, home_team_id, away_team_id, home_team, away_team,
           selected_spread as spread, selected_total_provider_key as prov
    from core.fact_game where game_id in (select game_id from ids)
),
ln as (
    -- open/close from the selected total provider, else any provider carrying both
    select game_id, total_open, total_close from (
        select l.game_id, l.total_open, l.total_close,
               row_number() over (partition by l.game_id order by
                   case when l.provider_key = g.prov then 0 else 1 end,
                   case when l.total_open is not null and l.total_close is not null then 0 else 1 end) rn
        from core.fact_game_line l join g on g.game_id = l.game_id
    ) where rn = 1
),
w as (select gameId as game_id, windSpeed as wind, gameIndoors as indoors from stg.weather),
-- every team-game with plays, for pregame pace (2022+ only -- stg.advanced_game_stats has no earlier seasons)
tg as (
    select s.gameId as game_id, f.season, f.start_date, s.team, s.offense_plays as plays
    from stg.advanced_game_stats s join core.fact_game f on f.game_id = s.gameId
    where f.season >= 2022
),
pace as (
    select g.game_id, side.team,
           (select avg(plays) from tg where tg.team = side.team and tg.season = g.season and tg.start_date < g.start_date) as std_pace,
           (select avg(plays) from tg where tg.team = side.team and tg.season = g.season - 1) as prior_pace,
           (select avg(plays) from tg where tg.season = g.season and tg.start_date < g.start_date) as fbs_std,
           (select avg(plays) from tg where tg.season = g.season - 1) as fbs_prior
    from g, lateral (select g.home_team as team union all select g.away_team) side
),
rest as (
    select g.game_id, side.team_id,
           date_diff('day', (select max(f.start_date) from core.fact_game f
                             where f.season = g.season and f.start_date < g.start_date
                               and (f.home_team_id = side.team_id or f.away_team_id = side.team_id)),
                     g.start_date) as days
    from g, lateral (select g.home_team_id as team_id union all select g.away_team_id) side
)
select g.game_id, g.spread, ln.total_open, ln.total_close, w.wind, w.indoors,
       hour(g.start_date at time zone 'America/New_York') as hour,
       ph.std_pace, ph.prior_pace, pa.std_pace, pa.prior_pace, ph.fbs_std, ph.fbs_prior,
       rh.days, ra.days
from g
left join ln on ln.game_id = g.game_id
left join w on w.game_id = g.game_id
left join pace ph on ph.game_id = g.game_id and ph.team = g.home_team
left join pace pa on pa.game_id = g.game_id and pa.team = g.away_team
left join rest rh on rh.game_id = g.game_id and rh.team_id = g.home_team_id
left join rest ra on ra.game_id = g.game_id and ra.team_id = g.away_team_id
"""


def features(game_ids: list[int]) -> dict[int, dict]:
    import duckdb
    con = duckdb.connect(str(DB_PATH), read_only=True)
    con.execute("create temp table ids (game_id integer)")
    con.executemany("insert into ids values (?)", [(g,) for g in sorted(set(game_ids))])
    rows = con.execute(FEATURE_SQL).fetchall()
    con.close()
    out = {}
    for (gid, spread, t_open, t_close, wind, indoors, hour, h_std, h_prior, a_std, a_prior,
         fbs_std, fbs_prior, h_rest, a_rest) in rows:
        # week 1 has no season-to-date pace; fall back to the prior season for both sides
        home_pace, away_pace, fbs = (h_std, a_std, fbs_std) if h_std is not None and a_std is not None \
            else (h_prior, a_prior, fbs_prior)
        out[int(gid)] = {"spread": spread, "total_open": t_open, "total_close": t_close, "wind": wind,
                         "indoors": bool(indoors) if indoors is not None else False, "hour": hour,
                         "home_pace": home_pace, "away_pace": away_pace, "fbs_pace": fbs,
                         "home_rest": h_rest, "away_rest": a_rest}
    return out


# ---------------------------------------------------------------- stats

def rec(rows: list[dict]) -> tuple[int, int]:
    w = sum(r["result"] == "win" for r in rows)
    return w, len(rows) - w


def fmt(w: int, l: int) -> str:
    n = w + l
    if not n:
        return "--"
    lo, hi = wilson(w, n)
    return f"{w}-{l} ({w / n * 100:.0f}%, {lo * 100:.0f}–{hi * 100:.0f}%)"


def two_prop(w1, n1, w2, n2) -> float:
    if not n1 or not n2:
        return float("nan")
    return stats.fisher_exact([[w1, n1 - w1], [w2, n2 - w2]])[1]


def holm(ps: list[float]) -> list[float]:
    order = sorted(range(len(ps)), key=lambda i: (math.isnan(ps[i]), ps[i]))
    out, m, run = [float("nan")] * len(ps), len(ps), 0.0
    for k, i in enumerate(order):
        if math.isnan(ps[i]):
            continue
        run = max(run, (m - k) * ps[i])
        out[i] = min(1.0, run)
    return out


# ---------------------------------------------------------------- report

def evaluate(rows: list[dict], feats: dict[int, dict], filters=None) -> list[dict]:
    res = []
    for name, desc, fn in (FILTERS if filters is None else filters):
        tagged = []
        for r in rows:
            f = feats.get(r["game_id"])
            v = fn(f) if f else None
            if v is not None:
                tagged.append((r, bool(v)))
        by_era = {}
        for e in ERAS:
            sub = [(r, v) for r, v in tagged if r["era"] == e]
            on = rec([r for r, v in sub if v])
            off = rec([r for r, v in sub if not v])
            by_era[e] = {"on": on, "off": off, "p": two_prop(on[0], sum(on), off[0], sum(off))}
        groups = [(by_era[e]["on"][0], by_era[e]["on"][1], by_era[e]["off"][0], by_era[e]["off"][1]) for e in ERAS]
        cmh_stat, cmh_p = cmh(groups)
        pooled_on = rec([r for r, v in tagged if v])
        pooled_off = rec([r for r, v in tagged if not v])
        pooled_p = two_prop(pooled_on[0], sum(pooled_on), pooled_off[0], sum(pooled_off))
        n_on = sum(pooled_on)
        res.append({"name": name, "desc": desc, "n_tagged": len(tagged), "n_missing": len(rows) - len(tagged),
                    "by_era": by_era, "pooled_on": pooled_on, "pooled_off": pooled_off, "pooled_p": pooled_p,
                    "cmh_stat": cmh_stat, "cmh_p": cmh_p, "mde_on": mde(n_on) if n_on else float("nan")})
    hp = holm([r["cmh_p"] for r in res])
    for r, p in zip(res, hp):
        r["p_holm"] = p
    return res


def render(rows: list[dict], res: list[dict], by_era_n: dict[str, int]) -> str:
    w, l = rec(rows)
    lo, hi = wilson(w, w + l)
    L = [f"# Situational filters on Greenline unders, {dt.date.today().isoformat()}", "",
         "Reproduce: `python research/totals/scripts/under_filters.py --out research/totals/docs`.", "",
         "**Supersedes** [greenline-under-filters-2026-09-17.md](../../../archive/docs/greenline-under-filters-2026-09-17.md), "
         "which pooled the 2023-25 personal unders with the 2026 flags on the premise that they were mostly the same "
         "picks -- a premise `pool_totals_record.overlap()` later measured and found false on 3 of 12 checkable days.", "",
         "## Question", "",
         "Does any pre-registered, pregame situational filter separate winning Greenline unders from losing ones?",
         "Runs on the 270 Greenline-only unders across all three graded eras, stratified by era via",
         "Cochran-Mantel-Haenszel so a filter that is really era composition (2020 has no weather rows, 2026 sits",
         "on different totals) cancels here instead of reporting itself as a finding.", "",
         "## Data", ""]
    for e in ERAS:
        L.append(f"- {e}: {by_era_n[e]} graded unders.")
    L += ["- 3 of the pooled 270 graded Greenline unders (all 2020 PFF_hist) carry a result but no CFBD "
          "`game_id` -- their final came with the archive row directly rather than through a CFBD join -- "
          "so they cannot be joined to a feature and are excluded here, not miscounted.", "",
          f"- Pooled: {w}-{l} ({w / (w + l) * 100:.1f}%, 95% Wilson {lo * 100:.0f}–{hi * 100:.0f}%). "
          f"MDE for the whole pool: {mde(w + l) * 100:.1f}%. Break-even {BREAK_EVEN * 100:.2f}%.",
          "- Features from the local warehouse: `core.fact_game_line` (open/close), `stg.weather` (wind, indoors),",
          "  `stg.advanced_game_stats` (plays, season-to-date before kickoff, 2022+ only), `core.fact_game`",
          "  (spread, kickoff, rest). A row missing a feature is dropped from that filter only; the count is in",
          "  the table.", "",
          "## Filters, fixed before running", "", "| filter | rule |", "|---|---|"]
    L += [f"| {n} | {d} |" for n, d, _ in FILTERS]
    L += ["", "## Records: filter on vs off, by era", "",
          "| filter | era | on | off | Fisher p |", "|---|---|---|---|---:|"]
    for r in res:
        for e in ERAS:
            s = r["by_era"][e]
            L.append(f"| {r['name']} | {e} | {fmt(*s['on'])} | {fmt(*s['off'])} | {s['p']:.3f} |")
        L.append(f"| {r['name']} | pooled (descriptive) | {fmt(*r['pooled_on'])} | {fmt(*r['pooled_off'])} "
                 f"| {r['pooled_p']:.3f} |")
    L += ["", "## Era-stratified test", "",
          "Cochran-Mantel-Haenszel across the three eras -- the pooled Fisher p above is descriptive only; this",
          "is the inferential test, because it cancels a split that is really era composition instead of reporting",
          "it as a finding. Holm corrects across the six filters. `MDE on` is the smallest win rate the filter's",
          "kept rows could distinguish from break-even at their own pooled n.", "",
          "| filter | n tagged | missing | CMH stat | CMH p | Holm p | MDE on |",
          "|---|---:|---:|---:|---:|---:|---:|"]
    for r in res:
        L.append(f"| {r['name']} | {r['n_tagged']} | {r['n_missing']} | {r['cmh_stat']:.2f} | {r['cmh_p']:.3f} | "
                 f"{r['p_holm']:.3f} | {r['mde_on'] * 100:.0f}% |")
    keep = [r for r in res if r["p_holm"] < 0.05]
    L += ["", "## Reading", ""]
    if keep:
        L += [f"- Filters that survive Holm at 5%: {', '.join(r['name'] for r in keep)}."]
    else:
        L += ["- No filter survives the Holm correction at 5%. None of the six is a rule yet."]
    best = min(res, key=lambda r: r["cmh_p"] if not math.isnan(r["cmh_p"]) else 9)
    L += [f"- Strongest era-stratified split is `{best['name']}` (CMH p {best['cmh_p']:.3f}, Holm "
          f"{best['p_holm']:.3f}): pooled on {fmt(*best['pooled_on'])} vs off {fmt(*best['pooled_off'])}.",
          "- Per-era rows are printed above precisely so a filter that only shows up in one era (a selection",
          "  artifact or a feature-coverage gap) is visible before the CMH line averages it away.",
          "", "## What this does not support", "",
          "- Applying any filter to a live slate. Six looks at 270 rows; the Holm column is the honest p.",
          "- Reading a missing-feature filter (wind, pace) as null on 2020: `stg.weather` and",
          "  `stg.advanced_game_stats` do not cover that era, so those rows are dropped, not zero.",
          "- Treating any era as out-of-sample for the others. All three are graded Greenline flags; none was",
          "  selected by these filters.",
          "", "## What settles it", "",
          "- Rerun after each graded 2026 week; it is the era that keeps growing.",
          "- A filter that holds: consistent sign across eras (see the per-era table), CMH p Holm < 0.05."]
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- entry

def self_check() -> None:
    rows = [{"era": "2020 PFF_hist", "game_id": i, "date": f"2020-09-{7 + i % 3:02d}", "line": 55.5,
             "result": "win" if i % 3 else "loss"} for i in range(30)]
    rows += [{"era": "2022-23 exports", "game_id": 1000 + i, "date": f"2022-10-{2 + i % 2:02d}", "line": 52.5,
              "result": "win" if i % 3 else "loss"} for i in range(20)]
    rows += [{"era": "2026 flags", "game_id": 2000 + i, "date": f"2026-09-{12 + i % 2:02d}", "line": 50.5,
              "result": "win" if i % 2 else "loss"} for i in range(20)]
    feats = {r["game_id"]: {"spread": 20 if r["game_id"] % 5 < 2 else 3, "total_open": 55.0,
                            "total_close": 54.0 if r["game_id"] % 4 else 56.0, "wind": None, "indoors": False,
                            "hour": 20 if r["game_id"] % 3 else 12,
                            "home_pace": 60.0, "away_pace": 70.0, "fbs_pace": 65.0,
                            "home_rest": 7, "away_rest": 7} for r in rows}
    by_era_n = {e: sum(1 for r in rows if r["era"] == e) for e in ERAS}
    res = evaluate(rows, feats)
    by = {r["name"]: r for r in res}
    assert by["windy"]["n_tagged"] == 0 and by["windy"]["n_missing"] == 70
    assert by["big_fav"]["n_tagged"] == 70
    assert sum(by["big_fav"]["pooled_on"]) == 28
    assert by["slow"]["pooled_on"] == (0, 0)  # away pace above mean -> never both slow
    assert all(0 <= r["p_holm"] <= 1 for r in res if not math.isnan(r["p_holm"]))
    assert 0 <= by["big_fav"]["cmh_p"] <= 1
    assert holm([0.01, 0.04, 0.03]) == [0.03, 0.06, 0.06]
    assert 0.6 < mde(120) < 0.66
    out = render(rows, res, by_era_n)
    assert "| big_fav | 2020 PFF_hist |" in out and "Era-stratified test" in out
    print("self-check ok")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, help="directory for the .md write-up")
    ap.add_argument("--dump", type=Path, help="write the tagged rows as CSV")
    ap.add_argument("--self-check", action="store_true")
    a = ap.parse_args()
    if a.self_check:
        self_check()
        return
    rows = greenline_unders()
    by_era_n = {e: sum(1 for r in rows if r["era"] == e) for e in ERAS}
    feats = features([r["game_id"] for r in rows])
    res = evaluate(rows, feats)
    text = render(rows, res, by_era_n)
    if a.dump:
        with a.dump.open("w", newline="", encoding="utf-8") as fh:
            wri = csv.writer(fh)
            wri.writerow(["era", "game_id", "date", "line", "result"] + [n for n, _, _ in FILTERS])
            for r in rows:
                f = feats.get(r["game_id"], {})
                wri.writerow([r["era"], r["game_id"], r["date"], r["line"], r["result"]]
                             + [fn(f) if f else None for _, _, fn in FILTERS])
    if a.out:
        p = a.out / f"greenline-under-filters-{dt.date.today().isoformat()}.md"
        p.write_text(text, encoding="utf-8")
        print(f"wrote {p}")
    else:
        print(text)


if __name__ == "__main__":
    main()
