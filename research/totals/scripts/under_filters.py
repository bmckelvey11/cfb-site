"""Do any pre-registered situational filters separate winning Greenline unders from losing ones?

The 2023-25 personal unders are treated as Greenline unders (they were mostly the same
flags, taken as bets) and pooled with the graded 2026 under flags. The two are kept as
strata: every filter reports history / 2026 / pooled, and the logistic fit carries a
source dummy plus a filter x source interaction so a population difference cannot pass
as a filter effect.

Filters were fixed before this script was run (2026-09-17), not after looking:

    line_fell   market total closed below its open (steam toward the under)
    windy       wind >= 12 mph, outdoors
    slow        both teams' pregame plays-per-game below the FBS mean to date
    big_fav     |spread| >= 14
    night       kickoff at or after 19:00 ET
    short_rest  either team on <= 6 days of rest

Every feature is available before kickoff. Pace and rest use only games played before
the one being bet; week-1 pace falls back to the prior season.

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

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research" / "totals" / "scripts"))
sys.path.insert(0, str(ROOT / "research" / "bankroll" / "scripts"))

from cfb_paths import DB_PATH, INGEST  # noqa: E402
from greenline_season_review import BREAK_EVEN, load, mde, personal_totals, wilson  # noqa: E402

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

def history_unders() -> list[dict]:
    """2023-25 bet unders with a warehouse game_id, via the bankroll unit's matcher."""
    import duckdb
    from under_selection_profile import attach, bet_unders, fbs_slate
    con = duckdb.connect(str(DB_PATH), read_only=True)
    bet, _, unmatched = attach(bet_unders(), fbs_slate(con))
    con.close()
    return [{"source": "history", "game_id": int(b["game_id"]), "date": b["date"], "line": b["line"],
             "result": b["result"]} for b in bet if b["result"] in ("win", "loss")]


def flag_unders(season: int = 2026) -> list[dict]:
    """Graded 2026 under flags with a warehouse game_id, via pff_franchise -> cfbd_team_id."""
    import duckdb
    from greenline_bet_log import _flag_cfbd_ids
    ids = _flag_cfbd_ids()
    graded, _ = load(season)
    rows = [r for r in graded if r["market"] == "total" and r["side"] == "under" and r["result"] in ("win", "loss")]
    con = duckdb.connect(str(DB_PATH), read_only=True)
    games = con.execute("select game_id, home_team_id, away_team_id, start_date::date::varchar "
                        "from core.fact_game where season = ?", [season]).fetchall()
    con.close()
    by_pair = {}
    for gid, h, a, d in games:
        by_pair.setdefault(frozenset((str(h), str(a))), []).append((gid, d))
    out = []
    for r in rows:
        pair = ids.get(r["pff_game_id"])
        cands = by_pair.get(pair, []) if pair else []
        if not cands:
            continue
        d0 = dt.date.fromisoformat(r["date"])
        gid = min(cands, key=lambda c: abs((dt.date.fromisoformat(c[1]) - d0).days))[0]
        out.append({"source": "2026", "game_id": int(gid), "date": r["date"], "line": r["line"],
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
-- every team-game with plays, for pregame pace
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


def logit_interaction(rows: list[dict], flag: list[bool]) -> dict:
    """win ~ filter + source + filter:source, SE clustered by calendar day.

    The interaction is only identified when all four filter x source cells hold both a
    win and a loss. Otherwise (a 3-0 cell, or a stratum with no tagged rows) it is
    dropped and the fit is filter + source, flagged `sep`."""
    import warnings
    import statsmodels.api as sm
    y = np.array([r["result"] == "win" for r in rows], dtype=float)
    f = np.array(flag, dtype=float)
    s = np.array([r["source"] == "2026" for r in rows], dtype=float)
    cells = [y[(f == a) & (s == b)] for a in (0, 1) for b in (0, 1)]
    sep = any(len(c) == 0 or c.min() == c.max() for c in cells)
    X = np.column_stack([np.ones(len(y)), f, s] + ([] if sep else [f * s]))
    if s.min() == s.max():  # one stratum only: source is constant
        X = X[:, [0, 1]]
    groups = np.unique([r["date"] for r in rows], return_inverse=True)[1]
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            m = sm.Logit(y, X).fit(disp=0, cov_type="cluster", cov_kwds={"groups": groups})
    except Exception as e:
        return {"ok": False, "err": type(e).__name__}
    out = {"ok": True, "sep": sep, "b_filter": m.params[1], "se_filter": m.bse[1], "p_filter": m.pvalues[1]}
    if not sep:
        out.update(b_inter=m.params[3], se_inter=m.bse[3], p_inter=m.pvalues[3])
    return out


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

def evaluate(rows: list[dict], feats: dict[int, dict]) -> list[dict]:
    res = []
    for name, desc, fn in FILTERS:
        tagged = []
        for r in rows:
            f = feats.get(r["game_id"])
            v = fn(f) if f else None
            if v is not None:
                tagged.append((r, bool(v)))
        strata = {}
        for src in ("history", "2026", "pooled"):
            sub = [(r, v) for r, v in tagged if src == "pooled" or r["source"] == src]
            on = rec([r for r, v in sub if v])
            off = rec([r for r, v in sub if not v])
            strata[src] = {"on": on, "off": off, "p": two_prop(on[0], sum(on), off[0], sum(off))}
        fit = logit_interaction([r for r, _ in tagged], [v for _, v in tagged]) if tagged else {"ok": False}
        n_on = sum(strata["pooled"]["on"])
        res.append({"name": name, "desc": desc, "n_tagged": len(tagged), "n_missing": len(rows) - len(tagged),
                    "strata": strata, "fit": fit, "mde_on": mde(n_on) if n_on else float("nan")})
    hp = holm([r["strata"]["pooled"]["p"] for r in res])
    for r, p in zip(res, hp):
        r["p_holm"] = p
    return res


def render(rows: list[dict], res: list[dict], H: int, F: int) -> str:
    w, l = rec(rows)
    lo, hi = wilson(w, w + l)
    L = [f"# Situational filters on Greenline unders, {dt.date.today().isoformat()}", "",
         "Reproduce: `python research/totals/scripts/under_filters.py --out research/totals/docs`.", "",
         "## Question", "",
         "Does any pre-registered, pregame situational filter separate winning Greenline unders from losing ones?",
         "The 2023-25 personal unders are treated as Greenline unders and pooled with the graded 2026 flags,",
         "kept as strata so a population difference cannot pass as a filter effect.", "",
         "## Data", "",
         f"- History 2023-25: {H} bet unders matched to `core.fact_game` (`data/ingest/bet_history/history.csv`).",
         f"- 2026 flags: {F} graded under flags matched through `pff_franchise.cfbd_team_id`.",
         f"- Pooled: {w}-{l} ({w / (w + l) * 100:.1f}%, 95% Wilson {lo * 100:.0f}–{hi * 100:.0f}%). "
         f"MDE for the whole pool: {mde(w + l) * 100:.1f}%. Break-even {BREAK_EVEN * 100:.2f}%.",
         "- Features from the local warehouse: `core.fact_game_line` (open/close), `stg.weather` (wind, indoors),",
         "  `stg.advanced_game_stats` (plays, season-to-date before kickoff), `core.fact_game` (spread, kickoff, rest).",
         "  A row missing a feature is dropped from that filter only; the count is in the table.", "",
         "## Filters, fixed before running", "", "| filter | rule |", "|---|---|"]
    L += [f"| {n} | {d} |" for n, d, _ in FILTERS]
    L += ["", "## Records: filter on vs off", "",
          "| filter | stratum | on | off | Fisher p |", "|---|---|---|---|---:|"]
    for r in res:
        for src in ("history", "2026", "pooled"):
            s = r["strata"][src]
            L.append(f"| {r['name']} | {src} | {fmt(*s['on'])} | {fmt(*s['off'])} | {s['p']:.3f} |")
    L += ["", "## Pooled test with the strata inside it", "",
          "Logistic: win ~ filter + source + filter×source, SE clustered by calendar day. `b_filter` is the",
          "log-odds shift the filter gives in the history stratum; `b_inter` is how much that shift differs in 2026.",
          "A filter whose interaction is large and opposite-signed is a population difference, not a filter.",
          "`sep` means a filter×source cell had no losses (or no rows), so the interaction is not identified",
          "and the fit is filter + source only.",
          "Holm corrects the pooled Fisher p across the six filters. `MDE on` is the smallest win rate the",
          "filter's kept rows could distinguish from break-even at their own n.", "",
          "| filter | n tagged | missing | b_filter ± se | p | b_inter ± se | p_inter | Fisher p (pooled) | Holm p | MDE on |",
          "|---|---:|---:|---|---:|---|---:|---:|---:|---:|"]
    for r in res:
        f = r["fit"]
        if f.get("ok") and not f["sep"]:
            fit = (f"{f['b_filter']:+.2f} ± {f['se_filter']:.2f} | {f['p_filter']:.3f} | "
                   f"{f['b_inter']:+.2f} ± {f['se_inter']:.2f} | {f['p_inter']:.3f}")
        elif f.get("ok"):
            fit = f"{f['b_filter']:+.2f} ± {f['se_filter']:.2f} | {f['p_filter']:.3f} | sep | --"
        else:
            fit = f"-- ({f.get('err', 'no fit')}) | -- | -- | --"
        L.append(f"| {r['name']} | {r['n_tagged']} | {r['n_missing']} | {fit} | "
                 f"{r['strata']['pooled']['p']:.3f} | {r['p_holm']:.3f} | {r['mde_on'] * 100:.0f}% |")
    keep = [r for r in res if r["p_holm"] < 0.05]
    L += ["", "## Reading", ""]
    if keep:
        L += [f"- Filters that survive Holm at 5%: {', '.join(r['name'] for r in keep)}. Check the interaction"
              " column before treating any as a rule: same sign in both strata is required."]
    else:
        L += ["- No filter survives the Holm correction at 5%. None of the six is a rule yet."]
    best = min(res, key=lambda r: r["strata"]["pooled"]["p"] if not math.isnan(r["strata"]["pooled"]["p"]) else 9)
    bs = best["strata"]["pooled"]
    L += [f"- Strongest raw split is `{best['name']}` (pooled Fisher p {bs['p']:.3f}, Holm {best['p_holm']:.3f}): "
          f"on {fmt(*bs['on'])} vs off {fmt(*bs['off'])}.",
          "- The strata differ in population (history is a high-total selection, 2026 flags sit six points",
          "  lower), so a filter that only shows in one stratum is a selection artifact until the other confirms it.",
          "", "## What this does not support", "",
          "- Applying any filter to a live slate. Six looks at ~240 rows; the Holm column is the honest p.",
          "- Reading a missing-feature filter (wind, pace) as null: 2026 weather coverage is a fifth of games,",
          "  so those rows are mostly history.",
          "- Treating history as out-of-sample. It was not selected by these filters, but it was selected by",
          "  a high-total rule that correlates with several of them (pace, big favorites).",
          "", "## What settles it", "",
          "- Rerun after each graded week. The 2026 stratum is the confirmation set; at ~150 2026 unders a",
          "  filter needs ~64% on its kept half to clear floor on 2026 alone.",
          "- A filter that holds: same sign in both strata, interaction p > 0.10, Holm p < 0.05."]
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- entry

def self_check() -> None:
    rows = [{"source": "history", "game_id": i, "date": f"2024-09-{7 + i % 3:02d}", "line": 55.5,
             "result": "win" if i % 3 else "loss"} for i in range(30)]
    rows += [{"source": "2026", "game_id": 100 + i, "date": f"2026-09-{12 + i % 2:02d}", "line": 50.5,
              "result": "win" if i % 2 else "loss"} for i in range(20)]
    feats = {r["game_id"]: {"spread": 20 if r["game_id"] % 5 < 2 else 3, "total_open": 55.0,
                            "total_close": 54.0 if r["game_id"] % 4 else 56.0, "wind": None, "indoors": False,
                            "hour": 20 if r["game_id"] % 3 else 12, "home_pace": 60.0, "away_pace": 70.0,
                            "fbs_pace": 65.0, "home_rest": 7, "away_rest": 7} for r in rows}
    res = evaluate(rows, feats)
    by = {r["name"]: r for r in res}
    assert by["windy"]["n_tagged"] == 0 and by["windy"]["n_missing"] == 50
    assert by["big_fav"]["n_tagged"] == 50
    assert sum(by["big_fav"]["strata"]["pooled"]["on"]) == 20
    assert by["slow"]["strata"]["pooled"]["on"] == (0, 0)  # away pace above mean -> never both slow
    assert all(0 <= r["p_holm"] <= 1 for r in res if not math.isnan(r["p_holm"]))
    assert by["big_fav"]["fit"]["ok"] and not by["big_fav"]["fit"]["sep"]
    one = evaluate([r for r in rows if r["source"] == "history"], feats)  # single stratum still fits
    assert {r["name"]: r for r in one}["big_fav"]["fit"]["ok"]
    assert holm([0.01, 0.04, 0.03]) == [0.03, 0.06, 0.06]
    assert 0.6 < mde(120) < 0.66
    out = render(rows, res, 30, 20)
    assert "| big_fav | pooled |" in out
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
    H, F = history_unders(), flag_unders()
    rows = H + F
    feats = features([r["game_id"] for r in rows])
    res = evaluate(rows, feats)
    text = render(rows, res, len(H), len(F))
    if a.dump:
        with a.dump.open("w", newline="", encoding="utf-8") as fh:
            wri = csv.writer(fh)
            wri.writerow(["source", "game_id", "date", "line", "result"] + [n for n, _, _ in FILTERS])
            for r in rows:
                f = feats.get(r["game_id"], {})
                wri.writerow([r["source"], r["game_id"], r["date"], r["line"], r["result"]]
                             + [fn(f) if f else None for _, _, fn in FILTERS])
    if a.out:
        p = a.out / f"greenline-under-filters-{dt.date.today().isoformat()}.md"
        p.write_text(text, encoding="utf-8")
        print(f"wrote {p}")
    else:
        print(text)


if __name__ == "__main__":
    main()
