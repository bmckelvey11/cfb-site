"""Warehouse reads for the matchup page, one function per section.

Every function takes an open connection from `warehouse()`, which opens `cfb.duckdb`
read-only for one request and closes it. A process that holds the file open makes the
nightly rebuild's final swap fail on Windows
(`cfb_system_maker/docs/app-vs-warehouse-read-path-2026-09-16.md`), so nothing here caches
a connection.

Teams are `core.dim_team.team_id` everywhere; `stg` tables key on the school string and are
bridged through `dim_team.school`. FBS membership is per season from `stg.fbs_teams`, because
`dim_team.is_fbs` is current-state.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import duckdb

from cfb_paths import current_season
from cfb_system_maker.matchup import odds as odds_mod
from dataclasses import replace

from cfb_system_maker.matchup.stats import (
    ADJUSTED, PROFILE, RATINGS, SOURCES, UNIT_GROUPS, UNITS, Source, Stat, Unit, edge,
)

SHARP_BOOKS = ("pinnacle", "circa")
MAIN_BOOKS = ("draftkings", "fanduel")


class WarehouseBusy(Exception):
    """The rebuild holds `cfb.duckdb`; the page says so instead of failing."""


@contextmanager
def warehouse(path: Path):
    try:
        con = duckdb.connect(str(path), read_only=True)
    except duckdb.Error as exc:
        raise WarehouseBusy(str(exc)) from exc
    try:
        # Kickoffs are TIMESTAMPTZ; pin the zone rather than inherit the server's.
        con.execute("SET TimeZone = 'America/New_York'")
        yield con
    finally:
        con.close()


def _plain(v):
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    return v


def rows(con, sql: str, params=()) -> list[dict]:
    cur = con.execute(sql, list(params))
    cols = [d[0] for d in cur.description]
    return [{c: _plain(v) for c, v in zip(cols, r)} for r in cur.fetchall()]


# --- calendar -------------------------------------------------------------------------------

def current_week(con, now: datetime) -> dict:
    """The regular week containing `now`, or the next one; the season's last week after that.

    Pinned to one season because an unfiltered scan also matches a mis-dated 2025 week 16.
    """
    season = current_season(now)
    found = rows(con, """
        select season, week, season_type from core.dim_week
        where season = ? and season_type = 'regular' and end_date > ?
        order by start_date limit 1""", [season, now])
    if not found:
        found = rows(con, """
            select season, week, season_type from core.dim_week
            where season = ? order by start_date desc limit 1""", [season])
    return found[0] if found else {"season": season, "week": 1, "season_type": "regular"}


def weeks(con, season: int) -> list[dict]:
    return rows(con, """
        select week, season_type, start_date from core.dim_week
        where season = ? order by start_date""", [season])


def first_kickoff(con, season: int, week: int, season_type: str = "regular"):
    r = con.execute("""
        select min(start_date) from core.fact_game
        where season = ? and week = ? and season_type = ?""", [season, week, season_type]).fetchone()
    return r[0]


# --- teams ----------------------------------------------------------------------------------

def fbs(con, season: int) -> dict[int, dict]:
    """FBS teams that season: team_id -> {school, conference}. The rank universe."""
    return {r["team_id"]: r for r in rows(con, """
        select teamId as team_id, school, conference from stg.fbs_teams where season = ?""",
        [season])}


def teams(con, season: int) -> list[dict]:
    members = fbs(con, season)
    return [dict(r, fbs=r["team_id"] in members,
                 conference=members.get(r["team_id"], {}).get("conference"))
            for r in rows(con, "select team_id, school, classification from core.dim_team order by school")]


def team(con, team_id: int, season: int) -> dict | None:
    found = [t for t in teams(con, season) if t["team_id"] == team_id]
    return found[0] if found else None


def school_index(con) -> dict[str, str]:
    return odds_mod.school_index([r[0] for r in con.execute("select school from core.dim_team").fetchall()])


# --- ranks ----------------------------------------------------------------------------------

def _side(stat: Stat, values: dict[int, float], universe: dict[int, dict], team_id: int) -> dict:
    """One team's value with its rank among the universe teams that have a value."""
    pool = {t: v for t, v in values.items() if t in universe and v is not None}
    v = values.get(team_id)
    out = {"value": v, "rank": None, "n": len(pool), "conf_rank": None, "conf_n": None}
    if v is None:
        return out
    better = (lambda x: x < v) if stat.higher_is_better is False else (lambda x: x > v)
    out["rank"] = 1 + sum(better(x) for x in pool.values())
    conf = universe.get(team_id, {}).get("conference")
    if conf:
        peers = [x for t, x in pool.items() if universe[t]["conference"] == conf]
        out["conf_rank"] = 1 + sum(better(x) for x in peers)
        out["conf_n"] = len(peers)
    return out


def stat_row(stat: Stat, values: dict[int, float], universe: dict[int, dict], a: int, b: int,
             **extra) -> dict:
    sa, sb = _side(stat, values, universe, a), _side(stat, values, universe, b)
    return {"key": stat.key, "label": stat.label, "fmt": stat.fmt, "dp": stat.dp, "verdict": stat.verdict,
            "higher_is_better": stat.higher_is_better, "source": f"{stat.table}.{stat.column}",
            "a": sa, "b": sb, "edge": edge(sa["value"], sb["value"], stat.higher_is_better),
            "prior": None, "estimate": None, **extra}


def season_values(con, stat: Stat, season: int) -> dict[int, float]:
    """A season-grain stg table's column for every team that season, keyed by team_id."""
    return dict(con.execute(f"""
        select d.team_id, t."{stat.column}"::double from {stat.table} t
        join core.dim_team d on d.school = t.team
        where t.season = ?""", [season]).fetchall())


def season_rows(con, stats: tuple[Stat, ...], season: int, a: int, b: int, *,
                prior: bool = True) -> list[dict]:
    universe = fbs(con, season)
    before = fbs(con, season - 1) if prior else {}
    out = []
    for stat in stats:
        row = stat_row(stat, season_values(con, stat, season), universe, a, b, season=season)
        if prior:
            pv = season_values(con, stat, season - 1)
            row["prior"] = {"season": season - 1, "a": _side(stat, pv, before, a),
                            "b": _side(stat, pv, before, b)}
        out.append(row)
    return out


# --- slate ----------------------------------------------------------------------------------

def slate(con, season: int, week: int, season_type: str, lines: dict) -> list[dict]:
    games = rows(con, """
        select g.game_id, g.start_date, coalesce(sg.startTimeTBD, false) as tbd,
               coalesce(sg.neutralSite, false) as neutral, g.completed,
               g.home_team_id, g.away_team_id, g.home_team, g.away_team,
               g.home_conference, g.away_conference, g.home_points, g.away_points, g.has_line,
               g.median_spread_close, g.median_total_close,
               h.teamId is not null as home_fbs, a.teamId is not null as away_fbs
        from core.v_game_book_median g
        left join (select gameId, startTimeTBD, neutralSite from stg.games
                   where season = ? and week = ?) sg on sg.gameId = g.game_id
        left join stg.fbs_teams h on h.teamId = g.home_team_id and h.season = g.season
        left join stg.fbs_teams a on a.teamId = g.away_team_id and a.season = g.season
        where g.season = ? and g.week = ? and g.season_type = ?
        order by g.start_date, g.game_id""", [season, week, season, week, season_type])
    for g in games:
        snap = snap_game(lines, g["home_team"], g["away_team"], g["start_date"])
        g["books"] = {bk: _book_for(snap, bk, g["home_team"], g["away_team"]) for bk in MAIN_BOOKS}
        g["lined"] = bool(g["has_line"] or snap)
    return games


def _book_for(snap: dict | None, book: str, home: str, away: str) -> dict | None:
    b = (snap or {}).get("books", {}).get(book)
    if not b:
        return None
    return {"spread": {"home": (b["spread"].get(home) or [None])[0],
                       "away": (b["spread"].get(away) or [None])[0]},
            "total": (b["total"].get("over") or [None])[0],
            "ml": {"home": b["ml"].get(home), "away": b["ml"].get(away)},
            "prices": b, "last_update": b.get("last_update")}


# --- game card ------------------------------------------------------------------------------

def find_game(con, season: int, a: int, b: int, cutoff) -> int | None:
    """The pair's game that season kicking off at or after the as-of cutoff.

    A meeting before the cutoff is already inside the stat window, so it is not "the game";
    the head-to-head section lists it. Full-season mode (no cutoff) takes the last meeting.
    """
    found = con.execute(f"""
        select game_id from core.fact_game
        where season = ? and least(home_team_id, away_team_id) = least(?, ?)
          and greatest(home_team_id, away_team_id) = greatest(?, ?)
          {"" if cutoff is None else "and start_date >= ?"}
        order by start_date {"desc" if cutoff is None else ""} limit 1""",
        [season, a, b, a, b, *([] if cutoff is None else [cutoff])]).fetchone()
    return found[0] if found else None


def snap_game(lines: dict, home: str, away: str, start: str | None) -> dict | None:
    """The snapshot's event for this game: same unordered pair, kickoff within 3 days.

    The pair alone is not enough; the same teams can meet in another season (or twice).
    """
    ev = lines["games"].get(frozenset((home, away)))
    if not ev or not start or not ev.get("commence_time"):
        return None
    kick = datetime.fromisoformat(ev["commence_time"].replace("Z", "+00:00"))
    return ev if abs((kick - datetime.fromisoformat(start)).total_seconds()) < 3 * 86400 else None


def game_card(con, game_id: int, lines: dict, *, full: bool) -> dict | None:
    base = rows(con, """
        select v.*, coalesce(sg.neutralSite, false) as neutral, coalesce(sg.startTimeTBD, false) as tbd,
               sg.conferenceGame as conference_game, sg.notes,
               m.median_spread_open, m.median_spread_close, m.n_books_spread_open, m.n_books_spread_close,
               m.median_total_open, m.median_total_close, m.n_books_total_open, m.n_books_total_close
        from core.v_game v
        left join core.v_game_book_median m using (game_id)
        left join stg.games sg on sg.gameId = v.game_id
        where v.game_id = ?""", [game_id])
    if not base:
        return None
    g = base[0]
    home, away = g["home_team"], g["away_team"]
    if not full:  # the result is postgame; the as-of view never shows it
        g["home_points"] = g["away_points"] = None
    g["weather"] = (rows(con, "select * exclude (_source) from core.fact_game_weather where game_id = ?",
                         [game_id]) or [None])[0]
    g["win_prob"] = (rows(con, """
        select homeWinProbability as home_win_probability, spread from stg.pregame_win_prob
        where gameId = ?""", [game_id]) or [None])[0]
    closes = rows(con, """
        select provider_key as book, spread_open, spread_close, total_open, total_close,
               moneyline_home, moneyline_away
        from core.fact_game_line where game_id = ? order by provider_key""", [game_id])
    g["sharp"] = [r for r in closes if r["book"] in SHARP_BOOKS]
    g["other_books"] = [r for r in closes if r["book"] not in SHARP_BOOKS + MAIN_BOOKS]
    g["main_books"] = _main_books(con, game_id, snap_game(lines, home, away, g["start_date"]),
                                  lines["pulled_at"], home, away,
                                  {r["book"]: r for r in closes if r["book"] in MAIN_BOOKS})
    return g


def _main_books(con, game_id: int, snap: dict | None, pulled_at: str | None, home: str, away: str,
                closes: dict) -> dict:
    """DK/FD now (newest snapshot, else the warehouse's last tick) plus their movement.

    History ticks key the line by the vendor's own home side; `home_school` turns that into a
    school so a neutral-site flip cannot invert the sign.
    """
    ticks = rows(con, """
        select book, market, side, line, odds, pulled_at, home_school, away_school
        from core.fact_game_odds
        where game_id = ? and book in ('draftkings', 'fanduel') and market in ('spreads', 'totals', 'h2h')
        order by pulled_at""", [game_id])
    out = {}
    for bk in MAIN_BOOKS:
        series: dict[str, dict] = {}
        for t in (t for t in ticks if t["book"] == bk):
            p = series.setdefault(t["pulled_at"], {"t": t["pulled_at"], "spread_home": None, "total": None})
            if t["market"] == "spreads":
                school = t["home_school"] if t["side"] == "home" else t["away_school"]
                if school == home:
                    p["spread_home"] = t["line"]
            elif t["market"] == "totals" and t["side"] == "over":
                p["total"] = t["line"]
        history = []
        for p in series.values():  # keep only the ticks where the number moved
            if not history or (p["spread_home"], p["total"]) != (history[-1]["spread_home"], history[-1]["total"]):
                history.append(p)
        now = _book_for(snap, bk, home, away)
        if now:
            now.update(source="snapshot", as_of=pulled_at)
            history.append({"t": pulled_at, "spread_home": now["spread"]["home"], "total": now["total"]})
        elif history:
            last = history[-1]
            now = {"spread": {"home": last["spread_home"], "away": -last["spread_home"]
                              if last["spread_home"] is not None else None},
                   "total": last["total"], "ml": None, "source": "warehouse", "as_of": last["t"]}
        elif bk in closes:  # before tick history began (2026-09-09): the book's closing line
            c = closes[bk]
            now = {"spread": {"home": c["spread_close"], "away": None if c["spread_close"] is None
                              else -c["spread_close"]}, "total": c["total_close"],
                   "ml": {"home": c["moneyline_home"], "away": c["moneyline_away"]},
                   "source": "close", "as_of": None}
        out[bk] = {"now": now, "history": history}
    return out


# --- team profile ---------------------------------------------------------------------------

def _window(full: bool) -> str:
    return "true" if full else "(g.season_type = 'regular' and g.week < ?)"


def asof(con, season: int, week: int, season_type: str, *, full: bool) -> tuple[int, object]:
    """(window week, kickoff cutoff) for a selection.

    The window is regular-season games with week < W; a postseason selection takes the whole
    regular season. The cutoff is that week's first kickoff (None in full-season mode).
    """
    if full:
        return 99, None
    cutoff = first_kickoff(con, season, week, season_type)
    return (99 if season_type == "postseason" else week), cutoff


def profile(con, team_id: int, season: int, week: int, cutoff, *, full: bool) -> dict:
    school = con.execute("select school from core.dim_team where team_id = ?", [team_id]).fetchone()[0]
    wargs = [] if full else [week]
    rec = rows(con, f"""
        select count(*) filter (where won) as w, count(*) filter (where not won) as l,
               count(*) filter (where won and conf) as conf_w,
               count(*) filter (where not won and conf) as conf_l
        from (select (case when g.home_team_id = ? then g.home_points > g.away_points
                           else g.away_points > g.home_points end) as won,
                     coalesce(sg.conferenceGame, false) as conf
              from core.fact_game g left join stg.games sg on sg.gameId = g.game_id
              where g.season = ? and g.completed and ? in (g.home_team_id, g.away_team_id)
                and {_window(full)})""", [team_id, season, team_id, *wargs])[0]
    return {"record": rec, "polls": _polls(con, team_id, season, week, full=full),
            "massey": _massey(con, school, season, cutoff), "coach": _coach(con, team_id, season),
            "portal": _portal(con, school, season)}


def _polls(con, team_id: int, season: int, week: int, *, full: bool) -> list[dict]:
    """The poll labelled week N is released before week N's games, so as-of W reads poll W."""
    return rows(con, f"""
        select p.short_name as poll, r.week, r.season_type, r.rank from (
            select *, row_number() over (partition by poll_type_id
                order by season_type = 'postseason' desc, week desc) as k
            from core.fact_poll_rank
            where season = ? and poll_type_id in (1, 2)
              and ({'true' if full else "season_type = 'regular' and week <= ?"})) r
        join core.dim_poll_type p on p.poll_type_id = r.poll_type_id
        where k = 1 and r.team_id = ?""", [season, *([] if full else [week]), team_id])


def massey_date(con, season: int, cutoff) -> date | None:
    """Latest edition dated before the week's first kickoff (editions land 2-7 days ahead)."""
    if cutoff is None:
        r = con.execute("select max(date) from stg.massey_editions where season = ?", [season]).fetchone()
    else:
        r = con.execute("select max(date) from stg.massey_editions where season = ? and date < ?::date",
                        [season, cutoff]).fetchone()
    return r[0]


def _massey(con, school: str, season: int, cutoff) -> dict | None:
    d = massey_date(con, season, cutoff)
    found = rows(con, """
        select date, cmp_rank, n_systems, wins, losses from stg.massey_editions
        where season = ? and date = ? and cfbd_team = ?""", [season, d, school]) if d else []
    return found[0] if found else None


def _coach(con, team_id: int, season: int) -> dict | None:
    found = rows(con, """
        select c.first_name, c.last_name,
               (select count(distinct x.season) from core.fact_coach_season x
                where x.coach_id = c.coach_id and x.team_id = c.team_id and x.season <= c.season) as season_n
        from core.fact_coach_season c where c.team_id = ? and c.season = ?""", [team_id, season])
    return found[0] if found else None


def _portal(con, school: str, season: int) -> dict:
    return rows(con, """
        select count(*) filter (where destination = ?) as incoming,
               count(*) filter (where origin = ?) as outgoing,
               avg(stars) filter (where destination = ?) as incoming_stars,
               avg(stars) filter (where origin = ?) as outgoing_stars
        from stg.transfer_portal where season = ?""", [school, school, school, school, season])[0]


def profile_rows(con, season: int, a: int, b: int) -> list[dict]:
    return season_rows(con, PROFILE, season, a, b)


# --- ratings --------------------------------------------------------------------------------

def ratings(con, season: int, cutoff, a: int, b: int, *, full: bool, show_postgame: bool) -> dict:
    """As-of: every rating system is a season-final snapshot, so only last season's is shown.

    Massey is the exception: its editions are dated, so this season's ranks as of the week's
    first kickoff are pre-game safe.
    """
    shown = season if full else season - 1
    out = {"season": shown, "basis": "postgame" if full else "prior_season",
           "rows": season_rows(con, RATINGS, shown, a, b, prior=full)}
    if full:
        out["rows"] += season_rows(con, ADJUSTED, season, a, b, prior=False)
    elif show_postgame:
        out["postgame"] = season_rows(con, RATINGS + ADJUSTED, season, a, b, prior=False)
    d = massey_date(con, season, cutoff)
    out["massey_date"] = _plain(d)
    out["massey"] = rows(con, """
        select r.system, max(r.rank) filter (where r.cfbd_team = ta.school) as a,
               max(r.rank) filter (where r.cfbd_team = tb.school) as b
        from stg.massey_ranks r, core.dim_team ta, core.dim_team tb
        where ta.team_id = ? and tb.team_id = ? and r.season = ? and r.date = ?
          and r.cfbd_team in (ta.school, tb.school)
        group by r.system order by r.system""", [a, b, season, d]) if d else []
    return out


# --- windowed game-grain stats (unit matchups) ----------------------------------------------

# Drives rolled up to one row per team-game, in the same offense_/defense_ shape as the CFBD
# game tables. Scores are UBIGINT in core, so the delta is cast before subtracting.
_DRIVES_SQL = """(
  with d as (
    select dr.game_id, dr.offense_team_id, dr.defense_team_id, f.week, f.season_type,
           dr.plays::double as plays,
           dr.end_offense_score::bigint - dr.start_offense_score::bigint as pts,
           (coalesce(dr.scoring, false) or dr.end_yards_to_goal <= 40)::int as opp,
           dr.start_yards_to_goal::double as start,
           (coalesce(dr.elapsed_minutes, 0) * 60 + coalesce(dr.elapsed_seconds, 0))::double as secs
    from core.fact_drive_postgame dr join core.fact_game f using (game_id)
    where f.season = {season}),
  side as (
    select game_id, offense_team_id as tid, defense_team_id as oid, 'offense' as unit, week, season_type,
           pts, opp, start, plays, secs from d
    union all
    select game_id, defense_team_id, offense_team_id, 'defense', week, season_type,
           pts, opp, start, plays, secs from d),
  g as (
    select game_id, tid, unit, any_value(oid) as oid, any_value(week) as week,
           any_value(season_type) as season_type, count(*)::double as drives,
           sum(pts) / count(*) as ppd, avg(opp) as so_rate, avg(start) as start,
           sum(plays) / count(*) as plays_per_drive, sum(secs) / nullif(sum(plays), 0) as sec_per_play,
           sum(plays) as plays
    from side group by game_id, tid, unit)
  select {season} as season, o.week, o.season_type as "seasonType", o.game_id as "gameId",
         t.school as team, op.school as opponent,
         o.drives as offense_drives, o.ppd as offense_ppd, o.so_rate as offense_so_rate,
         o.start as offense_start, o.plays_per_drive as offense_plays_per_drive,
         o.sec_per_play as offense_sec_per_play, o.plays as offense_plays,
         x.drives as defense_drives, x.ppd as defense_ppd, x.so_rate as defense_so_rate,
         x.start as defense_start, x.plays_per_drive as defense_plays_per_drive,
         x.sec_per_play as defense_sec_per_play, x.plays as defense_plays
  from g o join g x on x.game_id = o.game_id and x.tid = o.tid and x.unit = 'defense'
  join core.dim_team t on t.team_id = o.tid
  join core.dim_team op on op.team_id = o.oid
  where o.unit = 'offense')"""


def latest_week(con, table: str, season: int) -> int | None:
    if table == SOURCES["drives"].table:
        table = "core.fact_game"  # drives key on games; completed games bound them
        r = con.execute("""select max(week) from core.fact_game where season = ? and completed
                           and season_type = 'regular'""", [season]).fetchone()
    else:
        r = con.execute(f"""select max(week) from {table}
                            where season = ? and "seasonType" = 'regular'""", [season]).fetchone()
    return r[0]


def pick_table(con, src: Source, season: int, ngt: bool) -> tuple[str, bool, int | None]:
    """(table, used the no-garbage-time twin?, weeks the twin lags).

    The twin is used only when it is as fresh as its all-plays table; otherwise the section
    falls back to all plays and says so, rather than showing last week's numbers.
    """
    if not (ngt and src.ngt):
        return src.table, False, None
    lag = (latest_week(con, src.table, season) or 0) - (latest_week(con, src.ngt, season) or 0)
    return (src.table, False, lag) if lag > 0 else (src.ngt, True, None)


def windowed(con, src: Source, units: list[Unit], table: str, season: int, week: int, *,
             full: bool, rollup: str, fcs: bool) -> dict[int, dict]:
    """team_id -> {"n": games, "offense_<stem>": v, "defense_<stem>": v} over the window.

    pooled: sum(rate x plays) / sum(plays), what recomputing from the plays would give;
    mean: every game counts once; last3: pooled over each team's three latest games.
    A unit with no weight column pools as a game mean.
    """
    season = int(season)
    source = _DRIVES_SQL.format(season=season) if src.key == "drives" else table
    aggs = []
    for stem, weight in {u.stem: u.weight for u in units}.items():
        for side in ("offense", "defense"):
            col = f'"{side}_{stem}"'
            if rollup == "mean" or weight is None:
                aggs.append(f"avg(s.{col}::double) as {col}")
            else:
                w = f'"{side}_{weight}"'
                aggs.append(f"sum(s.{col}::double * s.{w}) / nullif(sum(case when s.{col} is not null "
                            f"then s.{w} end), 0) as {col}")
    window = ("""s."seasonType" in ('regular', 'postseason')""" if full
              else f"""s."seasonType" = 'regular' and s.week < {int(week)}""")
    fcs_clause = (f"o.team_id in (select teamId from stg.fbs_teams where season = {season})"
                  if fcs else "true")
    last3 = "s.recency <= 3" if rollup == "last3" else "true"
    found = rows(con, f"""
        with base as (
            select t.team_id, s.*,
                   row_number() over (partition by t.team_id
                       order by s."seasonType" = 'postseason' desc, s.week desc) as recency
            from {source} s
            join core.dim_team t on t.school = s.team
            left join core.dim_team o on o.school = s.opponent
            where s.season = {season} and {window} and {fcs_clause})
        select team_id, count(*) as n, max(week) as last_week, {", ".join(aggs)}
        from base s where {last3} group by team_id""")
    return {r["team_id"]: r for r in found}


def expected_games(con, teams: list[int], season: int, week: int, *, full: bool, fcs: bool) -> dict[int, int]:
    """Completed games each team has played in the window: the denominator of 'k of m games'."""
    window = "true" if full else f"g.season_type = 'regular' and g.week < {int(week)}"
    out = {}
    for t in teams:
        opp_fbs = (f"""(case when g.home_team_id = {int(t)} then g.away_team_id else g.home_team_id end)
                      in (select teamId from stg.fbs_teams where season = {int(season)})""" if fcs else "true")
        out[t] = con.execute(f"""select count(*) from core.fact_game g where g.season = ? and g.completed
                                 and ? in (g.home_team_id, g.away_team_id) and {window} and {opp_fbs}""",
                             [season, t]).fetchone()[0]
    return out


def _pct(s: dict) -> float | None:
    return (s["n"] - s["rank"]) / (s["n"] - 1) if s.get("rank") and s["n"] > 1 else None


def units(con, season: int, week: int, a: int, b: int, *, full: bool, rollup: str, fcs: bool,
          ngt: bool) -> dict:
    """Two blocks, A offense vs B defense and B offense vs A defense, one row per concept.

    Each concept row carries every candidate stat already ranked, so switching the row's stat
    on the page needs no refetch. The edge compares where each unit sits in its own ranking
    (percentile), not the raw values, since an offense stat and a defense-allowed stat are not
    one quantity. Prior = last season's full-season value with the same toggles.
    """
    universe, before = fbs(con, season), fbs(con, season - 1)
    cur, prior, status = {}, {}, {}
    expected = expected_games(con, [a, b], season, week, full=full, fcs=fcs)
    through = None if full else week - 1
    for key, src in SOURCES.items():
        us = [u for u in UNITS if u.source == key]
        table, used_ngt, lag = pick_table(con, src, season, ngt)
        cur[key] = windowed(con, src, us, table, season, week, full=full, rollup=rollup, fcs=fcs)
        p_table, _, _ = pick_table(con, src, season - 1, ngt)
        prior[key] = windowed(con, src, us, p_table, season - 1, 99, full=True,
                              rollup="mean" if rollup == "mean" else "pooled", fcs=fcs)
        latest = latest_week(con, table, season)
        status[key] = {
            "label": src.label, "table": table, "ngt": used_ngt, "ngt_lag": lag,
            "all_plays": not used_ngt, "through_week": latest,
            "stale": bool(through and (latest or 0) < through),
            "games": {str(t): cur[key].get(t, {}).get("n", 0) for t in (a, b)},
            "expected": {str(t): expected[t] for t in (a, b)},
        }

    def side(stat: Stat, data: dict, pool: dict, team: int) -> dict:
        vals = {t: r[stat.column] for t, r in data.items()}
        s = _side(stat, vals, pool, team)
        s["games"] = data.get(team, {}).get("n", 0)
        return s

    def option(u: Unit, off: int, dfn: int) -> dict:
        o = Stat(u.key, u.label, u.table, f"offense_{u.stem}", u.higher_is_better, u.fmt, u.verdict, u.reason, u.dp)
        d = replace(o, column=f"defense_{u.stem}",
                    higher_is_better=None if u.higher_is_better is None else not u.higher_is_better)
        so, sd = side(o, cur[u.source], universe, off), side(d, cur[u.source], universe, dfn)
        return {"key": u.key, "label": u.label, "fmt": u.fmt, "dp": u.dp, "verdict": u.verdict,
                "source": f"{status[u.source]['table']}.{{offense,defense}}_{u.stem}",
                "source_key": u.source, "a": so, "b": sd,
                "edge": None if u.higher_is_better is None else edge(_pct(so), _pct(sd), True),
                "prior": {"season": season - 1, "a": side(o, prior[u.source], before, off),
                          "b": side(d, prior[u.source], before, dfn)},
                "estimate": None}

    def block(off: int, dfn: int) -> dict:
        return {"off": off, "def": dfn, "groups": [
            {"group": g, "rows": [{"concept": ck, "label": label,
                                   "options": [option(u, off, dfn) for u in cands]}
                                  for ck, label, cands in concepts]}
            for g, concepts in UNIT_GROUPS]}

    return {"rollup": rollup, "fcs": fcs, "ngt": ngt, "sources": status,
            "blocks": [block(a, b), block(b, a)]}
