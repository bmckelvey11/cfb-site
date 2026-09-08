-- Sample PFF staging schema -- DuckDB, runnable as written.
--
-- A sample, not the whole target: one table per family out of the 19 in
-- docs/pff-warehouse-schema.md §3, so the flattener (S3) and the loader (S5) have a
-- concrete shape to build against. Every column below is a real 2025 column, and the
-- primary keys are checked against the files on disk, not assumed.
--
-- Conventions, all of which follow from decisions already made:
--
--   * Grain is (season, week, ...). The weekly file is the row source -- ingest plan S2.
--     There is no season-aggregate row and no `week = 0` sentinel; season-to-date is a
--     windowed SUM over weeks < N. See the example query at the bottom.
--   * Types are pinned here, never inferred per file. 320 team-report columns come back
--     with two declared types across responses (`draftSeason` integer/string, percentages
--     integer/number/string), so the flattener normalizes '' to NULL and the loader takes
--     the types below as the contract -- same treatment as `_AN_TICK_COLUMNS` (f0c729b).
--   * Column sets are the union of that season's weekly headers, matched by name. Weekly
--     sets are disjoint, not nested, so a column absent from one week is NULL there, not
--     a schema change.
--   * Names stay PFF's snake_case, minus the split prefix, which becomes `split`.
--
-- Two conventions in §3 are superseded by S2 and are NOT used here:
--   * "`week` is 0 on season-aggregate rows" -- there are no season-aggregate rows.
--   * `player_game_count` as a fact column -- it is 1 on every weekly row (verified
--     across all 21 weeks of `facet_passing_summary`), so it carries nothing. Games
--     played is COUNT(DISTINCT week).

CREATE SCHEMA IF NOT EXISTS stg;

-- ---------------------------------------------------------------- dimensions

-- The leaderboards carry `franchise_id` on every row, so this is a join key, not a name
-- match. The ~35 hand-maintained entries are only for reaching CFBD (ingest plan S4).
CREATE TABLE stg.pff_franchise (
    franchise_id  INTEGER PRIMARY KEY,
    slug          VARCHAR NOT NULL,        -- 'alabama-crimson-tide', from team_directory
    team_name     VARCHAR NOT NULL,        -- 'S JOSE ST' on a leaderboard row: abbreviated
    kind          VARCHAR NOT NULL CHECK (kind IN ('team', 'allstar')),
    cfbd_team_id  INTEGER,                 -- stg.teams.teamId; NULL until mapped
    match         VARCHAR                  -- 'exact' | 'abbreviation' | 'manual' | NULL
);

-- One row per player-season. No player appeared for two franchises in 2025 (checked), but
-- the key does not assume it stays that way -- franchise_id is an attribute, not a key,
-- and a transfer shows up as a changed value the flattener resolves to the last week seen.
CREATE TABLE stg.pff_player_season (
    season          INTEGER NOT NULL,
    player_id       INTEGER NOT NULL,
    franchise_id    INTEGER NOT NULL REFERENCES stg.pff_franchise,
    player          VARCHAR NOT NULL,
    position        VARCHAR,
    jersey_number   VARCHAR,               -- string: '09', '00', 'D01' are real values
    draft_season    INTEGER,               -- '' -> NULL at flatten; that is the type drift
    eligible_season INTEGER,
    PRIMARY KEY (season, player_id)
);

-- ---------------------------------------------------------------- long split fact

-- The flagship shape: four wide passing reports unpivoted into one long table. `split`
-- carries what used to be a column prefix, so 199 columns become ~40 plus a split label.
-- Verified: (season, week, player_id, franchise_id) is unique across all 2,676 weekly
-- `facet_passing_summary` rows for 2025, so adding `split` cannot collide.
CREATE TABLE stg.pff_passing (
    season       INTEGER NOT NULL,
    week         INTEGER NOT NULL,         -- a real week; weeks 0-20, no sentinel
    player_id    INTEGER NOT NULL,
    franchise_id INTEGER NOT NULL,
    split        VARCHAR NOT NULL,         -- 'all' | 'deep' | 'left_short' | 'pressure' |
                                           -- 'blitz' | 'pa' | 'screen' | 'ttt_le_2_5' ...
    -- counts
    attempts INTEGER, aimed_passes INTEGER, completions INTEGER, yards INTEGER,
    touchdowns INTEGER, interceptions INTEGER, sacks INTEGER, dropbacks INTEGER,
    passing_snaps INTEGER, first_downs INTEGER, big_time_throws INTEGER,
    turnover_worthy_plays INTEGER, drops INTEGER, bats INTEGER, hit_as_threw INTEGER,
    scrambles INTEGER, spikes INTEGER, thrown_aways INTEGER, def_gen_pressures INTEGER,
    penalties INTEGER, declined_penalties INTEGER,
    -- rates and grades: DOUBLE without exception, because PFF declares these integer on
    -- a whole value and number otherwise, in the same column across two responses
    accuracy_percent DOUBLE, completion_percent DOUBLE, ypa DOUBLE, qb_rating DOUBLE,
    avg_depth_of_target DOUBLE, avg_time_to_throw DOUBLE, btt_rate DOUBLE, twp_rate DOUBLE,
    drop_rate DOUBLE, sack_percent DOUBLE, pressure_to_sack_rate DOUBLE,
    epa DOUBLE, positive_epa_percent DOUBLE,
    attempts_percent DOUBLE, dropbacks_percent DOUBLE,
    grades_pass DOUBLE, grades_offense DOUBLE, grades_run DOUBLE, grades_hands_fumble DOUBLE,
    -- provenance: PFF regrades within the live season, so a current-week file is not
    -- immutable and a completed-week one is. This is how a revision is detectable.
    pulled_at    DATE NOT NULL,
    PRIMARY KEY (season, week, player_id, franchise_id, split)
);

-- ---------------------------------------------------------------- wide fact, extra key

-- `team-rushing-direction` is pulled twice per team for one distinct body -- but the body
-- already holds *both* views: `rows` is player-grain and `teamTotals` is franchise-grain,
-- same 19-value direction vocabulary. Nothing is lost by dropping the second call, and the
-- two payloads become two tables from one file (ingest plan S7).
--
-- The direction vocabulary is 19 values, not the 8 gaps §3 lists: the gaps (LE..RE, ML,
-- MR), plus end-around and jet-sweep by side (EA-L/R, JS-L/R), scrambles and designed QB
-- runs (QBK, QBSc, QBSn, QBT, QBF), and R-L/R-R. Enumerated rather than free text so a new
-- value fails loudly instead of silently widening the split.
CREATE TABLE stg.pff_rushing_direction (
    season       INTEGER NOT NULL,
    week         INTEGER NOT NULL,
    player_id    INTEGER NOT NULL,
    franchise_id INTEGER NOT NULL,
    direction    VARCHAR NOT NULL CHECK (direction IN (
                     'LE', 'LT', 'LG', 'ML', 'MR', 'RG', 'RT', 'RE',
                     'EA-L', 'EA-R', 'JS-L', 'JS-R', 'R-L', 'R-R',
                     'QBK', 'QBSc', 'QBSn', 'QBT', 'QBF')),
    attempts INTEGER, yards INTEGER, touchdowns INTEGER, first_downs INTEGER,
    explosive INTEGER, avoided_tackles INTEGER, fumbles INTEGER, longest INTEGER,
    yards_after_contact INTEGER,
    ypa DOUBLE, yco_attempt DOUBLE,
    pulled_at    DATE NOT NULL,
    PRIMARY KEY (season, week, player_id, franchise_id, direction)
);

-- The same file's `teamTotals` payload: identical metrics, franchise grain, no player.
CREATE TABLE stg.pff_team_rushing_direction (
    season       INTEGER NOT NULL,
    week         INTEGER NOT NULL,
    franchise_id INTEGER NOT NULL REFERENCES stg.pff_franchise,
    direction    VARCHAR NOT NULL,
    attempts INTEGER, yards INTEGER, touchdowns INTEGER, first_downs INTEGER,
    explosive INTEGER, avoided_tackles INTEGER, fumbles INTEGER, longest INTEGER,
    yards_after_contact INTEGER,
    ypa DOUBLE, yco_attempt DOUBLE,
    pulled_at    DATE NOT NULL,
    PRIMARY KEY (season, week, franchise_id, direction)
);

-- ---------------------------------------------------------------- team-grain fact

-- `signature-pass-blocking-efficiency-line` is already weekly and franchise-grain: one row
-- per franchise per week (verified -- 216 rows, 216 distinct franchises, wk5 2025). It is
-- 216 and not 136 because the signature exports take no `--division` and so are
-- all-division (c406dcb); `pff_franchise.kind` and `cfbd_team_id` do the filtering
-- downstream rather than the pull doing it.
CREATE TABLE stg.pff_team_pass_block_week (
    season             INTEGER NOT NULL,
    week               INTEGER NOT NULL,
    franchise_id       INTEGER NOT NULL REFERENCES stg.pff_franchise,
    attempts           INTEGER,
    pass_snaps         INTEGER,
    pressures_allowed  INTEGER,
    sacks_allowed      INTEGER,
    hits_allowed       INTEGER,
    hurries_allowed    INTEGER,
    pbe                DOUBLE,   -- pass-blocking efficiency
    pulled_at          DATE NOT NULL,
    PRIMARY KEY (season, week, franchise_id)
);

-- ---------------------------------------------------------------- season-to-date
--
-- What the weekly grain buys: a pre-game feature for week N sees weeks < N and nothing
-- else, so it cannot leak the rest of the season. The season-aggregate row this schema
-- deliberately does not store is one window away.

-- SELECT season, week, player_id,
--        SUM(attempts)    OVER w AS attempts_to_date,
--        SUM(yards)       OVER w AS yards_to_date,
--        COUNT(*)         OVER w AS games_to_date          -- replaces player_game_count
-- FROM   stg.pff_passing
-- WHERE  split = 'all'
-- WINDOW w AS (PARTITION BY season, player_id ORDER BY week
--              ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING);
