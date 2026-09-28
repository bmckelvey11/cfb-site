-- Clock-quality diagnostics behind docs/pace-stats-2026-09-24.md.
--   duckdb -readonly data/cfb.duckdb < scripts/pace_clock_coverage.sql
-- The per-game gate lives in core.fact_game_clock_quality (cfb_system_maker/duckdb_core.py).

-- FCS offenses arrive in the play feed in 2022.
select season, count(distinct offense) as offenses from stg.plays group by 1 order by 1;

-- Share of FBS games clean / stale on each clock. Bimodal: staleness is per game.
select q.season, count(*) as games,
  round(avg(clock_ok::int), 3) as clk_clean,
  round(avg((clock_stale_share > 0.5)::int), 3) as clk_stale,
  round(avg(wallclock_ok::int), 3) as wc_clean,
  round(avg((clock_ok or wallclock_ok)::int), 3) as either_clean
from core.fact_game_clock_quality q
join stg.games g on g.gameId = q.game_id
where g.homeClassification = 'fbs' and g.awayClassification = 'fbs'
  and g.seasonType = 'regular'
group by 1 order by 1;

-- Why: clean-clock rate by TV outlet (games with one TV listing). Through 2023 only
-- ABC/ESPN games are reliably clean; in 2024 every outlet jumps.
with tv as (
  select gameId as game_id, any_value(outlet) as outlet
  from stg.media where mediaType = 'tv' group by 1 having count(*) = 1
)
select outlet, count(*) filter (where q.season between 2015 and 2023) as games_15_23,
  round(avg(clock_ok::int) filter (where q.season between 2015 and 2023), 2) as clean_15_23,
  round(avg(clock_ok::int) filter (where q.season = 2023), 2) as clean_2023,
  round(avg(clock_ok::int) filter (where q.season = 2024), 2) as clean_2024,
  round(avg(clock_ok::int) filter (where q.season = 2025), 2) as clean_2025
from core.fact_game_clock_quality q
join tv using (game_id)
join stg.games g on g.gameId = q.game_id
where g.homeClassification = 'fbs' and g.awayClassification = 'fbs'
  and g.seasonType = 'regular'
group by 1 having count(*) filter (where q.season between 2015 and 2023) >= 150
order by clean_15_23 desc;

-- Not the stadium: within the same home team, ABC/ESPN games against every other outlet
-- (2015-2023, home teams with 3+ games of each).
with tv as (
  select gameId as game_id, any_value(outlet) as outlet
  from stg.media where mediaType = 'tv' group by 1 having count(*) = 1
),
fg as (
  select g.homeTeam, q.clock_ok, outlet in ('ABC', 'ESPN') as flagship
  from core.fact_game_clock_quality q
  join stg.games g on g.gameId = q.game_id
  join tv using (game_id)
  where g.homeClassification = 'fbs' and g.awayClassification = 'fbs'
    and g.seasonType = 'regular' and q.season between 2015 and 2023
),
t as (
  select homeTeam,
    avg(clock_ok::int) filter (where flagship) as f,
    avg(clock_ok::int) filter (where not flagship) as o,
    count(*) filter (where flagship) as n_flagship,
    count(*) filter (where not flagship) as n_other
  from fg group by 1 having n_flagship >= 3 and n_other >= 3
)
select count(*) as home_teams, sum(n_flagship) as flagship_games, sum(n_other) as other_games,
  round(avg(f), 3) as clean_abc_espn, round(avg(o), 3) as clean_other,
  round(avg((f > o)::int), 3) as share_teams_flagship_cleaner
from t;

-- Wallclock vs clock tempo on the same neutral, clock-running post-rush pairs in games
-- where both clocks pass, team-season medians.
with p as (
  select pl.*, cast(clock_minutes * 60 + clock_seconds as int) as s,
         try_cast(wallclock as timestamptz) as wc,
         lead(playType) over w as nxt_type, lead(offense) over w as nxt_off,
         lead(period) over w as nxt_period,
         lead(cast(clock_minutes * 60 + clock_seconds as int)) over w as nxt_s,
         lead(try_cast(wallclock as timestamptz)) over w as nxt_wc
  from stg.plays pl
  join core.fact_game_clock_quality q on q.game_id = pl.gameId and q.clock_ok and q.wallclock_ok
  join stg.games g on g.gameId = pl.gameId
  where g.homeClassification = 'fbs' and g.awayClassification = 'fbs'
    and g.seasonType = 'regular' and pl.period <= 4
  window w as (partition by driveId order by playNumber, playId)
),
t as (
  select season, offense, median(s - nxt_s) as clk, median(epoch(nxt_wc) - epoch(wc)) as wc
  from p
  where playType = 'Rush' and yardsGained < distance and nxt_off = offense
    and nxt_period = period and period <= 3
    and nxt_type in ('Rush', 'Pass Reception', 'Pass Incompletion', 'Pass Completion',
                     'Sack', 'Rushing Touchdown', 'Passing Touchdown', 'Interception',
                     'Pass Interception Return', 'Interception Return Touchdown',
                     'Fumble Recovery (Own)', 'Fumble Recovery (Opponent)',
                     'Fumble Return Touchdown', 'Fumble')
    and abs(cast(offenseScore as int) - cast(defenseScore as int)) <= 14
    and not (period = 2 and s <= 120)
  group by 1, 2 having count(*) >= 50
)
select season, count(*) as teams, round(corr(clk, wc), 3) as r_clk_wc,
       median(clk) as med_clk, median(wc) as med_wc
from t group by 1 order by 1;
