"""`build_core` steps must degrade when an optional source is absent, not abort the build.

The live warehouse always has the ActionNetwork tape, so every test that runs against it
sees the rich shape and none of them exercise the poor one. `tests/test_core_merges.py`
already learned this lesson on the *output* side -- `test_source_exists_even_without_the_
actionnetwork_tape` pins `_source` onto `core.fact_game_line` precisely because a column
that appears only when an optional source was present is a trap. These are the same
lesson on the *input* side.

Fixture-built, never against `DATA_ROOT/cfb.duckdb`: the point is the state the live
warehouse is never in.
"""

import sys
from pathlib import Path

import duckdb
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
from cfb_system_maker.duckdb_core import _merge_game_lines  # noqa: E402

# `stg.game_lines` exactly as the CFBD GraphQL dump lands it, before
# `backfill_gamelines_from_actionnetwork` widens it. Nine columns, and neither `period`
# nor `line_source` among them -- both are added by the backfill.
BARE_GAME_LINES = """
    CREATE TABLE stg.game_lines (
      "gameId" UBIGINT, "linesProviderId" UBIGINT,
      "moneylineAway" HUGEINT, "moneylineHome" HUGEINT,
      "overUnder" JSON, "overUnderOpen" DOUBLE,
      spread JSON, "spreadOpen" DOUBLE,
      _source_file VARCHAR
    )
"""


@pytest.fixture
def bare(tmp_path):
    """A warehouse whose ActionNetwork backfill did not run."""
    con = duckdb.connect(str(tmp_path / "bare.duckdb"))
    con.execute("CREATE SCHEMA stg")
    con.execute("CREATE SCHEMA core")
    con.execute(BARE_GAME_LINES)
    con.execute('CREATE TABLE stg.lines_provider ("linesProviderId" UBIGINT, name VARCHAR)')
    con.execute("CREATE TABLE core.fact_game (game_id INTEGER)")
    # Mirrors `_build_fact_game_line`'s CREATE verbatim -- the merge reads every value
    # column off this side of the full outer, so a thinner stand-in fails on the wrong
    # column and the test stops testing what it says it does.
    con.execute(
        """
        CREATE TABLE core.fact_game_line (
          game_id INTEGER NOT NULL, provider_key VARCHAR NOT NULL,
          spread_close DOUBLE, spread_open DOUBLE,
          total_close DOUBLE, total_open DOUBLE,
          moneyline_home INTEGER, moneyline_away INTEGER,
          formatted_spread VARCHAR,
          _source VARCHAR NOT NULL DEFAULT 'rest'
        )
        """
    )
    yield con
    con.close()


def test_the_line_merge_skips_a_game_lines_that_was_never_backfilled(bare):
    """2026-09-11: the 05:00 refresh lost `stg.an_market`, so the backfill returned without
    widening `stg.game_lines`, and this merge -- guarding on the TABLE existing, never on
    the columns it reads -- hit `Binder Error: Table "l" does not have a column named
    "period"`. `build_core` aborted at step 7 of ~14 and left `core` with 6 tables.

    An absent optional source is a skip, the same as every other missing input here."""
    assert _merge_game_lines(bare) is False


def test_the_skip_is_announced(bare):
    """The gap that caused this was invisible for a full run: the backfill returned early
    without a word and nothing downstream said the tape was missing. A skip that says
    nothing is the failure mode, not the fix -- so the warning is pinned."""
    with pytest.warns(RuntimeWarning, match="ActionNetwork backfill did not run"):
        _merge_game_lines(bare)


def test_the_skipped_merge_leaves_the_rest_side_intact(bare):
    """A skip must not be a half-merge: `core.fact_game_line` is `_build_fact_game_line`'s
    REST output and has to survive untouched so the rest of `build_core` can run on it."""
    bare.execute(
        "INSERT INTO core.fact_game_line (game_id, provider_key) VALUES (1, 'draftkings')"
    )
    _merge_game_lines(bare)
    assert bare.execute("SELECT count(*) FROM core.fact_game_line").fetchone()[0] == 1


def test_the_merge_still_runs_when_the_backfill_did_widen_the_table(bare):
    """The guard must key on the columns actually read, not on the tape's presence -- a
    check that never lets the merge run would pass the two tests above and be useless."""
    bare.execute("DROP TABLE stg.game_lines")
    bare.execute(
        BARE_GAME_LINES.replace(
            "_source_file VARCHAR", "_source_file VARCHAR, period VARCHAR, line_source VARCHAR"
        )
    )
    assert _merge_game_lines(bare) is True
