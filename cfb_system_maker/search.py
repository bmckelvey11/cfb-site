"""Candidate generation + in-sample beam search for auto-discovering betting systems.

Candidate generation (MVP-002) owns canonical candidate identity (for dedup and
deterministic tie-breaking), the compatibility grammar for expanding a candidate by
exactly one predicate dimension, and in-sample-only value derivation (quantiles for
numeric features, capped sorted levels for boolean/categorical features) — pure,
side-effect-free, no evaluation.

Beam search (MVP-003, see bottom of file) evaluates candidates using
`run_backtest_summary` only — `run_backtest` (full, 1000-iteration permutation test)
is never imported or called here; that stage is MVP-004's holdout finalist grading.

Scope cuts made deliberately for MVP (see .solopreneur/backlog/2026-07-22-auto-discover-
systems/backlog.md cross-cutting risk #5):
  - Team-scoped registry features are only generated from the `bet_side` perspective.
    Home/away/either/opponent perspectives are not generated here.
  - `seasons`, `weeks`, `teams`, `conferences`, `providers` are treated as external
    search *scope*, not generated candidate dimensions (they are high-cardinality and
    MVP-003 already treats season range as scope config, not a beam dimension). They
    pass through from the seed `SystemFilter` unchanged and are still sorted explicitly
    by `candidate_identity` per the ticket's requirement.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from cfb_system_maker.backtest import (
    _analytic_p_value,
    _break_even_rate,
    _wilson_interval,
    bh_correct,
    run_backtest,
    run_backtest_summary,
)
from cfb_system_maker.features import FEATURE_REGISTRY, resolve_feature_value
from cfb_system_maker.models import BacktestResult, FeatureFilter, GameRecord, SystemFilter

# Non-lookahead registry features only, in fixed FEATURE_REGISTRY tuple order
# (never dict/set order) so downstream iteration is deterministic.
_CANDIDATE_FEATURES = tuple(f for f in FEATURE_REGISTRY if f.group != "result_lookahead")

# Fixed quartile scheme for numeric feature/spread/total thresholds (MVP — no smart
# binning). Interior cut points only; min/max are not useful thresholds on their own.
_QUANTILES: tuple[float, ...] = (0.25, 0.5, 0.75)

# Deterministic cap on distinct boolean/categorical levels considered per dimension:
# top-N most frequent in-sample levels, ties broken by value ascending. Documented here
# per the ticket's requirement for an explicit, stated limit.
_CATEGORICAL_LIMIT = 8

_HARD_DIMENSION_CAP = 6
_DEFAULT_MAX_DIMENSIONS = 4

# Dimension name constants.
_DIM_FAVORITE_UNDERDOG = "favorite_underdog"
_DIM_HOME_AWAY = "home_away"
_DIM_SPREAD_RANGE = "spread_range"
_DIM_TOTAL_RANGE = "total_range"


def _feature_dimension(key: str) -> str:
    return f"feature:{key}"


def _sort_value(value: Any) -> Any:
    """Normalize a FeatureFilter.value for canonical, order-independent comparison."""
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(sorted(value, key=lambda v: (str(type(v)), v)))
    return value


def _feature_filter_key(filt: FeatureFilter) -> tuple:
    return (filt.key, filt.op, str(type(filt.value)), _sort_value(filt.value), filt.perspective)


def _sortable_optional_float(value: float | None) -> tuple[bool, float]:
    """Make an Optional[float] field totally orderable for tuple sort/comparison.

    None sorts before any real value; a real 0.0 never collides with None since the
    leading bool differs. Needed because candidate_identity tuples are used as sort
    keys, and plain None/float comparison raises TypeError.
    """
    return (value is not None, value if value is not None else 0.0)


def candidate_identity(system: SystemFilter) -> tuple:
    """Canonical, fully sorted identity for a SystemFilter.

    Used for both deduplication during expansion and as the deterministic tie-break
    key when ranking (MVP-003). Set-typed fields are sorted explicitly — never relies
    on Python's randomized set-iteration order. feature_filters is order-independent:
    two SystemFilters with the same filters in different tuple order collapse to the
    same identity.
    """
    return (
        system.bet_type,
        system.side,
        system.total_side,
        tuple(sorted(system.seasons)),
        tuple(sorted(system.weeks)),
        tuple(sorted(system.teams)),
        tuple(sorted(system.conferences)),
        system.favorite,
        system.underdog,
        system.home,
        system.away,
        system.fade,
        tuple(sorted(system.providers)),
        _sortable_optional_float(system.min_spread),
        _sortable_optional_float(system.max_spread),
        _sortable_optional_float(system.min_total),
        _sortable_optional_float(system.max_total),
        tuple(sorted((_feature_filter_key(f) for f in system.feature_filters))),
    )


def active_dimensions(system: SystemFilter) -> set[str]:
    """Which candidate dimensions are already set on this SystemFilter."""
    dims: set[str] = set()
    if system.favorite or system.underdog:
        dims.add(_DIM_FAVORITE_UNDERDOG)
    if system.home or system.away:
        dims.add(_DIM_HOME_AWAY)
    if system.min_spread is not None or system.max_spread is not None:
        dims.add(_DIM_SPREAD_RANGE)
    if system.min_total is not None or system.max_total is not None:
        dims.add(_DIM_TOTAL_RANGE)
    for filt in system.feature_filters:
        dims.add(_feature_dimension(filt.key))
    return dims


def count_dimensions(system: SystemFilter) -> int:
    """Count of active candidate DIMENSIONS (not values).

    Deliberately a different counting scheme from backtest.count_overfit_filters,
    which counts individual values (e.g. each team/season/week/feature-in-value
    counts separately for overfit scoring). This function counts one per dimension
    regardless of how many candidate values were tried for it — used only to enforce
    the filter-dimension cap during generation/expansion. Does not import or reuse
    count_overfit_filters.
    """
    return len(active_dimensions(system))


def _is_noop(system: SystemFilter) -> bool:
    return count_dimensions(system) == 0


def _feature_values(
    games: list[GameRecord],
    feature_map: dict[int, dict[str, Any]],
    feature_key: str,
    perspective: str,
) -> list[Any]:
    """Extract non-None in-sample values for one feature via the same resolver
    matches_system/feature_ok use, so derived thresholds are read from the exact
    storage columns the matcher later reads. games/feature_map must be the caller's
    in-sample split only — this function has no access to storage/enrich and cannot
    reach for holdout data itself.

    For "bet_side" perspective, the eventual candidate's side (home or away) isn't
    known yet at generation time, so values are pooled from both home_<key> and
    away_<key> columns (resolved via perspective="either") rather than assuming a
    fixed side. This avoids skewing thresholds toward one side's distribution for
    features that aren't home/away symmetric (e.g. pregame win prob).
    """
    from cfb_system_maker import features as features_module

    feature = features_module.FEATURE_BY_KEY[feature_key]
    lookup_perspective = "either" if perspective == "bet_side" else perspective
    filt = FeatureFilter(key=feature_key, op="eq", value=None, perspective=lookup_perspective)
    system_like = SystemFilter(side="home")
    values: list[Any] = []
    for game in games:
        row = feature_map.get(game.game_id, {})
        value = resolve_feature_value(row, feature, filt, system_like)
        if lookup_perspective == "either" and isinstance(value, tuple):
            values.extend(v for v in value if v is not None)
            continue
        if value is None:
            continue
        values.append(value)
    return values


def numeric_quantile_values(
    games: list[GameRecord],
    feature_map: dict[int, dict[str, Any]],
    feature_key: str,
    perspective: str = "bet_side",
    *,
    quantiles: tuple[float, ...] = _QUANTILES,
) -> list[float]:
    """Fixed-quantile candidate thresholds for a numeric feature, in-sample only.

    games/feature_map are required plain arguments (mirrors backtest.run_backtest's
    signature) — there is no code path here that reaches into storage/enrich, so it is
    structurally impossible to pass holdout rows in without the caller doing so
    explicitly.
    """
    values = sorted(v for v in _feature_values(games, feature_map, feature_key, perspective) if isinstance(v, (int, float)))
    if not values:
        return []
    n = len(values)
    thresholds: list[float] = []
    for q in quantiles:
        idx = min(n - 1, max(0, int(round(q * (n - 1)))))
        thresholds.append(float(values[idx]))
    # dedup while preserving ascending order (collapsed bins produce repeats)
    deduped: list[float] = []
    for t in thresholds:
        if not deduped or deduped[-1] != t:
            deduped.append(t)
    return deduped


def categorical_or_bool_values(
    games: list[GameRecord],
    feature_map: dict[int, dict[str, Any]],
    feature_key: str,
    perspective: str = "bet_side",
    *,
    limit: int = _CATEGORICAL_LIMIT,
) -> list[Any]:
    """Sorted, frequency-capped in-sample levels for a boolean/categorical feature.

    Levels are ranked by (-count, value) so ties break deterministically on the value
    itself, then capped to `limit` (default 8) — the documented deterministic cap on
    distinct levels considered per dimension. games/feature_map are required plain
    in-sample arguments, same non-leak guarantee as numeric_quantile_values.
    """
    values = _feature_values(games, feature_map, feature_key, perspective)
    counts: dict[Any, int] = {}
    for v in values:
        counts[v] = counts.get(v, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], str(item[0])))
    return [value for value, _ in ranked[:limit]]


def _spread_range_children(parent: SystemFilter, games: list[GameRecord]) -> list[SystemFilter]:
    # Note: thresholds are derived from the raw home spread (GameRecord.spread), while
    # matches_system applies min_spread/max_spread to the side-adjusted spread
    # (negated for away bets). Acceptable for MVP — candidates are evaluated
    # empirically by MVP-003's beam search, which will simply score a poorly-placed
    # threshold lower rather than silently misbehave.
    spreads = sorted(g.spread for g in games if g.spread is not None)
    if not spreads:
        return []
    n = len(spreads)
    children = []
    for q in _QUANTILES:
        idx = min(n - 1, max(0, int(round(q * (n - 1)))))
        threshold = float(spreads[idx])
        children.append(replace(parent, min_spread=threshold))
        children.append(replace(parent, max_spread=threshold))
    return children


def _total_range_children(parent: SystemFilter, games: list[GameRecord]) -> list[SystemFilter]:
    totals = sorted(g.total for g in games if g.total is not None)
    if not totals:
        return []
    n = len(totals)
    children = []
    for q in _QUANTILES:
        idx = min(n - 1, max(0, int(round(q * (n - 1)))))
        threshold = float(totals[idx])
        children.append(replace(parent, min_total=threshold))
        children.append(replace(parent, max_total=threshold))
    return children


def _feature_children(
    parent: SystemFilter,
    games: list[GameRecord],
    feature_map: dict[int, dict[str, Any]],
) -> list[SystemFilter]:
    children: list[SystemFilter] = []
    for feature in _CANDIDATE_FEATURES:
        # Team-scoped features generated from bet_side perspective only (documented
        # MVP scope cut). Non-team-scoped features use "single" perspective.
        perspective = "bet_side" if feature.team_scoped else "single"

        if feature.control == "numeric":
            for threshold in numeric_quantile_values(games, feature_map, feature.key, perspective):
                for op in ("gte", "lte"):
                    filt = FeatureFilter(key=feature.key, op=op, value=threshold, perspective=perspective)
                    children.append(replace(parent, feature_filters=parent.feature_filters + (filt,)))
        else:  # bool or categorical
            for level in categorical_or_bool_values(games, feature_map, feature.key, perspective):
                filt = FeatureFilter(key=feature.key, op="eq", value=level, perspective=perspective)
                children.append(replace(parent, feature_filters=parent.feature_filters + (filt,)))
    return children


def expand_candidates(
    parent: SystemFilter,
    games: list[GameRecord],
    feature_map: dict[int, dict[str, Any]],
    *,
    max_dimensions: int = _DEFAULT_MAX_DIMENSIONS,
    hard_cap: int = _HARD_DIMENSION_CAP,
) -> list[SystemFilter]:
    """Expand `parent` by exactly one legal, compatible predicate dimension.

    games/feature_map must be the caller's in-sample split only (mirrors
    backtest.run_backtest's signature) — no storage/enrich access happens here.

    Grammar rules enforced:
      - Never combines mutually exclusive choices (favorite+underdog, home+away,
        incompatible spread/total bound pairs) in one candidate.
      - Never sets a dimension already active on `parent`.
      - Never emits a child identical to `parent`, and never emits the no-op/empty
        SystemFilter (only relevant when `parent` itself has no active dimensions —
        such a parent produces normal one-dimension children, but a child that ends
        up no-op, i.e. impossible here by construction, would be rejected too).
      - Children are deduplicated by candidate_identity and returned sorted by
        candidate_identity for deterministic order.
    """
    if hard_cap > _HARD_DIMENSION_CAP:
        raise ValueError(f"hard_cap may not exceed {_HARD_DIMENSION_CAP}")
    if max_dimensions > hard_cap:
        raise ValueError("max_dimensions may not exceed hard_cap")

    active = active_dimensions(parent)
    if len(active) >= max_dimensions:
        return []

    children: list[SystemFilter] = []

    if _DIM_FAVORITE_UNDERDOG not in active:
        children.append(replace(parent, favorite=True))
        children.append(replace(parent, underdog=True))

    if _DIM_HOME_AWAY not in active:
        # home/away flags only restrict matches_system when paired with the matching
        # `side` (verified against matches_system: side="away", home=True -> 0
        # matches) — set both together as one candidate, never the bool alone.
        children.append(replace(parent, home=True, side="home"))
        children.append(replace(parent, away=True, side="away"))

    if _DIM_SPREAD_RANGE not in active and parent.bet_type == "spread":
        children.extend(_spread_range_children(parent, games))

    if _DIM_TOTAL_RANGE not in active:
        children.extend(_total_range_children(parent, games))

    existing_feature_dims = {d for d in active if d.startswith("feature:")}
    feature_children = _feature_children(parent, games, feature_map)
    for child in feature_children:
        new_filt = child.feature_filters[-1]
        if _feature_dimension(new_filt.key) in existing_feature_dims:
            continue
        children.append(child)

    seen: set[tuple] = set()
    deduped: list[SystemFilter] = []
    for child in children:
        if child == parent or _is_noop(child):
            continue
        identity = candidate_identity(child)
        if identity in seen:
            continue
        seen.add(identity)
        deduped.append(child)

    deduped.sort(key=candidate_identity)
    return deduped


# --- MVP-003: in-sample beam search -----------------------------------------------
#
# Evaluation-only stage. Ranks/prunes candidates from expand_candidates using
# run_backtest_summary exclusively (match+grade, no permutation test) — run_backtest
# (full, 1000-iteration permutation) is never imported or called here. A test spy
# asserts this at zero calls (see tests/test_search.py).

_DEFAULT_BEAM_WIDTH = 100
_DEFAULT_TOP_K = 20
_DEFAULT_MIN_DECIDED_BETS = 100
_DEFAULT_ALPHA = 0.05


@dataclass(frozen=True)
class BeamCandidate:
    """One evaluated candidate: the SystemFilter plus its in-sample summary stats."""

    system: SystemFilter
    wins: int
    losses: int
    decided: int
    roi: float
    wilson_low: float
    identity: tuple


@dataclass(frozen=True)
class BeamSearchResult:
    survivors: tuple[BeamCandidate, ...]  # top-K, ranked, deterministic order
    candidates_tested: int  # N distinct candidates evaluated across all rounds
    effective_params: dict[str, int | float]


def _rank_key(candidate: BeamCandidate) -> tuple:
    return (-candidate.wilson_low, -candidate.roi, -candidate.decided, candidate.identity)


def _evaluate(
    system: SystemFilter,
    games: list[GameRecord],
    feature_map: dict[int, dict[str, Any]],
) -> BeamCandidate:
    summary = run_backtest_summary(games, system, feature_map=feature_map)
    decided = summary["wins"] + summary["losses"]
    wilson_low, _ = _wilson_interval(summary["hit_rate"], decided)
    return BeamCandidate(
        system=system,
        wins=summary["wins"],
        losses=summary["losses"],
        decided=decided,
        roi=summary["roi"],
        wilson_low=wilson_low,
        identity=candidate_identity(system),
    )


def beam_search(
    games: list[GameRecord],
    feature_map: dict[int, dict[str, Any]],
    *,
    seed: SystemFilter | None = None,
    beam_width: int = _DEFAULT_BEAM_WIDTH,
    top_k: int = _DEFAULT_TOP_K,
    min_decided_bets: int = _DEFAULT_MIN_DECIDED_BETS,
    alpha: float = _DEFAULT_ALPHA,
    max_dimensions: int = _DEFAULT_MAX_DIMENSIONS,
    hard_cap: int = _HARD_DIMENSION_CAP,
) -> BeamSearchResult:
    """Greedy/beam search over expand_candidates, in-sample evaluation only.

    `games`/`feature_map` must already be the caller's in-sample split (e.g. games
    filtered to split_holdout's in-sample seasons) — this function never partitions
    or restricts them itself, and never calls split_holdout or run_backtest. Passing
    the full unsplit dataset here is a caller bug, not something this function can
    detect or guard against structurally beyond its signature taking exactly the
    rows to evaluate on.

    Rank/prune ordering (deterministic): in-sample Wilson lower bound (desc) ->
    ROI (desc) -> decided-bet count (desc) -> candidate_identity (asc, tie-break).
    Wilson bound uses the standard 95% z=1.96 regardless of `alpha` -- `alpha` is
    accepted, defaulted, and reported in effective_params for provenance/pass-through
    to MVP-004's BH correction only; it does not change beam-stage ranking.

    Beam mechanics: start from `seed` (default: empty SystemFilter). Each round,
    expand every surviving beam member by one more dimension via expand_candidates,
    evaluate all newly-seen expansions (deduplicated globally by candidate_identity
    so a candidate reachable via multiple expansion paths is evaluated once), drop
    candidates below min_decided_bets or with non-positive ROI, keep the top
    `beam_width` by rank for the next round's expansion. Stops when no round
    produces any new legal expansion (max_dimensions reached or grammar exhausted).
    Note: pruning is greedy, not recall-complete — a parent dropped for non-positive
    ROI is never expanded, so a deeper candidate that would only become profitable
    after one more dimension on an unprofitable parent is never explored. Sample-size
    pruning has no such gap: every added dimension strictly narrows the matched game
    set, so decided-bet count is monotonically non-increasing as dimensions
    accumulate, and a parent pruned for low decided count can never hide a
    higher-decided-count child.

    top_k is drawn from the union of every surviving candidate across all rounds,
    not just the final round's beam — a shallower candidate can outrank a deeper
    one and must not be dropped just because expansion continued past it.
    """
    seed_system = seed if seed is not None else SystemFilter()

    seen_identities: set[tuple] = {candidate_identity(seed_system)}
    all_survivors: list[BeamCandidate] = []
    beam: list[SystemFilter] = [seed_system]
    tested = 0

    while beam:
        expansions: list[SystemFilter] = []
        for parent in beam:
            for child in expand_candidates(parent, games, feature_map, max_dimensions=max_dimensions, hard_cap=hard_cap):
                identity = candidate_identity(child)
                if identity in seen_identities:
                    continue
                seen_identities.add(identity)
                expansions.append(child)

        if not expansions:
            break

        expansions.sort(key=candidate_identity)
        evaluated = [_evaluate(child, games, feature_map) for child in expansions]
        tested += len(evaluated)

        qualifying = [c for c in evaluated if c.decided >= min_decided_bets and c.roi > 0]
        qualifying.sort(key=_rank_key)

        all_survivors.extend(qualifying)
        beam = [c.system for c in qualifying[:beam_width]]

    all_survivors.sort(key=_rank_key)
    top = tuple(all_survivors[:top_k])

    return BeamSearchResult(
        survivors=top,
        candidates_tested=tested,
        effective_params={
            "beam_width": beam_width,
            "top_k": top_k,
            "min_decided_bets": min_decided_bets,
            "alpha": alpha,
            "max_dimensions": max_dimensions,
        },
    )


# --- MVP-004: holdout finalist grading + BH correction ----------------------------
#
# Final evaluation-only stage. Takes the fixed, already-ranked top-K survivors from
# beam_search (MVP-003) and touches holdout data exactly once per survivor via a full
# run_backtest call -- never split_holdout, never any code path back into candidate
# selection/ranking. Finalist order/identity is entirely inherited from
# beam_result.survivors; this stage only measures and annotates, it never re-sorts by
# holdout performance (that would be exactly the leakage this ticket exists to avoid).

_DEFAULT_AMERICAN_ODDS = -110


@dataclass(frozen=True)
class GradedFinalist:
    """One beam-search survivor after a single holdout-only run_backtest call."""

    system: SystemFilter
    holdout_result: BacktestResult
    raw_p: float
    corrected_p: float
    bh_significant: bool


@dataclass(frozen=True)
class FinalistGradingResult:
    finalists: tuple[GradedFinalist, ...]
    candidates_tested: int  # N, pass-through from BeamSearchResult, provenance only
    finalists_graded: int  # K, count after zero-holdout-bet exclusion


def grade_finalists(
    beam_result: BeamSearchResult,
    holdout_games: list[GameRecord],
    holdout_feature_map: dict[int, dict[str, Any]],
    *,
    alpha: float = _DEFAULT_ALPHA,
    american_odds: int = _DEFAULT_AMERICAN_ODDS,
) -> FinalistGradingResult:
    """Grade beam_result.survivors on holdout data and BH-correct across them.

    holdout_games/holdout_feature_map must already be the caller's holdout-only split
    (e.g. from backtest.split_holdout) -- this function never calls split_holdout or
    reaches for "the full dataset" itself, and never partitions its inputs further.

    Finalist identity and order are fixed by beam_result.survivors before this
    function runs; holdout results are never used to re-rank or re-select finalists.
    Output preserves beam_result.survivors order (minus any zero-holdout-bet
    exclusions) -- do not sort by corrected_p, holdout ROI, or any holdout-derived
    field.

    At most one full run_backtest call per survivor (never once per candidate
    evaluated during beam_search) -- this and a cheap run_backtest_summary pre-check
    per survivor are the only places holdout data is touched, and neither ever feeds
    back into candidate selection/ranking. A survivor whose holdout data yields zero
    matched bets is excluded from the returned finalists entirely (not graded on a
    near-zero/empty sample); the summary pre-check (match+grade, no permutation test)
    detects this before the expensive full run_backtest call, so a zero-match
    survivor never triggers a full call at all -- total full run_backtest calls equal
    finalists_graded exactly, never len(beam_result.survivors).

    BH correction (backtest.bh_correct) runs as a single batch over the analytic
    p-value (backtest._analytic_p_value, NOT the permutation p-value) of every
    surviving (non-excluded) finalist's holdout counts -- batch size K =
    finalists_graded, explicitly not N = candidates_tested. The full run_backtest's
    permutation p-value and letter grade are retained on holdout_result and reported
    only as descriptive secondary statistics, uninvolved in the BH batch.

    alpha is accepted as this function's own parameter (default matches
    beam_search's _DEFAULT_ALPHA) rather than implicitly reused from
    beam_result.effective_params["alpha"] -- callers who want beam_search's alpha
    must pass it explicitly (e.g. grade_finalists(..., alpha=beam_result.
    effective_params["alpha"])). Keeps this function's contract independent of
    beam_result's internals, mirroring how MVP-003 documented alpha as pass-through.
    """
    break_even_rate = _break_even_rate(american_odds)

    kept_systems: list[SystemFilter] = []
    kept_results: list[BacktestResult] = []
    raw_p_values: list[float] = []

    for candidate in beam_result.survivors:
        summary = run_backtest_summary(
            holdout_games, candidate.system, feature_map=holdout_feature_map, american_odds=american_odds
        )
        if summary["wins"] + summary["losses"] + summary["pushes"] == 0:
            continue
        result = run_backtest(
            holdout_games, candidate.system, feature_map=holdout_feature_map, american_odds=american_odds
        )
        decided = result.wins + result.losses
        raw_p = _analytic_p_value(result.wins, decided, break_even_rate)

        kept_systems.append(candidate.system)
        kept_results.append(result)
        raw_p_values.append(raw_p)

    bh_rows = bh_correct(raw_p_values, alpha=alpha)

    finalists = tuple(
        GradedFinalist(
            system=system,
            holdout_result=result,
            raw_p=row["raw_p"],
            corrected_p=row["corrected_p"],
            bh_significant=row["bh_significant"],
        )
        for system, result, row in zip(kept_systems, kept_results, bh_rows)
    )

    return FinalistGradingResult(
        finalists=finalists,
        candidates_tested=beam_result.candidates_tested,
        finalists_graded=len(finalists),
    )
