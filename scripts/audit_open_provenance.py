"""Can CFBD's Bovada open be trusted as a pre-kickoff line? Provenance audit of `spreadOpen`
and `overUnderOpen` in raw/lines_<season>.json.

    python scripts/audit_open_provenance.py
    python scripts/audit_open_provenance.py --json OUT

Backs rankings/docs/odds-provenance-audit-2026-10-17.md (roadmap §5). Every baseline and
Glicko record scores against the Bovada open, and CFBD carries no time for it. This asks
what can be checked without one:

* fields      which keys a line row carries, per provider and season, and whether any is a time
* coverage    FBS-vs-FBS games with a Bovada open by season, and by conference and week
* open/curr   how often the open equals the current (closing) number
* duplicates  games with more than one Bovada row, and whether those rows disagree
* snapshots   older CFBD pulls on disk: was the open already there before kickoff, and is it
              the same number in today's file
* oddsapi     the-odds-api Bovada snapshots (2026): does CFBD's open match a Bovada price
              seen before kickoff
* an          Action Network's Open book (30) ticks (2026): when the market opened, and how
              close CFBD's Bovada open is to it

Existing work it does not repeat: docs/odds-sources-an-vs-apis-2026-09-11.md (what each
source holds), docs/cfbd-lines-coverage-2026-09-17.md (provider eras, 2013 floor),
scripts/audit_line_sign_convention.py (spread sign). Read-only: reads files and the warehouse
read-only, prints tables, writes only --json when asked. Ignores any snapshot, pull or kickoff
at or after 2026-10-17 00:00 UTC.
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd

REPO = next(p for p in Path(__file__).resolve().parents if (p / "cfb_paths.py").is_file())
sys.path.insert(0, str(REPO))

CUTOFF = pd.Timestamp("2026-10-17T00:00:00Z")
PROVIDER = "Bovada"
SEASONS = range(2013, 2027)
MODERN = range(2021, 2027)                      # seasons with any open line
AN_OPEN_BOOK = 30
# AN location -> CFBD school, beyond the duckdb_load aliases (cfb_system_maker/duckdb_load.py).
AN_ALIAS = {"Miami (FL)": "Miami", "San Jose State": "San José State",
            "Appalachian State": "App State", "Louisiana-Monroe": "UL Monroe",
            "UMass": "Massachusetts", "Miami (OH)": "Miami (OH)",
            "Southern Mississippi": "Southern Miss", "Hawaii": "Hawai'i"}
TIMEISH = re.compile(r"time|date|updated|stamp|_at$|At$", re.I)


def _load(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def _kick(g: dict) -> pd.Timestamp:
    return pd.to_datetime(g.get("startDate"), errors="coerce", utc=True, format="ISO8601")


def _fbs(g: dict) -> bool:
    return g.get("homeClassification") == "fbs" and g.get("awayClassification") == "fbs"


def bovada_rows(g: dict) -> list[dict]:
    return [ln for ln in g.get("lines") or [] if ln.get("provider") == PROVIDER]


def first_open(g: dict) -> tuple[float | None, float | None]:
    """(spreadOpen, overUnderOpen) of the first Bovada row, as market_implied_scores reads it."""
    rows = bovada_rows(g)
    return (rows[0].get("spreadOpen"), rows[0].get("overUnderOpen")) if rows else (None, None)


# ---------------------------------------------------------------- fields and coverage

def fields(raw: Path) -> dict:
    """Per season: line-row keys, non-null open counts per provider, any time-like key."""
    out = {}
    for s in SEASONS:
        f = raw / f"lines_{s}.json"
        if not f.exists():
            continue
        keys, game_keys = collections.Counter(), set()
        opens = collections.defaultdict(lambda: [0, 0, 0])   # rows, spreadOpen, overUnderOpen
        for g in _load(f):
            game_keys |= set(g)
            for ln in g.get("lines") or []:
                keys.update(ln.keys())
                o = opens[ln.get("provider")]
                o[0] += 1
                o[1] += ln.get("spreadOpen") is not None
                o[2] += ln.get("overUnderOpen") is not None
        out[s] = {"line_keys": sorted(keys), "game_keys_timeish": sorted(k for k in game_keys if TIMEISH.search(k)),
                  "line_keys_timeish": sorted(k for k in keys if TIMEISH.search(k)),
                  "providers": {p: {"rows": v[0], "spreadOpen": v[1], "overUnderOpen": v[2]}
                                for p, v in sorted(opens.items(), key=lambda kv: str(kv[0]))}}
    return out


def fbs_frame(raw: Path, seasons) -> pd.DataFrame:
    """One row per FBS-vs-FBS game kicked off before CUTOFF, with its Bovada fields."""
    rows = []
    for s in seasons:
        for g in _load(raw / f"lines_{s}.json"):
            k = _kick(g)
            if not _fbs(g) or pd.isna(k) or k >= CUTOFF:
                continue
            b = bovada_rows(g)
            so, to = first_open(g)
            rows.append({"game_id": g["id"], "season": s, "season_type": g.get("seasonType"),
                         "week": g.get("week"), "kickoff": k,
                         "home_conf": g.get("homeConference"), "away_conf": g.get("awayConference"),
                         "n_lines": len(g.get("lines") or []), "n_bovada": len(b),
                         "spread_open": so, "total_open": to,
                         "spread": b[0].get("spread") if b else None,
                         "total": b[0].get("overUnder") if b else None,
                         "bovada_disagree": len({(r.get("spreadOpen"), r.get("overUnderOpen")) for r in b}) > 1})
    return pd.DataFrame(rows)


def coverage(d: pd.DataFrame) -> pd.DataFrame:
    has = d.spread_open.notna() & d.total_open.notna()
    return (d.assign(lined=d.n_lines > 0, bovada=d.n_bovada > 0, spread_open_ok=d.spread_open.notna(),
                     total_open_ok=d.total_open.notna(), both=has, dup=d.n_bovada > 1,
                     dup_disagree=d.bovada_disagree)
             .groupby("season")[["lined", "bovada", "spread_open_ok", "total_open_ok", "both", "dup", "dup_disagree"]]
             .sum().assign(games=d.groupby("season").size()).astype(int))


def missing_by(d: pd.DataFrame, key: str) -> pd.DataFrame:
    has = d.spread_open.notna() & d.total_open.notna()
    if key == "conference":
        long = pd.concat([d.assign(conference=d.home_conf, has=has), d.assign(conference=d.away_conf, has=has)])
        long = long.drop_duplicates(["game_id", "conference"])
    else:
        long = d.assign(has=has, week=d.week.where(d.season_type == "regular", "post"))
    t = long.groupby(key).agg(games=("game_id", "size"), with_open=("has", "sum"))
    return t.assign(missing_pct=(100 * (1 - t.with_open / t.games)).round(1)).sort_values("missing_pct", ascending=False)


def open_vs_current(d: pd.DataFrame) -> pd.DataFrame:
    e = d.dropna(subset=["spread_open", "total_open", "spread", "total"])
    ds, dt = (e.spread - e.spread_open).abs(), (e.total - e.total_open).abs()
    return pd.DataFrame({"games": e.groupby("season").size(),
                         "spread_eq_pct": (100 * (ds == 0).groupby(e.season).mean()).round(1),
                         "total_eq_pct": (100 * (dt == 0).groupby(e.season).mean()).round(1),
                         "spread_mean_abs_move": ds.groupby(e.season).mean().round(2),
                         "total_mean_abs_move": dt.groupby(e.season).mean().round(2),
                         "spread_move_ge3_pct": (100 * (ds >= 3).groupby(e.season).mean()).round(1)})


# ---------------------------------------------------------------- older CFBD pulls

def snapshot_files(data: Path) -> list[tuple[Path, int, pd.Timestamp]]:
    """(file, season, observed-at) for every lines snapshot outside raw/. The observed-at is the
    file's mtime, or the date in its name when that is earlier (a copy can be touched later)."""
    out = []
    for f in sorted(data.rglob("lines_20*.json")):
        if f.parent == data / "raw":
            continue
        m = re.search(r"lines_(\d{4})", f.name)
        t = pd.Timestamp(f.stat().st_mtime, unit="s", tz="UTC")
        dm = re.search(r"_(\d{8})\.json$", f.name)
        if dm:
            t = min(t, pd.Timestamp(dm.group(1), tz="UTC") + pd.Timedelta(days=1))  # end of that day
        if t < CUTOFF:
            out.append((f, int(m.group(1)), t))
    return out


def snapshots(data: Path) -> dict:
    """Per older pull: games whose Bovada open was present then, how many of those had not yet
    kicked off at the pull, and whether today's raw file holds the same number. Also the
    distinct games seen with an open before kickoff in any pull."""
    raw = data / "raw"
    current = {s: {g["id"]: first_open(g) for g in _load(raw / f"lines_{s}.json")} for s in SEASONS
               if (raw / f"lines_{s}.json").exists()}
    out, pre_kick = [], {}
    for f, s, t in snapshot_files(data):
        games = _load(f)
        rows = []
        for g in games:
            so, to = first_open(g)
            if so is None or to is None:
                continue
            k = _kick(g)
            now = current.get(s, {}).get(g["id"], (None, None))
            rows.append({"pre_kick": bool(pd.notna(k) and k > t), "in_current": now[0] is not None,
                         "same": now == (so, to), "same_spread": now[0] == so})
            if rows[-1]["pre_kick"] and rows[-1]["in_current"]:
                pre_kick[g["id"]] = pre_kick.get(g["id"], True) and rows[-1]["same"]
        r = pd.DataFrame(rows)
        if r.empty:
            out.append({"file": str(f.relative_to(data)), "season": s, "observed": t.isoformat(),
                        "games": len(games), "with_open": 0})
            continue
        pre = r[r.pre_kick & r.in_current]
        out.append({"file": str(f.relative_to(data)), "season": s, "observed": t.isoformat(),
                    "games": len(games), "with_open": len(r), "pre_kick_with_open": int(r.pre_kick.sum()),
                    "pre_kick_same_as_now": int(pre.same.sum()), "pre_kick_compared": len(pre),
                    "all_same_as_now_pct": round(100 * r[r.in_current].same.mean(), 1) if r.in_current.any() else None})
    return {"files": out, "pre_kick_games": len(pre_kick), "pre_kick_games_same_now": sum(pre_kick.values())}


# ---------------------------------------------------------------- the-odds-api and AN

def _match(a: pd.Series, b: pd.Series) -> dict:
    x = (a - b).abs()
    return {"n": int(len(x)), "exact_pct": round(100 * float((x == 0).mean()), 1),
            "within_0_5_pct": round(100 * float((x <= 0.5).mean()), 1),
            "within_1_pct": round(100 * float((x <= 1.0).mean()), 1),
            "median_abs": round(float(x.median()), 2) if len(x) else None}


def oddsapi(con: duckdb.DuckDBPyConnection, cfbd: pd.DataFrame) -> dict:
    """Bovada spread (home) and total (over) from every the-odds-api pull before kickoff."""
    o = con.sql(f"""
        select game_id, market, line, pulled_at, commence_time from core.fact_game_odds
        where book = 'bovada' and ((market = 'spreads' and side = 'home') or (market = 'totals' and side = 'over'))
          and pulled_at < commence_time and pulled_at < TIMESTAMPTZ '{CUTOFF.isoformat()}'""").df()
    o["game_id"] = o.game_id.astype("int64")
    c = cfbd.dropna(subset=["spread_open", "total_open"]).set_index("game_id")
    out = {"pulls": int(o.pulled_at.nunique()), "first_pull": str(o.pulled_at.min()),
           "last_pull": str(o.pulled_at.max()), "games": int(o.game_id.nunique())}
    for mkt, col, cur in (("spreads", "spread_open", "spread"), ("totals", "total_open", "total")):
        m = o[o.market == mkt].sort_values("pulled_at")
        m = m[m.game_id.isin(c.index)]
        first = m.groupby("game_id").first()
        last = m.groupby("game_id").last()
        seen = m.assign(v=c.loc[m.game_id, col].to_numpy()).assign(hit=lambda z: z.line == z.v)
        lead = (first.commence_time - first.pulled_at).dt.total_seconds() / 3600
        bucket = pd.cut(lead, [0, 48, 120, 1e9], labels=["<48h", "48-120h", ">120h"])
        out[mkt] = {"first_pull_vs_cfbd_open": _match(first.line, c.loc[first.index, col]),
                    "first_pull_vs_cfbd_open_by_lead": {
                        str(b): _match(first.line[bucket == b], c.loc[first.index[bucket == b], col])
                        for b in bucket.cat.categories},
                    "cfbd_open_seen_in_any_pre_kick_pull_pct":
                        round(100 * float(seen.groupby("game_id").hit.any().mean()), 1),
                    "last_pull_vs_cfbd_current": _match(last.line, c.loc[last.index, cur]),
                    "first_pull_hours_before_kick_median": round(float(lead.median()), 1)}
    return out


def _norm(name: str | None) -> str:
    return (AN_ALIAS.get(name, name) or "").lower().replace("é", "e").replace("'", "")


def an_events(con: duckdb.DuckDBPyConnection, cfbd_games: list[dict]) -> pd.DataFrame:
    """AN 2026 events paired to CFBD game ids on (home, away) school and kickoff within a day."""
    ev = con.sql("""
        select s.event_id, s.start_time, h.location home, a.location away
        from stg.an_scoreboard s
        join stg.an_team h on h.event_id = s.event_id and h.team_id = s.home_team_id
        join stg.an_team a on a.event_id = s.event_id and a.team_id = s.away_team_id
        where s.season = 2026""").df()
    idx = collections.defaultdict(list)
    for g in cfbd_games:
        idx[(_norm(g["homeTeam"]), _norm(g["awayTeam"]))].append((g["id"], _kick(g)))
    pairs = []
    for e in ev.itertuples():
        hits = [gid for gid, k in idx.get((_norm(e.home), _norm(e.away)), [])
                if pd.notna(k) and abs((k - pd.Timestamp(e.start_time).tz_convert("UTC")).total_seconds()) <= 86400]
        if len(hits) == 1:
            pairs.append({"event_id": e.event_id, "game_id": hits[0]})
    return pd.DataFrame(pairs, columns=["event_id", "game_id"])


def action_network(con: duckdb.DuckDBPyConnection, cfbd: pd.DataFrame, cfbd_games: list[dict]) -> dict:
    """AN Open book: first full-game home spread and over total tick, both before kickoff."""
    pairs = an_events(con, cfbd_games)
    t = con.sql(f"""
        select t.event_id, t.market_type, t.line, t.updated_at, s.start_time
        from stg.an_history_tick t join stg.an_scoreboard s using (event_id)
        where t.period = 'event' and t.book_id = {AN_OPEN_BOOK} and coalesce(t.is_live, false) = false
          and ((t.market_type = 'spread' and t.side = 'home') or (t.market_type = 'total' and t.side = 'over'))
          and t.updated_at < s.start_time and t.updated_at < TIMESTAMPTZ '{CUTOFF.isoformat()}'""").df()
    t = t.merge(pairs, on="event_id")
    c = cfbd.dropna(subset=["spread_open", "total_open"]).set_index("game_id")
    t = t[t.game_id.isin(c.index)].sort_values("updated_at")
    out = {"an_events_2026": int(con.sql("select count(*) from stg.an_scoreboard where season = 2026").fetchone()[0]),
           "paired_to_cfbd": len(pairs), "with_open_tick_and_cfbd_open": int(t.game_id.nunique()),
           "last_tick": str(t.updated_at.max()) if len(t) else None}
    for mkt, col, cur in (("spread", "spread_open", "spread"), ("total", "total_open", "total")):
        m = t[t.market_type == mkt]
        first = m.groupby("game_id").first()
        seen = m.assign(v=c.loc[m.game_id, col].to_numpy(), w=c.loc[m.game_id, cur].to_numpy())
        seen = seen.assign(hit=seen.line == seen.v, hit_cur=seen.line == seen.w)
        lead = (first.start_time - first.updated_at).dt.total_seconds() / 86400
        out[mkt] = {"an_first_open_tick_vs_cfbd_open": _match(first.line, c.loc[first.index, col]),
                    "cfbd_open_seen_in_any_an_open_tick_pct":
                        round(100 * float(seen.groupby("game_id").hit.any().mean()), 1) if len(seen) else None,
                    # reference: the same test for CFBD's current (closing) number
                    "cfbd_current_seen_in_any_an_open_tick_pct":
                        round(100 * float(seen.groupby("game_id").hit_cur.any().mean()), 1) if len(seen) else None,
                    "an_first_tick_days_before_kick_median": round(float(lead.median()), 1) if len(lead) else None}
    return out


# ---------------------------------------------------------------- main

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", type=Path, help="also write every table as JSON here")
    args = ap.parse_args(argv)
    import cfb_paths

    pd.set_option("display.width", 250, "display.max_rows", 200, "display.max_columns", 20)
    data, raw = cfb_paths.DATA_ROOT, cfb_paths.DATA_ROOT / "raw"
    report: dict = {"run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "cutoff": CUTOFF.isoformat(), "provider": PROVIDER}

    report["fields"] = fields(raw)
    print("== Line-row keys, and time-like keys (game level / line level)")
    for s, v in report["fields"].items():
        opens = {p: (x["spreadOpen"], x["overUnderOpen"]) for p, x in v["providers"].items()
                 if x["spreadOpen"] or x["overUnderOpen"]}
        print(f"{s}: timeish game={v['game_keys_timeish']} line={v['line_keys_timeish']} "
              f"providers={list(v['providers'])} with opens={opens or 'none'}")

    d = fbs_frame(raw, [s for s in SEASONS if (raw / f"lines_{s}.json").exists()])
    cov = coverage(d)
    print("\n== FBS-vs-FBS games before cutoff: Bovada rows and opens\n", cov)
    m = d[d.season.isin(MODERN)]
    ovc = open_vs_current(m)
    print("\n== Bovada open vs current (first Bovada row)\n", ovc)
    by_conf = missing_by(m[m.season < 2026], "conference")
    by_week = missing_by(m[m.season < 2026], "week")
    print("\n== Missing Bovada open by conference, 2021-2025\n", by_conf)
    print("\n== Missing Bovada open by week, 2021-2025\n", by_week)
    report.update(coverage=cov.to_dict("index"), open_vs_current=ovc.to_dict("index"),
                  missing_by_conference=by_conf.to_dict("index"),
                  missing_by_week={str(k): v for k, v in by_week.to_dict("index").items()})

    report["snapshots"] = snapshots(data)
    print("\n== Older CFBD pulls: Bovada open present before kickoff, same number today")
    print(pd.DataFrame(report["snapshots"]["files"]).to_string(index=False))
    print(f"distinct games with an open in a pull before kickoff: {report['snapshots']['pre_kick_games']}, "
          f"same open in today's file: {report['snapshots']['pre_kick_games_same_now']}")

    games26 = [g for g in _load(raw / "lines_2026.json") if pd.notna(_kick(g)) and _kick(g) < CUTOFF]
    d26 = d[d.season == 2026]
    con = duckdb.connect(str(data / "cfb.duckdb"), read_only=True)
    report["oddsapi"] = oddsapi(con, d26)
    print("\n== the-odds-api Bovada pulls before kickoff vs CFBD (2026)\n", json.dumps(report["oddsapi"], indent=1))
    report["action_network"] = action_network(con, d26, games26)
    print("\n== AN Open book ticks before kickoff vs CFBD Bovada open (2026)\n",
          json.dumps(report["action_network"], indent=1))
    if args.json:
        args.json.write_text(json.dumps(report, indent=2, default=str) + "\n")
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
