-- Why teams are missing from the 2026 pace table; behind docs/pace-clock-gaps-2026-10-15.md.
--   duckdb -readonly data/cfb.duckdb < scripts/pace_clock_gaps.sql
-- Change 2026 below for another season. The per-game gate is core.fact_game_clock_quality
-- (cfb_system_maker/duckdb_core.py); scripts/pace_clock_coverage.sql has the 2012-2025 history.
-- The neutral-snap counts per team come from pace_stats.neutral_mask applied to the last
-- query's rows (Q1-Q3, |margin| <= 14, not the final 2:00 of Q2).

-- Usable clock by season.
select q.season, count(*) games,
  round(avg(clock_ok::int), 3) clock_ok, round(avg(wallclock_ok::int), 3) wallclock_ok,
  round(avg((clock_ok or wallclock_ok)::int), 3) either_ok
from core.fact_game_clock_quality q join stg.games g on g.gameId = q.game_id
where g.homeClassification = 'fbs' and g.awayClassification = 'fbs' and g.seasonType = 'regular'
  and q.season between 2024 and 2026
group by 1 order by 1;

-- By week (completed games; a game with no quality row counts as not ok).
select g.week, count(*) games, count(q.game_id) with_quality_row,
  sum(coalesce(q.clock_ok, false)::int) clock_ok,
  sum(coalesce(q.wallclock_ok, false)::int) wallclock_ok,
  sum(coalesce(q.clock_ok or q.wallclock_ok, false)::int) either_ok,
  round(avg(coalesce(q.clock_ok, false)::int), 3) clock_ok_share
from stg.games g left join core.fact_game_clock_quality q on q.game_id = g.gameId
where g.season = 2026 and g.homeClassification = 'fbs' and g.awayClassification = 'fbs'
  and g.seasonType = 'regular' and g.completed
group by 1 order by 1;

-- By TV outlet (games with exactly one TV listing).
with tv as (select gameId game_id, any_value(outlet) outlet from stg.media
            where mediaType = 'tv' and season = 2026 group by 1 having count(*) = 1)
select coalesce(tv.outlet, '(none/multiple)') outlet, count(*) games,
  sum((not q.clock_ok)::int) failing, round(avg(q.clock_ok::int), 2) clock_ok_share
from core.fact_game_clock_quality q join stg.games g on g.gameId = q.game_id
left join tv using (game_id)
where q.season = 2026 and g.homeClassification = 'fbs' and g.awayClassification = 'fbs'
  and g.seasonType = 'regular'
group by 1 order by failing desc, games desc;

-- By home conference.
select g.homeConference, count(*) games, sum((not q.clock_ok)::int) failing,
  round(avg(q.clock_ok::int), 2) clock_ok_share
from core.fact_game_clock_quality q join stg.games g on g.gameId = q.game_id
where q.season = 2026 and g.homeClassification = 'fbs' and g.awayClassification = 'fbs'
  and g.seasonType = 'regular'
group by 1 order by failing desc;

-- Failing games: is the clock stuck or missing?
with fail as (select q.game_id, q.clock_stale_share from core.fact_game_clock_quality q
              join stg.games g on g.gameId = q.game_id
              where q.season = 2026 and not q.clock_ok and g.homeClassification = 'fbs'
                and g.awayClassification = 'fbs' and g.seasonType = 'regular')
select case when f.clock_stale_share >= 0.5 then 'mostly stale (>=50%)'
            else 'borderline (10-50%)' end band,
  count(distinct f.game_id) games, count(*) plays,
  sum((p.clock_minutes is null or p.clock_seconds is null)::int) null_clock_plays,
  sum((p.wallclock is null)::int) null_wallclock_plays
from fail f join stg.plays p on p.gameId = f.game_id
group by 1;

-- Home teams with 2+ failing games.
select g.homeTeam, count(*) home_games, sum((not q.clock_ok)::int) failing
from core.fact_game_clock_quality q join stg.games g on g.gameId = q.game_id
where q.season = 2026 and g.homeClassification = 'fbs' and g.awayClassification = 'fbs'
  and g.seasonType = 'regular'
group by 1 having sum((not q.clock_ok)::int) >= 2 order by failing desc, home_games;

-- Example stuck clock: Ohio State vs Ball State, week 1, Q1 (game 401858432).
select p.playNumber, p.period, p.offense, p.playType, p.clock_minutes, p.clock_seconds, p.wallclock
from stg.plays p join stg.games g on g.gameId = p.gameId
where g.season = 2026 and g.week = 1 and g.homeTeam = 'Ohio State' and p.period = 1
order by p.driveNumber, p.playNumber limit 12;

-- Post-rush snap pairs with both clocks, in games passing either gate. Same pairing rule
-- as pace_stats.PAIRS_SQL (non-first-down rush, next scrimmage snap in the same drive).
with fbs as (
  select g.gameId, q.clock_ok, q.wallclock_ok from stg.games g
  join core.fact_game_clock_quality q on q.game_id = g.gameId and (q.clock_ok or q.wallclock_ok)
  where g.season = 2026 and g.homeClassification = 'fbs' and g.awayClassification = 'fbs'
    and g.seasonType = 'regular'
),
p as (
  select pl.gameId, pl.week, pl.offense, pl.defense, pl.playType, pl.period, pl.yardsGained,
         pl.distance, fbs.clock_ok, fbs.wallclock_ok,
         cast(pl.offenseScore as int) - cast(pl.defenseScore as int) margin,
         cast(pl.clock_minutes * 60 + pl.clock_seconds as int) secs_left,
         try_cast(pl.wallclock as timestamptz) wall,
         lead(pl.playType) over w nxt_type, lead(pl.offense) over w nxt_offense,
         lead(pl.period) over w nxt_period,
         lead(cast(pl.clock_minutes * 60 + pl.clock_seconds as int)) over w nxt_secs,
         lead(try_cast(pl.wallclock as timestamptz)) over w nxt_wall
  from stg.plays pl join fbs using (gameId)
  window w as (partition by pl.driveId order by pl.playNumber, pl.playId)
)
select gameId game_id, week, offense, defense, period, secs_left, margin, clock_ok, wallclock_ok,
       secs_left - nxt_secs dclk, epoch(nxt_wall) - epoch(wall) dwall
from p
where playType = 'Rush' and period <= 4 and nxt_offense = offense and nxt_period = period
  and nxt_type in ('Rush', 'Pass Reception', 'Pass Incompletion', 'Pass Completion', 'Sack',
    'Rushing Touchdown', 'Passing Touchdown', 'Interception', 'Pass Interception Return',
    'Interception Return Touchdown', 'Fumble Recovery (Own)', 'Fumble Recovery (Opponent)',
    'Fumble Return Touchdown', 'Fumble')
  and yardsGained < distance;
