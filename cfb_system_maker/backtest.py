from __future__ import annotations

import math
import random
from dataclasses import replace
from typing import Any

from cfb_system_maker.features import feature_ok
from cfb_system_maker.models import BacktestResult, BetDetail, GameRecord, SeasonRecord, SystemFilter, SystemStats


def run_backtest_summary(
    games: list[GameRecord],
    system: SystemFilter,
    *,
    stake: float = 1.0,
    american_odds: int = -110,
    feature_map: dict[int, dict[str, Any]] | None = None,
) -> dict[str, float | int]:
    """Match + grade only — Record / Money Won / ROI chips without stats or grade."""
    feature_map = feature_map or {}
    matched = [game for game in games if matches_system(game, system, feature_map)]
    details = [
        grade_bet(game, system, stake=stake, american_odds=american_odds)
        for game in matched
    ]
    wins = sum(1 for bet in details if bet.result == "win")
    losses = sum(1 for bet in details if bet.result == "loss")
    pushes = sum(1 for bet in details if bet.result == "push")
    bets = len(details)
    decided = wins + losses
    profit = round(sum(bet.profit for bet in details), 4)
    risked = bets * stake
    hit_rate = round(wins / decided, 4) if decided else 0.0
    roi = round(profit / risked, 4) if risked else 0.0
    return {
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "hit_rate": hit_rate,
        "profit": profit,
        "money_won": profit * 100,
        "roi": roi,
    }


def run_backtest(
    games: list[GameRecord],
    system: SystemFilter,
    *,
    stake: float = 1.0,
    american_odds: int = -110,
    feature_map: dict[int, dict[str, Any]] | None = None,
) -> BacktestResult:
    feature_map = feature_map or {}
    matched = [game for game in games if matches_system(game, system, feature_map)]
    details = [
        grade_bet(game, system, stake=stake, american_odds=american_odds)
        for game in matched
    ]
    wins = sum(1 for bet in details if bet.result == "win")
    losses = sum(1 for bet in details if bet.result == "loss")
    pushes = sum(1 for bet in details if bet.result == "push")
    bets = len(details)
    decided = wins + losses
    profit = round(sum(bet.profit for bet in details), 4)
    risked = bets * stake
    average_line = round(sum(bet.line for bet in details) / bets, 4) if bets else None
    hit_rate = round(wins / decided, 4) if decided else 0.0
    roi = round(profit / risked, 4) if risked else 0.0

    result = BacktestResult(
        bets=bets,
        wins=wins,
        losses=losses,
        pushes=pushes,
        hit_rate=hit_rate,
        profit=profit,
        roi=roi,
        average_line=average_line,
        average_stake=stake,
        bet_details=details,
        stats=compute_system_stats(details, hit_rate=hit_rate, roi=roi, american_odds=american_odds, stake=stake),
        season_breakdown=tuple(compute_season_breakdown(details, stake=stake)),
        average_margin=(round(sum(bet.margin for bet in details) / bets, 4) if bets and system.bet_type == "spread" else None),
    )
    result = replace(result, grade=compute_grade(result, system))
    if result.stats is not None:
        result = replace(
            result,
            verdict=stats_verdict(result.stats, result.wins + result.losses, count_overfit_filters(system)),
        )
    return result


def split_holdout(
    system: SystemFilter,
    holdout_seasons: set[int],
    available_seasons: set[int],
) -> tuple[SystemFilter, SystemFilter]:
    base_seasons = system.seasons if system.seasons else available_seasons
    in_sample_seasons = base_seasons - holdout_seasons
    holdout_only_seasons = base_seasons & holdout_seasons
    # empty means "no restriction" in matches_system; use a sentinel so an
    # empty split yields zero bets, not everything.
    if not in_sample_seasons:
        in_sample_seasons = {-1}
    if not holdout_only_seasons:
        holdout_only_seasons = {-1}
    return replace(system, seasons=in_sample_seasons), replace(system, seasons=holdout_only_seasons)


def compute_season_breakdown(details: list[BetDetail], *, stake: float = 1.0) -> list[SeasonRecord]:
    by_season: dict[int, list[BetDetail]] = {}
    for bet in details:
        by_season.setdefault(bet.season, []).append(bet)

    records = []
    for season in sorted(by_season):
        bets = by_season[season]
        wins = sum(1 for bet in bets if bet.result == "win")
        losses = sum(1 for bet in bets if bet.result == "loss")
        pushes = sum(1 for bet in bets if bet.result == "push")
        profit = round(sum(bet.profit for bet in bets), 4)
        risked = len(bets) * stake
        roi = round(profit / risked, 4) if risked else 0.0
        records.append(
            SeasonRecord(
                season=season, bets=len(bets), wins=wins, losses=losses,
                pushes=pushes, profit=profit, roi=roi,
            )
        )
    return records


def sign_consistency(records: list[SeasonRecord]) -> tuple[int, int]:
    profitable = sum(1 for record in records if record.roi > 0)
    return profitable, len(records)


_GRADE_BANDS: tuple[tuple[float, str], ...] = (
    (0.85, "A"),
    (0.70, "B"),
    (0.55, "C"),
    (0.35, "D"),
    (0.00, "F"),
)


def _sample_size_score(decided: int, wilson_low: float, break_even_rate: float) -> float:
    if decided < 30:
        return 0.0
    margin = wilson_low - break_even_rate
    if margin < 0.0:
        return 0.0
    if margin < 0.02:
        return 0.3
    if margin < 0.05:
        return 0.6
    if margin < 0.10:
        return 0.8
    return 1.0


def _roi_significance_score(z_score: float) -> float:
    if z_score < 0:
        return 0.0
    if z_score < 1.0:
        return 0.2
    if z_score < 1.645:
        return 0.5
    if z_score < 1.96:
        return 0.75
    return 1.0


def _consistency_score(profitable: int, total_seasons: int) -> float:
    if total_seasons == 0:
        return 0.0
    return profitable / total_seasons


def _permutation_score(p_value: float) -> float:
    if p_value < 0.01:
        return 1.0
    if p_value < 0.05:
        return 0.8
    if p_value < 0.10:
        return 0.5
    if p_value < 0.20:
        return 0.25
    return 0.0


def _overfit_score(active_filter_value_count: int) -> float:
    if active_filter_value_count <= 3:
        return 1.0
    if active_filter_value_count <= 7:
        return 0.75
    if active_filter_value_count <= 14:
        return 0.5
    if active_filter_value_count <= 24:
        return 0.25
    return 0.0


def count_overfit_filters(system: SystemFilter) -> int:
    count = 0
    for flag in (system.favorite, system.underdog, system.home, system.away):
        if flag:
            count += 1
    for bound in (system.min_spread, system.max_spread, system.min_total, system.max_total):
        if bound is not None:
            count += 1
    if system.providers:
        count += 1
    for values in (system.teams, system.conferences, system.seasons, system.weeks):
        count += len(values)
    for filt in system.feature_filters:
        if filt.op == "in" and isinstance(filt.value, (list, tuple, set)):
            count += len(filt.value)
        else:
            count += 1
    return count


def stats_verdict(stats: SystemStats, decided: int, overfit_filters: int = 0) -> str:
    """Plain-English read of the significance panel, derived from the same
    fields compute_grade scores — not a second opinion, just a translation.

    overfit_filters (from count_overfit_filters) gates the "real signal" claim
    only -- NOT routed into compute_grade's composite (that would double-count
    the same signal _overfit_score already scores there). A system carved down
    by many active constraints (manual typing, a loaded save, or the Max ROI
    button all produce the same shape) is one candidate out of an unknown
    number the user or the search implicitly tried; its p-value is uncorrected
    for that search regardless of how the bounds were set, so significance
    here can't be read at face value.
    """
    if decided == 0:
        return "No decided bets yet."
    edge_pct = stats.edge * 100
    if stats.low_sample:
        return (
            f"Only {decided} decided bets — too few to say anything about edge. "
            "Treat this as a hypothesis, not a result."
        )
    # p_value and permutation_p_value are both ONE-SIDED upper-tail (see
    # _hit_rate_z_test) -- they can only ever detect a winning system, never a
    # losing one. That sidedness is load-bearing for bh_correct upstream, so it
    # is reconciled here rather than changed at the source.
    significant = stats.p_value < 0.05 and stats.permutation_p_value < 0.05
    # Wilson is two-sided (z=1.96), so it is NOT the dual of those tests and
    # routinely still contains break-even when they fire. Report it as its own
    # check instead of asserting it follows from significance.
    break_even_in_ci = stats.wilson_low <= stats.break_even_rate <= stats.wilson_high
    mde_note = f" This sample could only reliably detect an edge of {stats.mde * 100:.2f} points or more." if stats.mde is not None else ""
    cluster_note = ""
    if stats.cluster_low is not None and stats.cluster_high is not None:
        if stats.cluster_count < 40:
            cluster_note = (
                f" Bets cluster into only {stats.cluster_count} season/week groups (<40) — "
                "the cluster-robust ROI interval below is anti-conservative and likely too narrow; "
                "read it as directional, not exact."
            )
        else:
            cluster_note = (
                f" Accounting for {stats.cluster_count} season/week clusters (ICC={stats.icc:.3f}), "
                f"the cluster-robust ROI 95% CI is [{stats.cluster_low * 100:+.2f}%, {stats.cluster_high * 100:+.2f}%]."
            )
    if significant and edge_pct > 0:
        if overfit_filters > 7:
            return (
                f"Edge of {edge_pct:+.2f}% clears both significance tests (p={stats.p_value:.4f}, "
                f"permutation p={stats.permutation_p_value:.4f}), but this system has {overfit_filters} "
                "active narrowing constraints. A tight filter set is one candidate out of many that could "
                "have been tried, and this p-value isn't corrected for that search — treat it as "
                "hypothesis-generating, not confirmed, until it holds on a fresh season."
                + cluster_note
            )
        wilson_note = (
            " The two-sided Wilson interval still spans break-even, so the two views disagree — "
            "read the edge as suggestive rather than established."
            if break_even_in_ci
            else " Break-even sits outside the Wilson interval too — this looks like real signal, not noise."
        )
        return (
            f"Edge of {edge_pct:+.2f}% clears both the normal-theory (p={stats.p_value:.4f}) "
            f"and permutation (p={stats.permutation_p_value:.4f}) tests."
            + wilson_note
            + cluster_note
        )
    if edge_pct < 0:
        # The significance tests are one-sided upper-tail, so they can never
        # flag a losing system -- say so plainly instead of implying the
        # absence of a signal here means the same thing it does above.
        return (
            f"Edge of {edge_pct:+.2f}% is negative — this system lost money over the sample. "
            "The significance tests only look for a winning edge, so they cannot confirm a "
            "losing one; judge this on the size of the loss, not on the p-value."
            + cluster_note
        )
    return (
        f"Edge of {edge_pct:+.2f}% is not statistically distinguishable from break-even "
        f"(p={stats.p_value:.4f}, permutation p={stats.permutation_p_value:.4f}). "
        "Consistent with random variation around zero edge."
        + mde_note
        + cluster_note
    )


def compute_grade(result: BacktestResult, system: SystemFilter) -> str | None:
    if result.bets == 0:
        return None
    decided = result.wins + result.losses
    stats = result.stats
    profitable, total_seasons = sign_consistency(result.season_breakdown)
    scores = [
        _sample_size_score(decided, stats.wilson_low, stats.break_even_rate),
        _roi_significance_score(stats.z_score),
        _consistency_score(profitable, total_seasons),
        _permutation_score(stats.permutation_p_value),
        _overfit_score(count_overfit_filters(system)),
    ]
    average = sum(scores) / len(scores)
    for threshold, letter in _GRADE_BANDS:
        if average >= threshold:
            return letter
    return "F"


def matches_system(
    game: GameRecord,
    system: SystemFilter,
    feature_map: dict[int, dict[str, Any]] | None = None,
    *,
    require_played: bool = True,
) -> bool:
    # require_played=False lets Current Matches evaluate unplayed games (D-18).
    # Matching only — nothing below reads scores, and grade_bet still refuses
    # a game with no result.
    if require_played and (game.home_points is None or game.away_points is None):
        return False
    if system.bet_type == "spread" and game.spread is None:
        return False
    if system.bet_type == "total" and game.total is None:
        return False

    side = system.side.lower()
    if system.bet_type not in {"spread", "total"}:
        raise ValueError("bet_type must be 'spread' or 'total'")
    if system.bet_type == "spread" and side not in {"home", "away"}:
        raise ValueError("system side must be 'home' or 'away'")
    if system.bet_type == "total" and system.total_side not in {"over", "under"}:
        raise ValueError("total_side must be 'over' or 'under'")

    team = game.home_team if side == "home" else game.away_team
    conference = game.home_conference if side == "home" else game.away_conference
    side_spread = _side_spread(game.spread, side) if game.spread is not None else None

    if system.seasons and game.season not in system.seasons:
        return False
    if system.weeks and game.week not in system.weeks:
        return False
    if system.providers and game.provider not in system.providers:
        return False
    if system.teams and team not in system.teams:
        return False
    if system.conferences and conference not in system.conferences:
        return False
    if system.home and side != "home":
        return False
    if system.away and side != "away":
        return False
    if system.bet_type == "total":
        if system.min_total is not None and game.total is not None and game.total < system.min_total:
            return False
        if system.max_total is not None and game.total is not None and game.total > system.max_total:
            return False
    else:
        if side_spread is None:
            return False
        if system.favorite and side_spread >= 0:
            return False
        if system.underdog and side_spread <= 0:
            return False
        if system.min_spread is not None and side_spread < system.min_spread:
            return False
        if system.max_spread is not None and side_spread > system.max_spread:
            return False
        if system.min_total is not None and (game.total is None or game.total < system.min_total):
            return False
        if system.max_total is not None and (game.total is None or game.total > system.max_total):
            return False

    features = (feature_map or {}).get(game.game_id, {})
    return all(feature_ok(features, filt, system) for filt in system.feature_filters)


def compute_system_stats(
    details: list[BetDetail],
    *,
    hit_rate: float,
    roi: float,
    american_odds: int,
    stake: float,
    iterations: int = 1000,
    seed: int = 42,
) -> SystemStats:
    decided = sum(1 for bet in details if bet.result in {"win", "loss"})
    break_even_rate = _break_even_rate(american_odds)
    edge = round(hit_rate - break_even_rate, 4)
    wilson_low, wilson_high = _wilson_interval(hit_rate, decided)
    z_score, p_value = _hit_rate_z_test(hit_rate, decided, break_even_rate)
    returns = [bet.profit / stake for bet in details if bet.result in {"win", "loss"}]
    roi_std_error, roi_t_stat = _roi_stats(returns, roi)
    max_win_streak, max_loss_streak = _streaks(sorted(details, key=lambda bet: (bet.season, bet.week, bet.game_id)))
    permutation_p_value = _permutation_p_value(details, american_odds=american_odds, stake=stake, iterations=iterations, seed=seed)
    cluster_stats = cluster_dependence_stats(details, stake=stake, iterations=iterations, seed=seed)
    deff = decided / cluster_stats["effective_n"] if cluster_stats["effective_n"] else 1.0
    mde = _mde(decided, break_even_rate, deff=deff)

    return SystemStats(
        break_even_rate=round(break_even_rate, 4),
        edge=edge,
        wilson_low=wilson_low,
        wilson_high=wilson_high,
        z_score=z_score,
        p_value=p_value,
        roi_std_error=roi_std_error,
        roi_t_stat=roi_t_stat,
        low_sample=decided < 30,
        max_win_streak=max_win_streak,
        max_loss_streak=max_loss_streak,
        permutation_p_value=permutation_p_value,
        mde=mde,
        cluster_count=cluster_stats["cluster_count"],
        cluster_low=cluster_stats["cluster_low"],
        cluster_high=cluster_stats["cluster_high"],
        effective_n=cluster_stats["effective_n"],
        icc=cluster_stats["icc"],
    )


def grade_bet(
    game: GameRecord,
    system: SystemFilter | str,
    *,
    stake: float = 1.0,
    american_odds: int = -110,
) -> BetDetail:
    if isinstance(system, str):
        system = SystemFilter(side=system)
    normalized_side = system.side.lower()
    if system.fade:
        normalized_side = "away" if normalized_side == "home" else "home"
    if game.home_points is None or game.away_points is None:
        raise ValueError("game must have spread and final score")
    if system.bet_type == "total":
        return _grade_total_bet(game, system, stake=stake, american_odds=american_odds)
    if game.spread is None:
        raise ValueError("game must have spread and final score")

    if normalized_side == "home":
        team = game.home_team
        opponent = game.away_team
        team_points = game.home_points
        opponent_points = game.away_points
    elif normalized_side == "away":
        team = game.away_team
        opponent = game.home_team
        team_points = game.away_points
        opponent_points = game.home_points
    else:
        raise ValueError("side must be 'home' or 'away'")

    spread = _side_spread(game.spread, normalized_side)
    cover_margin = team_points + spread - opponent_points
    if cover_margin > 0:
        result = "win"
        profit = _profit_for_win(stake, american_odds)
    elif cover_margin < 0:
        result = "loss"
        profit = -stake
    else:
        result = "push"
        profit = 0.0

    return BetDetail(
        game_id=game.game_id,
        season=game.season,
        week=game.week,
        team=team,
        opponent=opponent,
        side=normalized_side,
        spread=spread,
        total=game.total,
        line=spread,
        result=result,
        profit=round(profit, 4),
        margin=round(cover_margin, 4),
    )


def _grade_total_bet(
    game: GameRecord,
    system: SystemFilter,
    *,
    stake: float,
    american_odds: int,
) -> BetDetail:
    if game.total is None or game.home_points is None or game.away_points is None:
        raise ValueError("game must have total and final score")

    points = game.home_points + game.away_points
    if points > game.total:
        winner = "over"
    elif points < game.total:
        winner = "under"
    else:
        winner = "push"

    effective_total_side = system.total_side
    if system.fade:
        effective_total_side = "under" if effective_total_side == "over" else "over"

    if winner == "push":
        result = "push"
        profit = 0.0
    elif winner == effective_total_side:
        result = "win"
        profit = _profit_for_win(stake, american_odds)
    else:
        result = "loss"
        profit = -stake

    return BetDetail(
        game_id=game.game_id,
        season=game.season,
        week=game.week,
        team=effective_total_side.title(),
        opponent=f"{game.away_team} at {game.home_team}",
        side=effective_total_side,
        spread=0.0,
        total=game.total,
        line=game.total,
        result=result,
        profit=round(profit, 4),
    )


def _break_even_rate(american_odds: int) -> float:
    if american_odds < 0:
        return abs(american_odds) / (abs(american_odds) + 100)
    return 100 / (american_odds + 100)


def _wilson_interval(hit_rate: float, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = hit_rate
    denom = 1 + z * z / n
    center = p + z * z / (2 * n)
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n)
    low = (center - margin) / denom
    high = (center + margin) / denom
    return round(max(0.0, low), 4), round(min(1.0, high), 4)


def _hit_rate_z_test(hit_rate: float, n: int, break_even_rate: float) -> tuple[float, float]:
    if n == 0:
        return 0.0, 1.0
    denom = math.sqrt(break_even_rate * (1 - break_even_rate) / n)
    if denom == 0:
        return 0.0, 1.0
    z_score = (hit_rate - break_even_rate) / denom
    p_value = 1 - _norm_cdf(z_score)
    return round(z_score, 4), round(p_value, 4)


def _analytic_p_value(wins: int, decided: int, break_even_rate: float) -> float:
    """One-sided analytic p-value from summary counts alone (no BetDetail list required).

    This is the SAME math as _hit_rate_z_test's p-value component, extracted so
    it is callable from run_backtest_summary's dict output (wins/decided counts)
    without constructing full BetDetail objects — needed by MVP-004's holdout
    finalist grading. hit_rate is rounded identically to how run_backtest and
    run_backtest_summary already round it (round(wins/decided, 4)) so results
    agree with SystemStats.p_value bit-for-bit at the same decided-bet counts.

    This is the multiple-testing-correction INPUT (paired with bh_correct below).
    It is NOT the permutation p-value (_permutation_p_value) — that is a
    separate descriptive stat computed from resampling BetDetail results and
    must not be fed into bh_correct.
    """
    if decided == 0:
        return 1.0
    hit_rate = round(wins / decided, 4)
    _, p_value = _hit_rate_z_test(hit_rate, decided, break_even_rate)
    return p_value


def bh_correct(p_values: list[float], alpha: float = 0.05) -> list[dict]:
    """Benjamini-Hochberg step-up correction over a fixed batch of p-values.

    K = len(p_values) is the number of finalists actually graded and passed
    into THIS call (MVP-004's holdout finalist batch) -- NOT candidates_tested
    (the much larger N of candidates the search considered, which is
    provenance-only and never enters this function). Conflating those two
    counts is an easy off-by-concept error; K here must always be the batch
    size of p-values actually supplied.

    Returns one dict per input p-value, in the ORIGINAL input order/identity,
    each with:
      - raw_p: the input p-value, unchanged
      - corrected_p: the BH-adjusted p-value (q-value), clamped to [0, 1]
      - bh_significant: True if corrected_p <= alpha

    Algorithm (step-up / reverse-cumulative-min form):
      1. Sort ascending, remembering original indices.
      2. For rank i (1-indexed) of K, compute candidate_i = p_(i) * K / i.
      3. Walk from the largest rank down to the smallest, taking a running
         minimum of candidate values -- this both guarantees the adjusted
         p-values are monotonic after the original order is restored, and
         (as a side effect) assigns tied raw p-values the identical
         corrected_p, satisfying the standard BH tie convention.
      4. Clamp each result to [0, 1].
      5. Restore original input order before returning.

    This function must never be called from compute_grade or any path
    feeding the letter-grade composite -- it is a standalone capability,
    not a modification of grading.
    """
    k = len(p_values)
    if k == 0:
        return []

    indexed = sorted(range(k), key=lambda i: p_values[i])  # ascending by p-value, stable for ties
    corrected_sorted = [0.0] * k

    running_min = 1.0
    for rank in range(k, 0, -1):  # walk from largest rank down to 1
        idx = indexed[rank - 1]
        candidate = p_values[idx] * k / rank
        running_min = min(running_min, candidate)
        corrected_sorted[rank - 1] = min(1.0, max(0.0, running_min))

    corrected_by_original_index = [0.0] * k
    for rank in range(1, k + 1):
        idx = indexed[rank - 1]
        corrected_by_original_index[idx] = corrected_sorted[rank - 1]

    return [
        {
            "raw_p": p_values[i],
            "corrected_p": corrected_by_original_index[i],
            "bh_significant": corrected_by_original_index[i] <= alpha,
        }
        for i in range(k)
    ]


def _permutation_p_value(
    details: list[BetDetail],
    *,
    american_odds: int,
    stake: float,
    iterations: int = 1000,
    seed: int = 42,
) -> float:
    decided_bets = [bet for bet in details if bet.result in {"win", "loss"}]
    decided = len(decided_bets)
    if decided == 0:
        return 1.0

    observed_profit = sum(bet.profit for bet in decided_bets)
    risked = decided * stake
    observed_roi = observed_profit / risked

    break_even_rate = _break_even_rate(american_odds)
    win_profit = _profit_for_win(stake, american_odds)
    loss_profit = -stake

    rng = random.Random(seed)
    at_or_above = 0
    for _ in range(iterations):
        profit = sum(win_profit if rng.random() < break_even_rate else loss_profit for _ in range(decided))
        if profit / risked >= observed_roi:
            at_or_above += 1
    return round(at_or_above / iterations, 4)


def _roi_stats(returns: list[float], roi: float) -> tuple[float, float]:
    n = len(returns)
    if n == 0:
        return 0.0, 0.0
    mean = sum(returns) / n
    variance = sum((value - mean) ** 2 for value in returns) / n
    std_error = math.sqrt(variance / n) if variance > 0 else 0.0
    t_stat = roi / std_error if std_error else 0.0
    return round(std_error, 4), round(t_stat, 4)


def _mde(n: int, break_even_rate: float, *, alpha: float = 0.05, power: float = 0.80, deff: float = 1.0) -> float | None:
    """Minimum detectable edge (hit-rate points above break-even) this sample
    size could reliably distinguish from zero, two-sided at the given alpha/power.

    MDE = (z_(1-alpha/2) + z_(1-power)) * SE, SE from break-even variance
    (the null hypothesis variance, standard for a sample-size formula) inflated
    by sqrt(deff) for cluster dependence. Not defined for n=0.
    """
    if n <= 0:
        return None
    z_alpha = _inverse_norm_cdf(1 - alpha / 2)
    z_power = _inverse_norm_cdf(power)
    se = math.sqrt(break_even_rate * (1 - break_even_rate) / n) * math.sqrt(deff)
    return round((z_alpha + z_power) * se, 4)


def _inverse_norm_cdf(p: float) -> float:
    """Acklam's rational approximation to the standard normal quantile function.

    Only ever called here with the fixed values 0.975 and 0.80 (alpha/power
    are keyword defaults, not user input), so a compact closed-form beats
    pulling in scipy for two constants.
    """
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    p_low = 0.02425
    p_high = 1 - p_low
    if p < p_low:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
            ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    if p <= p_high:
        q = p - 0.5
        r = q * q
        return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
            (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)
    q = math.sqrt(-2 * math.log(1 - p))
    return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
        ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)


def _cluster_key(bet: BetDetail) -> tuple[int, int]:
    # (season, week) is the only dependence dimension populated for both bet
    # types -- BetDetail.team is a real team for spread bets but "Over"/"Under"
    # for total bets, so team-level clustering silently degenerates to 2
    # clusters there. Season/week captures shared market and weather shocks
    # instead and is always meaningful.
    return (bet.season, bet.week)


def cluster_dependence_stats(
    details: list[BetDetail],
    *,
    stake: float,
    iterations: int = 1000,
    seed: int = 42,
) -> dict[str, float | int | None]:
    """Cluster (block) bootstrap ROI CI + effective sample size, clustered by
    (season, week). Resamples whole clusters, never individual bets, per
    dependence.md's block-bootstrap pattern for non-regression estimators.

    Also reports the intraclass correlation of per-bet profit (ICC) and the
    resulting design effect (DEFF = 1 + (m-1)*ICC), so effective_n reflects
    measured dependence rather than an assumed value.
    """
    decided_bets = [bet for bet in details if bet.result in {"win", "loss"}]
    n = len(decided_bets)
    if n == 0:
        return {"cluster_count": 0, "cluster_low": None, "cluster_high": None, "effective_n": None, "icc": None}

    clusters: dict[tuple[int, int], list[float]] = {}
    for bet in decided_bets:
        clusters.setdefault(_cluster_key(bet), []).append(bet.profit)
    cluster_profits = list(clusters.values())
    cluster_sizes = [len(p) for p in cluster_profits]
    g = len(cluster_profits)

    icc = _icc_one_way(cluster_profits)
    mean_cluster_size = n / g
    deff = 1 + (mean_cluster_size - 1) * max(0.0, icc)
    effective_n = round(n / deff, 2) if deff > 0 else float(n)

    if g < 2:
        return {"cluster_count": g, "cluster_low": None, "cluster_high": None, "effective_n": effective_n, "icc": round(icc, 4)}

    rng = random.Random(seed)
    risked = n * stake
    roi_samples = []
    for _ in range(iterations):
        take = rng.choices(range(g), k=g)
        profit = sum(sum(cluster_profits[idx]) for idx in take)
        weight = sum(cluster_sizes[idx] for idx in take)
        if weight == 0:
            continue
        roi_samples.append(profit / (weight * stake))
    roi_samples.sort()
    if not roi_samples:
        return {"cluster_count": g, "cluster_low": None, "cluster_high": None, "effective_n": effective_n, "icc": round(icc, 4)}
    lo_idx = max(0, round(0.025 * len(roi_samples)) - 1)
    hi_idx = min(len(roi_samples) - 1, round(0.975 * len(roi_samples)) - 1)

    return {
        "cluster_count": g,
        "cluster_low": round(roi_samples[lo_idx], 4),
        "cluster_high": round(roi_samples[hi_idx], 4),
        "effective_n": effective_n,
        "icc": round(icc, 4),
    }


def _icc_one_way(cluster_profits: list[list[float]]) -> float:
    """One-way random-effects intraclass correlation from a cluster-means ANOVA
    decomposition: ICC = (MSB - MSW) / (MSB + (m0 - 1) * MSW), m0 the average
    cluster size adjusted for unequal group sizes (standard ANOVA ICC formula).
    Clamped to [0, 1] -- negative raw ICC means no detectable within-cluster
    correlation, which is a valid (and common) result, not an error.
    """
    all_values = [v for group in cluster_profits for v in group]
    n = len(all_values)
    g = len(cluster_profits)
    if g < 2 or n <= g:
        return 0.0
    grand_mean = sum(all_values) / n

    ssb = sum(len(group) * (sum(group) / len(group) - grand_mean) ** 2 for group in cluster_profits)
    ssw = sum((v - sum(group) / len(group)) ** 2 for group in cluster_profits for v in group)
    msb = ssb / (g - 1)
    msw = ssw / (n - g) if n > g else 0.0
    if msw == 0.0 and msb == 0.0:
        return 0.0

    sum_sq_sizes = sum(len(group) ** 2 for group in cluster_profits)
    m0 = (n - sum_sq_sizes / n) / (g - 1)
    if m0 <= 0:
        return 0.0

    denom = msb + (m0 - 1) * msw
    if denom == 0:
        return 0.0
    icc = (msb - msw) / denom
    return max(0.0, min(1.0, icc))


def _streaks(details: list[BetDetail]) -> tuple[int, int]:
    best_win = best_loss = win_run = loss_run = 0
    for bet in details:
        if bet.result == "win":
            win_run += 1
            loss_run = 0
        elif bet.result == "loss":
            loss_run += 1
            win_run = 0
        else:
            continue  # pushes neither extend nor break a streak
        best_win = max(best_win, win_run)
        best_loss = max(best_loss, loss_run)
    return best_win, best_loss


def _norm_cdf(z: float) -> float:
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def _side_spread(home_spread: float, side: str) -> float:
    return home_spread if side == "home" else -home_spread


def _profit_for_win(stake: float, american_odds: int) -> float:
    if american_odds < 0:
        return stake * 100 / abs(american_odds)
    return stake * american_odds / 100
