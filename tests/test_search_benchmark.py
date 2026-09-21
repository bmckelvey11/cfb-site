"""MVP-006: performance benchmark + reproducibility gate.

The "Final gate" from the auto-discovery spec's Verification Plan -- proves the
two-tier evaluation design (cheap run_backtest_summary during beam search, expensive
run_backtest only for the top-K holdout finalists) actually holds at representative
data scale, not just fixture scale. Kept out of the default `pytest` run: it needs
the CEO's real built data (~13k games) and can take tens of minutes, which the rest
of the suite (~350 fixture-scale tests, seconds total) should never be gated on.

Run explicitly with: pytest -m slow tests/test_search_benchmark.py -v -s

FINDING (measured 2026-07-30, ~11.4k in-sample games, holdout season 2025, all
default params -- beam_width=100, top_k=20, min_decided_bets=100, max_dimensions=4):
default `search` params do NOT meet the spec's original "minutes, not hours" target.
`beam_search()` alone took 25.8 minutes (1548.6s), evaluating 50,390 candidates and
hitting the full beam_width=100 cap by round 2. Root cause: round 1 yields ~10
qualifying survivors from ~283 candidates; each re-expands into ~280 more children
per round across 4 rounds, compounding to 50k+ evaluations -- not a bug, beam search
doing its job on a wide grammar (49 non-lookahead registry features) at real scale.
Decision (CEO, 2026-07-30): accept this runtime rather than narrow search defaults
or the benchmark's scope. MAX_ELAPSED_SECONDS below reflects the measured ceiling
with headroom for grade_finalists' additional ~20 holdout run_backtest calls, not
an aspirational target -- do not silently tighten it back down without a matching
change to beam_search's actual behavior.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

import cfb_system_maker.search as search_module
from cfb_system_maker.enrich import load_features
from cfb_system_maker.search import beam_search, grade_finalists
from cfb_system_maker.storage import load_processed_games

from cfb_paths import DATA_ROOT  # noqa: E402

DATA_DIR = DATA_ROOT
# See module docstring's FINDING -- measured full-scale beam_search alone was
# 1548.6s; this ceiling adds headroom for grade_finalists' holdout run_backtest
# calls (each with a 1000-iteration permutation test) on top. Not "minutes not
# hours" as originally hoped; accepted as the measured reality (CEO, 2026-07-30).
MAX_ELAPSED_SECONDS = 2700

pytestmark = pytest.mark.skipif(
    not (DATA_DIR / "processed" / "games.csv").exists() or not (DATA_DIR / "processed" / "features.json").exists(),
    reason="requires representative-scale built data (data/processed/games.csv + features.json)",
)


def _load_in_sample_split(holdout_season: int = 2025):
    games = load_processed_games(DATA_DIR)
    feature_map = load_features(DATA_DIR)
    available_seasons = {g.season for g in games}
    in_sample_seasons = available_seasons - {holdout_season}
    holdout_seasons = available_seasons & {holdout_season}

    in_sample_games = [g for g in games if g.season in in_sample_seasons]
    holdout_games = [g for g in games if g.season in holdout_seasons]
    in_sample_ids = {g.game_id for g in in_sample_games}
    holdout_ids = {g.game_id for g in holdout_games}
    in_sample_fm = {gid: row for gid, row in feature_map.items() if gid in in_sample_ids}
    holdout_fm = {gid: row for gid, row in feature_map.items() if gid in holdout_ids}
    return in_sample_games, in_sample_fm, holdout_games, holdout_fm


@pytest.mark.slow
def test_beam_search_never_calls_run_backtest_at_representative_scale(monkeypatch):
    # Call-count instrumentation, not a timing inference (AC#2) -- patches
    # search_module's own name binding, the only one beam_search can actually call.
    in_sample_games, in_sample_fm, _, _ = _load_in_sample_split()
    calls = []
    monkeypatch.setattr(search_module, "run_backtest", lambda *a, **k: calls.append(1))

    beam_search(in_sample_games, in_sample_fm)

    assert calls == []


@pytest.mark.slow
def test_search_completes_within_minutes_at_representative_scale(capsys):
    in_sample_games, in_sample_fm, holdout_games, holdout_fm = _load_in_sample_split()

    t0 = time.monotonic()
    beam_result = beam_search(in_sample_games, in_sample_fm)
    grading = grade_finalists(beam_result, holdout_games, holdout_fm)
    elapsed = time.monotonic() - t0

    with capsys.disabled():
        print(
            f"\n[MVP-006 benchmark] games={len(in_sample_games)} in-sample / "
            f"{len(holdout_games)} holdout, candidates_tested={beam_result.candidates_tested}, "
            f"peak_beam_size={beam_result.peak_beam_size}, "
            f"finalists_graded={grading.finalists_graded}, elapsed={elapsed:.1f}s"
        )

    # Surfaced as a finding, not silently loosened, if this fails -- see module
    # docstring and MVP-006's technical notes.
    assert elapsed < MAX_ELAPSED_SECONDS, (
        f"beam_search + grade_finalists took {elapsed:.1f}s at representative scale "
        f"({len(in_sample_games)} in-sample games), exceeding the {MAX_ELAPSED_SECONDS}s "
        "'minutes not hours' target -- the two-tier design (cheap in-sample summary "
        "evaluation vs expensive holdout run_backtest) is not holding as designed and "
        "needs a redesign pass on MVP-003's beam mechanics, not a loosened threshold."
    )


@pytest.mark.slow
def test_search_reproducible_at_representative_scale():
    # Deliberately NOT a second full ~11.4k-game run -- two full-scale runs would
    # cost another 50+ minutes on top of the timing test above, to re-prove
    # something already covered cheaply at fixture scale by
    # test_deterministic_ranking_same_fixture_twice (search.py's sorting discipline
    # doesn't change with data volume). What that fixture-scale test can't reach is
    # real-data content: actual registry feature values, real spread/total
    # distributions, real string levels for categorical features. This bounds to a
    # single real season (~900 games) -- enough real-data surface to catch a
    # content-dependent nondeterminism bug, cheap enough to run twice.
    games = load_processed_games(DATA_DIR)
    feature_map = load_features(DATA_DIR)
    single_season = min(g.season for g in games)
    scoped_games = [g for g in games if g.season == single_season]
    scoped_ids = {g.game_id for g in scoped_games}
    scoped_fm = {gid: row for gid, row in feature_map.items() if gid in scoped_ids}

    first = beam_search(scoped_games, scoped_fm, min_decided_bets=20)
    second = beam_search(scoped_games, scoped_fm, min_decided_bets=20)

    assert first.candidates_tested == second.candidates_tested
    assert [c.identity for c in first.survivors] == [c.identity for c in second.survivors]
