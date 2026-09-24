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
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import duckdb

from cfb_paths import current_season
from cfb_system_maker.matchup import odds as odds_mod
from cfb_system_maker.matchup.stats import (
    ADJUSTED, CFBD_PLAYERS_REASON, KICKER_PAAR, PFF_GROUPS, PFF_METRICS, PFF_PLAYERS, PROFILE, RATINGS,
    SOURCES, SPECIAL_TEAMS, UNIT_GROUPS, UNITS, Pff, Source, Stat, Unit, edge,
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
    if cutoff is None:  # a week with no scheduled games still has a calendar start
        cutoff = con.execute("""select start_date from core.dim_week where season = ? and week = ?
                                and season_type = ?""", [season, week, season_type]).fetchone()
        cutoff = cutoff[0] if cutoff else datetime(season, 12, 31)
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


# --- PFF ------------------------------------------------------------------------------------

PFF_FIRST_SEASON = 2019

# PFF numbers weeks 0-19: 0 is CFBD week 1's early (late-August) game, 1-14 are CFBD weeks
# 1-14, 15-17 the late regular season, 18+ bowls (checked 2026-09-23 on five 2025
# schedules). Each team-week is joined to its CFBD game, so the window cuts on kickoff time
# and the FCS toggle sees the opponent. Weeks 15+ stay unmapped: they enter only full-season
# views, which is conservative for as-of windows (never early, sometimes a game short).
def _pff_ctes(season: int) -> str:
    s = int(season)
    return f"""
    pff_map as (select franchise_id, cfbd_team_id as team_id from stg.pff_franchise
                where kind = 'team' and cfbd_team_id is not null),
    tw as (select *, row_number() over (partition by team_id, week order by start_date) as rn,
                  count(*) over (partition by team_id, week) as k
           from (select game_id, week, start_date, home_team_id as team_id, away_team_id as opp_id
                 from core.fact_game where season = {s} and season_type = 'regular' and week <= 14
                 union all
                 select game_id, week, start_date, away_team_id, home_team_id
                 from core.fact_game where season = {s} and season_type = 'regular' and week <= 14)),
    -- the PFF week of each game: a team's first of two CFBD week-1 games is PFF week 0
    tg as (select *, case when week = 1 and k = 2 and rn = 1 then 0 else week end as pff_week from tw)"""


# Plain equality, so DuckDB can hash-join the player-week rows onto their game.
_PFF_JOIN = """join pff_map m on m.franchise_id = p.franchise_id
    left join tg g on g.team_id = m.team_id and g.pff_week = p.week"""


def _pff_where(season: int, cutoff, *, full: bool, fcs: bool, split: bool) -> tuple[str, list]:
    clauses, params = [f"p.season = {int(season)}"], []
    if split:
        clauses.append("p.split = 'all'")
    if not full:
        clauses.append("g.start_date < ?")
        params.append(cutoff)
    if fcs:  # unmapped late-season weeks are FBS matchups
        clauses.append(f"(g.opp_id is null or g.opp_id in "
                       f"(select teamId from stg.fbs_teams where season = {int(season)}))")
    return " and ".join(clauses), params


def pff_team(con, metrics: list[Pff], season: int, cutoff, *, full: bool, rollup: str,
             fcs: bool) -> dict[int, dict]:
    """team_id -> {"n": games, metric.key: value}; one query per PFF table."""
    out: dict[int, dict] = {}
    if season < PFF_FIRST_SEASON:
        return out
    for table in dict.fromkeys(m.table for m in metrics):
        ms = [m for m in metrics if m.table == table]
        sums, finals = [], []
        for m in ms:
            c, w = f'p."{m.column}"', f'p."{m.weight}"'
            num = f"sum({c})" if m.ratio else f"sum({c} * {w})"
            sums.append(f"({num} filter (where {c} is not null))::double as n_{m.key}, "
                        f"(sum({w}) filter (where {c} is not null))::double as d_{m.key}")
            finals.append(f"avg(n_{m.key} / nullif(d_{m.key}, 0)) as {m.key}" if rollup == "mean"
                          else f"sum(n_{m.key}) / nullif(sum(d_{m.key}), 0) as {m.key}")
        where, params = _pff_where(season, cutoff, full=full, fcs=fcs, split=any(m.split for m in ms))
        found = rows(con, f"""
            with {_pff_ctes(season)},
            per_game as (
                select m.team_id, coalesce(g.game_id, -p.week) as gk, max(p.week) as pw, {", ".join(sums)}
                from {table} p {_PFF_JOIN}
                where {where} group by 1, 2),
            ranked as (select *, row_number() over (partition by team_id order by pw desc) as recency
                       from per_game)
            select team_id, count(*) as n, {", ".join(finals)}
            from ranked where {"recency <= 3" if rollup == "last3" else "true"}
            group by team_id""", params)
        for r in found:
            out.setdefault(r["team_id"], {"n": 0}).update({k: v for k, v in r.items() if k != "team_id"})
            out[r["team_id"]]["n"] = max(out[r["team_id"]]["n"], r["n"])
    return out


def _pff_stat(m: Pff) -> Stat:
    return Stat(m.key, m.label, m.table, m.column, m.higher_is_better, m.fmt, m.verdict, m.reason, m.dp)


def _pff_side(m: Pff, data: dict, pool: dict, team: int) -> dict:
    s = _side(_pff_stat(m), {t: r.get(m.key) for t, r in data.items()}, pool, team)
    s["games"] = data.get(team, {}).get("n", 0)
    return s


def pff_latest(con, season: int) -> int | None:
    """The newest PFF week that season, as a CFBD week (0 counts as 1)."""
    r = con.execute("select max(week) from stg.pff_offense_summary where season = ? and week <= 14",
                    [season]).fetchone()[0]
    return None if r is None else max(r, 1)


def pff(con, season: int, week: int, cutoff, a: int, b: int, *, full: bool, rollup: str,
        fcs: bool) -> dict:
    """PFF unit grades in the same two blocks as the CFBD units, edge by rank percentile."""
    if season < PFF_FIRST_SEASON:
        return {"available": False, "reason": f"PFF grades start in {PFF_FIRST_SEASON}"}
    universe, before = fbs(con, season), fbs(con, season - 1)
    metrics = list(PFF_METRICS)
    cur = pff_team(con, metrics, season, cutoff, full=full, rollup=rollup, fcs=fcs)
    prior = pff_team(con, metrics, season - 1, None, full=True,
                     rollup="mean" if rollup == "mean" else "pooled", fcs=fcs)
    latest = pff_latest(con, season)
    status = {"label": "PFF", "through_week": latest,
              "stale": bool(not full and (latest or 0) < week - 1),
              "games": {str(t): cur.get(t, {}).get("n", 0) for t in (a, b)}}

    def option(label: str, o: Pff, d: Pff, off: int, dfn: int) -> dict:
        so, sd = _pff_side(o, cur, universe, off), _pff_side(d, cur, universe, dfn)
        return {"key": f"{o.key}:{d.key}", "label": label, "fmt": [o.fmt, d.fmt], "dp": [o.dp, d.dp],
                "verdict": o.verdict, "source": f"{o.table}.{o.column} vs {d.table}.{d.column}",
                "a": so, "b": sd, "edge": edge(_pct(so), _pct(sd), True),
                "prior": {"season": season - 1, "a": _pff_side(o, prior, before, off),
                          "b": _pff_side(d, prior, before, dfn)},
                "estimate": None}

    def block(off: int, dfn: int) -> dict:
        return {"off": off, "def": dfn, "groups": [
            {"group": g, "rows": [{"concept": ck, "label": label,
                                   "options": [option(ol, o, d, off, dfn) for ol, o, d in opts]}
                                  for ck, label, opts in concepts]}
            for g, concepts in PFF_GROUPS]}

    return {"available": True, "rollup": rollup, "fcs": fcs, "status": status,
            "blocks": [block(a, b), block(b, a)]}


def special_teams(con, season: int, week: int, cutoff, a: int, b: int, *, full: bool, rollup: str,
                  fcs: bool, show_postgame: bool) -> dict:
    """PFF special-teams grades A against B, plus kicker PAAR.

    PAAR is a season-final snapshot, so as-of views show last season's (PRIOR SEASON) and this
    season's only in the postgame panel.
    """
    universe, before = fbs(con, season), fbs(con, season - 1)
    cur = pff_team(con, list(SPECIAL_TEAMS), season, cutoff, full=full, rollup=rollup, fcs=fcs)
    prior = pff_team(con, list(SPECIAL_TEAMS), season - 1, None, full=True,
                     rollup="mean" if rollup == "mean" else "pooled", fcs=fcs)
    out_rows = []
    for m in SPECIAL_TEAMS:
        sa, sb = _pff_side(m, cur, universe, a), _pff_side(m, cur, universe, b)
        out_rows.append({"key": m.key, "label": m.label, "fmt": m.fmt, "dp": m.dp, "verdict": m.verdict,
                         "source": f"{m.table}.{m.column}", "a": sa, "b": sb,
                         "edge": edge(sa["value"], sb["value"], m.higher_is_better),
                         "prior": {"season": season - 1, "a": _pff_side(m, prior, before, a),
                                   "b": _pff_side(m, prior, before, b)},
                         "estimate": None})

    def paar(s: int) -> list[dict]:
        vals = dict(con.execute("""
            select d.team_id, arg_max(k.paar, k.attempts)::double from stg.kicker_paar k
            join core.dim_team d on d.school = k.team where k.season = ? group by d.team_id""",
            [s]).fetchall())
        return [stat_row(KICKER_PAAR, vals, fbs(con, s), a, b, season=s)]

    out = {"available": season >= PFF_FIRST_SEASON, "rows": out_rows,
           "paar": paar(season if full else season - 1), "paar_basis": "postgame" if full else "prior_season"}
    if show_postgame and not full:
        out["postgame"] = paar(season)
    return out


def _pff_players(con, team: int, season: int, cutoff, *, full: bool, fcs: bool) -> dict:
    out = {}
    names = {r["player_id"]: r for r in rows(con, """
        select player_id, any_value(player) as player, any_value(position) as position
        from stg.pff_player_season where season = ? group by player_id""", [season])}
    for role, table, grade, volume, (xlabel, xnum, xden), limit, split in PFF_PLAYERS:
        where, params = _pff_where(season, cutoff, full=full, fcs=fcs, split=split)
        extra = (f'sum(p."{xnum}")::double / nullif(sum(p."{xden}"), 0)' if xden
                 else f'sum(p."{xnum}")::double')
        found = rows(con, f"""
            with {_pff_ctes(season)}
            select p.player_id, count(distinct coalesce(g.game_id, -p.week)) as games,
                   sum(p."{volume}")::double as volume,
                   (sum(p."{grade}" * p."{volume}") filter (where p."{grade}" is not null))::double
                     / nullif(sum(p."{volume}") filter (where p."{grade}" is not null), 0) as grade,
                   {extra} as extra
            from {table} p {_PFF_JOIN}
            where {where} and m.team_id = ?
            group by p.player_id having sum(p."{volume}") > 0""", [*params, team])
        if role == "Defenders":  # best grades among the regulars (40%+ of the top snap count)
            top = max((r["volume"] for r in found), default=0)
            found = sorted((r for r in found if r["volume"] >= 0.4 * top and r["grade"] is not None),
                           key=lambda r: -r["grade"])[:limit]
        else:
            found = sorted(found, key=lambda r: -r["volume"])[:limit]
        out[role] = {"volume": volume, "extra": xlabel, "players": [
            dict(r, **{k: names.get(r["player_id"], {}).get(k) for k in ("player", "position")})
            for r in found]}
    return out


def _cfbd_players(con, team: int, season: int, week: int, *, full: bool, fcs: bool, ngt: bool) -> dict:
    src = Source("players", "stg.ppa_players_games", "stg.ppa_players_games_ngt", "CFBD player PPA")
    table, used_ngt, lag = pick_table(con, src, season, ngt)
    window = ("""p."seasonType" in ('regular', 'postseason')""" if full
              else f"""p."seasonType" = 'regular' and p.week < {int(week)}""")
    fcs_clause = (f"o.team_id in (select teamId from stg.fbs_teams where season = {int(season)})"
                  if fcs else "true")
    found = rows(con, f"""
        select p."athleteId" as athlete_id, any_value(p.name) as player, any_value(p.position) as position,
               count(*) as games, avg(p."averagePPA_all") as ppa, avg(p."averagePPA_pass") as ppa_pass,
               avg(p."averagePPA_rush") as ppa_rush
        from {table} p join core.dim_team t on t.school = p.team
        left join core.dim_team o on o.school = p.opponent
        where p.season = ? and t.team_id = ? and {window} and {fcs_clause}
        group by 1""", [season, team])

    def top(positions, key, limit):
        pool = [r for r in found if r["position"] in positions and r[key] is not None]
        return sorted(pool, key=lambda r: (-r["games"], -r[key]))[:limit]

    return {"table": table, "ngt": used_ngt, "ngt_lag": lag, "verdict": "pregame_windowed",
            "reason": CFBD_PLAYERS_REASON,
            "QB": top({"QB"}, "ppa_pass", 1), "Rushers": top({"RB", "FB"}, "ppa_rush", 3),
            "Receivers": top({"WR", "TE"}, "ppa_pass", 3)}


def schedule(con, team: int, season: int, cutoff, *, full: bool) -> list[dict]:
    """The team's season, one row per game, from its own side.

    As of a week, a game kicking off at or after the cutoff is the future: its score, closing
    line and result are blanked, never sent. `past` marks the games inside the window.
    """
    games = rows(con, """
        select x.*, f.teamId is not null as opp_fbs, pr.rank as opp_rank from (
            select g.game_id, g.week, g.season_type, g.start_date, g.completed,
                   coalesce(sg.neutralSite, false) as neutral, coalesce(sg.conferenceGame, false) as conf,
                   g.home_team_id = ? as is_home,
                   case when g.home_team_id = ? then g.away_team_id else g.home_team_id end as opp_id,
                   case when g.home_team_id = ? then g.away_team else g.home_team end as opp,
                   case when g.home_team_id = ? then g.home_points else g.away_points end as pts,
                   case when g.home_team_id = ? then g.away_points else g.home_points end as opp_pts,
                   case when g.home_team_id = ? then g.median_spread_close else -g.median_spread_close end as spread,
                   g.median_total_close as total, g.season
            from core.v_game_book_median g
            left join (select gameId, neutralSite, conferenceGame from stg.games where season = ?) sg
                   on sg.gameId = g.game_id
            where g.season = ? and ? in (g.home_team_id, g.away_team_id)) x
        left join stg.fbs_teams f on f.teamId = x.opp_id and f.season = x.season
        left join core.fact_poll_rank pr on pr.team_id = x.opp_id and pr.season = x.season
             and pr.week = x.week and pr.season_type = x.season_type and pr.poll_type_id = 1
        order by x.start_date""", [team] * 6 + [season, season, team])
    cut = None if full or cutoff is None else _plain(cutoff)
    for g in games:
        g["past"] = bool(g["completed"]) and (cut is None or g["start_date"] < cut)
        if not g["past"]:
            g.update(pts=None, opp_pts=None, spread=None, total=None)
        g["result"] = _result(g) if g["past"] else None
    return games


def _result(g: dict) -> dict:
    margin = g["pts"] - g["opp_pts"]
    out = {"su": "W" if margin > 0 else "L" if margin < 0 else "T", "margin": margin, "ats": None, "ou": None,
           "cover": None}
    if g["spread"] is not None:
        cover = margin + g["spread"]
        out.update(cover=cover, ats="W" if cover > 0 else "L" if cover < 0 else "P")
    if g["total"] is not None:
        diff = g["pts"] + g["opp_pts"] - g["total"]
        out["ou"] = "O" if diff > 0 else "U" if diff < 0 else "P"
    return out


def betting_profile(games: list[dict]) -> dict:
    """SU / ATS / O-U over the window's completed games, closing consensus lines.

    Computed from the games rather than the postgame ATS tables, so it stops at the cutoff.
    """
    past = [g for g in games if g["past"]]

    def rec(gs: list[dict]) -> dict:
        lined = [g for g in gs if g["result"]["ats"]]
        return {"n": len(gs), "su": [sum(g["result"]["su"] == k for g in gs) for k in "WLT"],
                "ats": [sum(g["result"]["ats"] == k for g in lined) for k in "WLP"],
                "ou": [sum(g["result"]["ou"] == k for g in gs) for k in "OUP"],
                "avg_cover": (sum(g["result"]["cover"] for g in lined) / len(lined)) if lined else None,
                "avg_spread": (sum(g["spread"] for g in lined) / len(lined)) if lined else None,
                "n_lined": len(lined)}

    lined = [g for g in past if g["spread"] is not None]
    # A list, not a dict: Flask's JSON sorts keys, and the order here is the reading order.
    return {"all": rec(past),
            "splits": [["Favorite", rec([g for g in lined if g["spread"] < 0])],
                       ["Underdog", rec([g for g in lined if g["spread"] > 0])],
                       ["Home", rec([g for g in past if g["is_home"] and not g["neutral"]])],
                       ["Away", rec([g for g in past if not g["is_home"] and not g["neutral"]])],
                       ["Neutral", rec([g for g in past if g["neutral"]])],
                       ["vs FBS", rec([g for g in past if g["opp_fbs"]])]]}


def common_opponents(sa: list[dict], sb: list[dict], a: int, b: int) -> list[dict]:
    """Opponents both teams played inside the window, with each team's result against them."""
    pa = {g["opp_id"]: g for g in sa if g["past"] and g["opp_id"] != b}
    pb = {g["opp_id"]: g for g in sb if g["past"] and g["opp_id"] != a}
    return [{"opp": pa[o]["opp"], "opp_id": o, "a": pa[o], "b": pb[o]}
            for o in sorted(pa.keys() & pb.keys(), key=lambda o: pa[o]["start_date"])]


def head_to_head(con, a: int, b: int, cutoff, *, full: bool, season: int) -> dict:
    """Every meeting (1869 on), before the cutoff as of a week, through the season in full mode.

    Lines exist only from 2012 (core.fact_game); earlier meetings carry scores alone.
    """
    limit = "g.start_date < ?" if not full and cutoff is not None else "g.season <= ?"
    param = cutoff if not full and cutoff is not None else season
    pair = "least(g.home_team_id, g.away_team_id) = least(?, ?) and greatest(g.home_team_id, g.away_team_id) = greatest(?, ?)"
    games = rows(con, f"""
        select * from (
            select g.season, g.week, g.season_type, g.start_date, g.home_team_id, g.home_team, g.away_team,
                   g.home_points, g.away_points, coalesce(g.neutral_site, false) as neutral, null::double as spread
            from core.fact_game_historical g where {pair} and {limit}
            union all
            select g.season, g.week, g.season_type, g.start_date, g.home_team_id, g.home_team, g.away_team,
                   g.home_points, g.away_points, coalesce(sg.neutralSite, false), g.median_spread_close
            from core.v_game_book_median g left join stg.games sg on sg.gameId = g.game_id
            where {pair} and g.completed and {limit})
        order by start_date desc""", [a, b, a, b, param] * 2)
    for g in games:
        a_home = g["home_team_id"] == a
        ap, bp = (g["home_points"], g["away_points"]) if a_home else (g["away_points"], g["home_points"])
        g.update(a_points=ap, b_points=bp, a_home=a_home,
                 a_spread=None if g["spread"] is None else (g["spread"] if a_home else -g["spread"]))
        g["winner"] = "a" if ap > bp else "b" if bp > ap else None
        g["a_ats"] = (None if g["a_spread"] is None else
                      "W" if ap - bp + g["a_spread"] > 0 else "L" if ap - bp + g["a_spread"] < 0 else "P")
    return {"n": len(games), "series": {"a": sum(g["winner"] == "a" for g in games),
                                        "b": sum(g["winner"] == "b" for g in games),
                                        "t": sum(g["winner"] is None for g in games)},
            "first": games[-1]["season"] if games else None, "games": games[:10]}


def trends(con, season: int, week: int, cutoff, a: int, b: int, *, full: bool, fcs: bool, ngt: bool) -> dict:
    """Game-by-game values inside the window, for the trend charts: CFBD PPA and success rate
    (the same table the unit matchups used) and PFF offense/defense grades."""
    table, used_ngt, _ = pick_table(con, SOURCES["advanced"], season, ngt)
    window = ("""s."seasonType" in ('regular', 'postseason')""" if full
              else f"""s."seasonType" = 'regular' and s.week < {int(week)}""")
    fcs_clause = (f"o.team_id in (select teamId from stg.fbs_teams where season = {int(season)})"
                  if fcs else "true")
    cfbd = rows(con, f"""
        select t.team_id, s.week, s."seasonType" as season_type, s.opponent,
               s.offense_ppa, s.defense_ppa, s."offense_successRate" as offense_sr,
               s."defense_successRate" as defense_sr
        from {table} s join core.dim_team t on t.school = s.team
        left join core.dim_team o on o.school = s.opponent
        where s.season = ? and t.team_id in (?, ?) and {window} and {fcs_clause}
        order by s."seasonType" = 'postseason', s.week""", [season, a, b])
    grades = []
    if season >= PFF_FIRST_SEASON:
        where, params = _pff_where(season, cutoff, full=full, fcs=fcs, split=False)
        for tbl, col, snaps, key in (("stg.pff_offense_summary", "grades_offense", "snap_counts_total", "pff_offense"),
                                     ("stg.pff_defense_summary", "grades_defense", "snap_counts_defense", "pff_defense")):
            grades += [dict(r, metric=key) for r in rows(con, f"""
                with {_pff_ctes(season)}
                select m.team_id, p.week as pff_week, any_value(g.week) as week,
                       (sum(p.{col} * p.{snaps}) filter (where p.{col} is not null))::double
                         / nullif(sum(p.{snaps}) filter (where p.{col} is not null), 0) as value
                from {tbl} p {_PFF_JOIN}
                where {where} and m.team_id in (?, ?)
                group by 1, 2 order by 2""", [*params, a, b])]
    return {"table": table, "ngt": used_ngt,
            "teams": {str(t): {"cfbd": [r for r in cfbd if r["team_id"] == t],
                               "pff": {k: [r for r in grades if r["team_id"] == t and r["metric"] == k]
                                       for k in ("pff_offense", "pff_defense")}}
                      for t in (a, b)}}


def players(con, season: int, week: int, cutoff, a: int, b: int, *, full: bool, fcs: bool,
            ngt: bool) -> dict:
    """Key players per team: a PFF list and a CFBD list, unlinked (no id crosswalk exists)."""
    return {str(t): {"pff": _pff_players(con, t, season, cutoff, full=full, fcs=fcs)
                     if season >= PFF_FIRST_SEASON else None,
                     "cfbd": _cfbd_players(con, t, season, week, full=full, fcs=fcs, ngt=ngt)}
            for t in (a, b)}
