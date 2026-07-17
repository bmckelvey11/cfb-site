# System Validation: Signal vs. Noise Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every backtested system a trust verdict — per-season breakdown with sign-consistency, a Monte Carlo permutation p-value, and holdout (out-of-sample) evaluation — layered on the existing in-sample `SystemStats`.

**Architecture:** All three parts are pure functions added to `backtest.py` plus small frozen-dataclass additions to `models.py`. Per-season breakdown and the permutation test are computed automatically inside `run_backtest`/`compute_system_stats` (cheap, always-on). Holdout evaluation is opt-in plumbing: a `split_holdout` helper produces two `SystemFilter`s (in-sample / holdout-only), wired into the CLI (`--holdout-season`) and `/compare` (a `holdout_season` query param) — both call `run_backtest` twice and print/render the results side by side. No new registry fields, no new source data, no new dependencies.

**Tech Stack:** Python stdlib only (`random`, `math`, `dataclasses`) — per locked decision 5 (`SystemStats` pure stdlib). Flask + Jinja for the two template changes.

## Global Constraints

- Pure stdlib only — no numpy/scipy/pandas. (Locked decision 5.)
- `GameRecord`/`games.csv` stay frozen — this item touches no source data, no registry, no `features.json`. (Locked decision 2.)
- **Deferred, not part of this plan:** per the roadmap (`docs/superpowers/plans/2026-07-16-next-steps-roadmap.md`, item 2), once item 1 (multi-season data backbone) lands, rerun this item's per-season/holdout/permutation logic against real multi-season data and treat any mismatch vs. the synthetic-data test behavior as blocking. That reconciliation is a manual step to perform later, not a task below.

---

## Task 1: Per-season breakdown + sign consistency

**Files:**
- Modify: `cfb_system_maker/models.py:81-94` (add `SeasonRecord`, add `season_breakdown` field to `BacktestResult`)
- Modify: `cfb_system_maker/backtest.py` (add `compute_season_breakdown`, `sign_consistency`; wire into `run_backtest`)
- Modify: `cfb_system_maker/cli.py` (surface per-season breakdown in `print_result`)
- Test: `tests/test_backtest.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Produces: `models.SeasonRecord` frozen dataclass — `season: int, bets: int, wins: int, losses: int, pushes: int, profit: float, roi: float`.
- Produces: `backtest.compute_season_breakdown(details: list[BetDetail], *, stake: float = 1.0) -> list[SeasonRecord]` — groups by `bet.season`, sorted ascending.
- Produces: `backtest.sign_consistency(records: list[SeasonRecord]) -> tuple[int, int]` — `(profitable_season_count, total_season_count)`.
- Produces: `models.BacktestResult.season_breakdown: tuple[SeasonRecord, ...] = ()` — populated automatically by `run_backtest`.
- Consumes (Task 2/3/4/5 build on these): the two functions above and the new field.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_backtest.py`:

```python
def test_season_breakdown_groups_bets_by_season_with_roi():
    season_2022_bet = BetDetail(
        game_id=3, season=2022, week=3, team="Alpha", opponent="Beta",
        side="home", spread=-3.0, total=None, line=-3.0, result="win", profit=0.9091,
    )
    details = [
        _bet(1, 1, "win"),
        _bet(2, 2, "loss"),
        season_2022_bet,
    ]

    records = compute_season_breakdown(details)

    assert [r.season for r in records] == [2022, 2023]
    season_2023 = next(r for r in records if r.season == 2023)
    assert season_2023.bets == 2
    assert season_2023.wins == 1
    assert season_2023.losses == 1
    expected_profit = round(0.9091 - 1.0, 4)
    assert season_2023.profit == expected_profit
    assert season_2023.roi == round(expected_profit / 2, 4)


def test_season_breakdown_computes_roi_per_season():
    details = [_bet(1, 1, "win"), _bet(2, 2, "win"), _bet(3, 3, "loss")]

    records = compute_season_breakdown(details, stake=1.0)

    assert len(records) == 1
    record = records[0]
    assert record.season == 2023
    assert record.bets == 3
    assert record.wins == 2
    assert record.losses == 1
    assert record.profit == round(0.9091 + 0.9091 - 1.0, 4)
    assert record.roi == round(record.profit / 3, 4)


def test_sign_consistency_counts_profitable_and_total_seasons():
    records = [
        SeasonRecord(season=2021, bets=10, wins=6, losses=4, pushes=0, profit=1.0, roi=0.1),
        SeasonRecord(season=2022, bets=10, wins=4, losses=6, pushes=0, profit=-1.0, roi=-0.1),
        SeasonRecord(season=2023, bets=10, wins=7, losses=3, pushes=0, profit=2.0, roi=0.2),
    ]

    profitable, total = sign_consistency(records)

    assert profitable == 2
    assert total == 3


def test_run_backtest_populates_season_breakdown():
    games = [
        GameRecord(1, 2022, 1, "A", "B", "ACC", "SEC", 28, 21, "consensus", -6.5, 49.5),
        GameRecord(2, 2023, 1, "A", "C", "ACC", "SEC", 30, 14, "consensus", -6.5, 49.5),
    ]

    result = run_backtest(games, SystemFilter(side="home", favorite=True))

    assert [r.season for r in result.season_breakdown] == [2022, 2023]
    assert all(r.bets == 1 for r in result.season_breakdown)
```

Update the top-of-file import to pull in the new symbols:

```python
from cfb_system_maker.backtest import compute_season_breakdown, compute_system_stats, run_backtest, sign_consistency
from cfb_system_maker.models import BetDetail, FeatureFilter, GameRecord, SeasonRecord, SystemFilter
```

Append to `tests/test_cli.py`:

```python
def test_backtest_command_prints_per_season_breakdown(tmp_path, capsys):
    assert main(["sample", "--data-dir", str(tmp_path)]) == 0

    exit_code = main(["backtest", "--data-dir", str(tmp_path), "--side", "home", "--favorite"])

    captured = capsys.readouterr().out
    assert exit_code == 0
    assert "Per-season breakdown:" in captured
    assert "Profitable in" in captured
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_backtest.py tests/test_cli.py -v`
Expected: FAIL/ERROR — `ImportError: cannot import name 'compute_season_breakdown'` (and `SeasonRecord`).

- [ ] **Step 3: Implement `SeasonRecord` and wire `BacktestResult.season_breakdown`**

In `cfb_system_maker/models.py`, insert a new dataclass immediately before `BacktestResult` (currently at line 81) and add a field to `BacktestResult`:

```python
@dataclass(frozen=True)
class SeasonRecord:
    season: int
    bets: int
    wins: int
    losses: int
    pushes: int
    profit: float
    roi: float


@dataclass(frozen=True)
class BacktestResult:
    bets: int
    wins: int
    losses: int
    pushes: int
    hit_rate: float
    profit: float
    roi: float
    average_line: float | None
    average_stake: float
    bet_details: list[BetDetail]
    stats: SystemStats | None = None
    season_breakdown: tuple[SeasonRecord, ...] = ()
```

- [ ] **Step 4: Implement `compute_season_breakdown` and `sign_consistency`, wire into `run_backtest`**

In `cfb_system_maker/backtest.py`, update the import line:

```python
from cfb_system_maker.models import BacktestResult, BetDetail, GameRecord, SeasonRecord, SystemFilter, SystemStats
```

Add these two functions (place after `run_backtest`, before `matches_system`):

```python
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
```

Update `run_backtest`'s return statement to populate the new field:

```python
    return BacktestResult(
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
    )
```

- [ ] **Step 5: Surface per-season breakdown in CLI `print_result`**

In `cfb_system_maker/cli.py`, update the import line:

```python
from cfb_system_maker.backtest import run_backtest, sign_consistency
```

In `print_result`, insert this block after the `Average line` print and before the `if result.stats:` block:

```python
    if result.season_breakdown:
        print("Per-season breakdown:")
        for record in result.season_breakdown:
            print(f"  {record.season}: {record.wins}-{record.losses}-{record.pushes}  ROI {record.roi:.2%}")
        profitable, total = sign_consistency(result.season_breakdown)
        print(f"Profitable in {profitable}/{total} seasons")
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_backtest.py tests/test_cli.py -v`
Expected: PASS (all tests, including previously-passing ones).

- [ ] **Step 7: Commit**

```bash
git add cfb_system_maker/models.py cfb_system_maker/backtest.py cfb_system_maker/cli.py tests/test_backtest.py tests/test_cli.py
git commit -m "feat: add per-season backtest breakdown with sign consistency"
```

---

## Task 2: Permutation test (Monte Carlo p-value)

**Files:**
- Modify: `cfb_system_maker/models.py` (add `permutation_p_value` field to `SystemStats`)
- Modify: `cfb_system_maker/backtest.py` (add `_permutation_p_value`; wire into `compute_system_stats`)
- Modify: `cfb_system_maker/cli.py` (surface permutation p-value in `print_result`)
- Test: `tests/test_backtest.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `models.SeasonRecord`/`BacktestResult.season_breakdown` unused here; consumes `BetDetail.result`/`BetDetail.profit` (existing), `backtest._break_even_rate`, `backtest._profit_for_win` (existing private helpers, same module).
- Produces: `models.SystemStats.permutation_p_value: float = 1.0`.
- Produces (private): `backtest._permutation_p_value(details: list[BetDetail], *, american_odds: int, stake: float, iterations: int = 1000, seed: int = 42) -> float`.
- `compute_system_stats` gains keyword-only params `iterations: int = 1000, seed: int = 42` (defaults preserve existing call sites).

**Design note (resampling convention):** the permutation test resamples only *decided* bets (wins/losses) at the break-even win probability — pushes carry no stake risk in the noise model, so they're excluded from both `n` and the risked-stake denominator. This means the permutation test's "observed ROI" is computed fresh from decided bets only, not reused from the headline `roi` param (which dilutes by including pushes in its denominator) — comparing decided-only observed ROI against decided-only simulated ROI keeps the comparison apples-to-apples.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_backtest.py` (reuses the existing `_bet(game_id, week, result)` helper already defined in this file, which fixes `season=2023` and `-110` odds profit):

```python
def _bets(win_count, loss_count):
    bets = []
    game_id = 1
    for _ in range(win_count):
        bets.append(_bet(game_id, game_id, "win"))
        game_id += 1
    for _ in range(loss_count):
        bets.append(_bet(game_id, game_id, "loss"))
        game_id += 1
    return bets


def test_permutation_test_flags_injected_edge_as_low_p_value():
    details = _bets(130, 70)  # 65% hit rate vs. 52.38% break-even at -110

    stats = compute_system_stats(details, hit_rate=0.65, roi=0.1815, american_odds=-110, stake=1.0)

    assert stats.permutation_p_value < 0.05


def test_permutation_test_flags_noise_dataset_as_high_p_value():
    details = _bets(262, 238)  # ~52.4% hit rate, essentially at break-even -> no edge

    stats = compute_system_stats(details, hit_rate=0.524, roi=0.0, american_odds=-110, stake=1.0)

    assert stats.permutation_p_value > 0.2


def test_permutation_test_excludes_pushes_from_resampling():
    edge = _bets(130, 70)
    with_pushes = edge + [_bet(9001, 9001, "push"), _bet(9002, 9002, "push")]

    stats_edge = compute_system_stats(edge, hit_rate=0.65, roi=0.1815, american_odds=-110, stake=1.0)
    stats_with_pushes = compute_system_stats(with_pushes, hit_rate=0.65, roi=0.1815, american_odds=-110, stake=1.0)

    assert stats_with_pushes.permutation_p_value == stats_edge.permutation_p_value


def test_permutation_test_is_reproducible_with_fixed_seed():
    details = _bets(130, 70)

    first = compute_system_stats(details, hit_rate=0.65, roi=0.1815, american_odds=-110, stake=1.0)
    second = compute_system_stats(details, hit_rate=0.65, roi=0.1815, american_odds=-110, stake=1.0)

    assert first.permutation_p_value == second.permutation_p_value


def test_permutation_test_defaults_to_no_signal_with_zero_decided_bets():
    stats = compute_system_stats([], hit_rate=0.0, roi=0.0, american_odds=-110, stake=1.0)

    assert stats.permutation_p_value == 1.0
```

Append to `tests/test_cli.py`:

```python
def test_backtest_command_prints_permutation_p_value(tmp_path, capsys):
    assert main(["sample", "--data-dir", str(tmp_path)]) == 0

    exit_code = main(["backtest", "--data-dir", str(tmp_path), "--side", "home", "--favorite"])

    captured = capsys.readouterr().out
    assert exit_code == 0
    assert "Permutation p-value:" in captured
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_backtest.py tests/test_cli.py -v`
Expected: FAIL — `AttributeError: 'SystemStats' object has no attribute 'permutation_p_value'`.

- [ ] **Step 3: Add the field to `SystemStats`**

In `cfb_system_maker/models.py`, update `SystemStats`:

```python
@dataclass(frozen=True)
class SystemStats:
    break_even_rate: float
    edge: float
    wilson_low: float
    wilson_high: float
    z_score: float
    p_value: float
    roi_std_error: float
    roi_t_stat: float
    low_sample: bool
    max_win_streak: int = 0
    max_loss_streak: int = 0
    permutation_p_value: float = 1.0
```

- [ ] **Step 4: Implement `_permutation_p_value` and wire into `compute_system_stats`**

In `cfb_system_maker/backtest.py`, add `import random` alongside the existing `import math` at the top of the file:

```python
import math
import random
from typing import Any
```

Add the private helper (place near the other private helpers, e.g. after `_hit_rate_z_test`):

```python
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
```

Update `compute_system_stats`'s signature and body:

```python
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
    )
```

- [ ] **Step 5: Surface permutation p-value in CLI `print_result`**

In `cfb_system_maker/cli.py`, in the `if result.stats:` block, insert a line after `p-value`:

```python
        print(f"p-value: {stats.p_value:.4f}")
        print(f"Permutation p-value: {stats.permutation_p_value:.4f}")
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_backtest.py tests/test_cli.py -v`
Expected: PASS (all tests).

- [ ] **Step 7: Commit**

```bash
git add cfb_system_maker/models.py cfb_system_maker/backtest.py cfb_system_maker/cli.py tests/test_backtest.py tests/test_cli.py
git commit -m "feat: add Monte Carlo permutation p-value to system stats"
```

---

## Task 3: Holdout evaluation (`split_holdout` + CLI `--holdout-season`)

**Files:**
- Modify: `cfb_system_maker/backtest.py` (add `split_holdout`)
- Modify: `cfb_system_maker/cli.py` (add `--holdout-season` flag, wire into `_backtest`)
- Test: `tests/test_backtest.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `models.SystemFilter` (existing, unchanged shape).
- Produces: `backtest.split_holdout(system: SystemFilter, holdout_seasons: set[int], available_seasons: set[int]) -> tuple[SystemFilter, SystemFilter]` — returns `(in_sample_system, holdout_system)`.

**Correctness note:** `matches_system` treats `SystemFilter.seasons == set()` as "no restriction" (matches every season), not "match nothing." If a holdout split naively produced an empty seasons set — e.g. the requested holdout season isn't in the system's own season filter at all, or the holdout covers every season the system filters on — that empty set would silently mean "unrestricted" and the holdout/in-sample side would wrongly show *all* games instead of *zero*. `split_holdout` must use a sentinel season (`{-1}`, which never matches a real game) whenever a split would otherwise produce an empty set.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_backtest.py`. Update the import line first:

```python
from cfb_system_maker.backtest import compute_season_breakdown, compute_system_stats, run_backtest, sign_consistency, split_holdout
```

```python
def test_split_holdout_separates_in_sample_and_holdout_seasons():
    system = SystemFilter(side="home", seasons={2020, 2021, 2022, 2023})

    in_sample, holdout = split_holdout(system, {2023}, {2020, 2021, 2022, 2023})

    assert in_sample.seasons == {2020, 2021, 2022}
    assert holdout.seasons == {2023}


def test_split_holdout_uses_available_seasons_when_system_has_no_season_filter():
    system = SystemFilter(side="home")  # empty seasons = unrestricted

    in_sample, holdout = split_holdout(system, {2023}, {2020, 2021, 2022, 2023})

    assert in_sample.seasons == {2020, 2021, 2022}
    assert holdout.seasons == {2023}


def test_split_holdout_returns_sentinel_holdout_when_no_overlap_remains():
    system = SystemFilter(side="home", seasons={2023})

    in_sample, holdout = split_holdout(system, {2020}, {2020, 2021, 2022, 2023})

    # 2020 isn't in the system's own season set -> holdout side must match
    # nothing, not fall back to "no restriction" (empty set means unrestricted
    # in matches_system, so an empty result here must use the sentinel instead).
    assert holdout.seasons == {-1}
    assert in_sample.seasons == {2023}


def test_split_holdout_returns_sentinel_in_sample_when_holdout_covers_all_seasons():
    system = SystemFilter(side="home", seasons={2023})

    in_sample, holdout = split_holdout(system, {2023}, {2020, 2021, 2022, 2023})

    assert in_sample.seasons == {-1}
    assert holdout.seasons == {2023}
```

Append to `tests/test_cli.py`:

```python
def test_backtest_command_prints_holdout_columns_when_holdout_season_given(tmp_path, capsys):
    assert main(["sample", "--data-dir", str(tmp_path)]) == 0

    exit_code = main(
        [
            "backtest", "--data-dir", str(tmp_path),
            "--side", "home", "--favorite",
            "--holdout-season", "2023",
        ]
    )

    captured = capsys.readouterr().out
    assert exit_code == 0
    assert "Custom system (in-sample)" in captured
    assert "Custom system (holdout)" in captured
    assert captured.count("Bets:") == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_backtest.py tests/test_cli.py -v`
Expected: FAIL — `ImportError: cannot import name 'split_holdout'` and argparse `unrecognized arguments: --holdout-season`.

- [ ] **Step 3: Implement `split_holdout`**

In `cfb_system_maker/backtest.py`, update the import line to add `replace`:

```python
from dataclasses import replace
```

Add the function (place after `run_backtest`, alongside `compute_season_breakdown`/`sign_consistency`):

```python
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
```

- [ ] **Step 4: Wire `--holdout-season` into the CLI**

In `cfb_system_maker/cli.py`, update the import line:

```python
from cfb_system_maker.backtest import run_backtest, sign_consistency, split_holdout
```

In `_build_parser`, add the flag to the `backtest` subparser (after `backtest.add_argument("--load")`):

```python
    backtest.add_argument("--holdout-season", dest="holdout_seasons", type=int, action="append")
```

Replace the result-computation tail of `_backtest` (from `result = run_backtest(...)` through `print_result(label, result)`) with:

```python
    label = args.load or "Custom system"
    if args.holdout_seasons:
        available_seasons = {game.season for game in games}
        in_sample, holdout = split_holdout(system, set(args.holdout_seasons), available_seasons)
        in_result = run_backtest(games, in_sample, feature_map=feature_map)
        holdout_result = run_backtest(games, holdout, feature_map=feature_map)
        print_result(f"{label} (in-sample)", in_result)
        print_result(f"{label} (holdout)", holdout_result)
    else:
        result = run_backtest(games, system, feature_map=feature_map)
        print_result(label, result)
```

(The surrounding `feature_map` load and the trailing `if args.save:` block stay unchanged.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_backtest.py tests/test_cli.py -v`
Expected: PASS (all tests).

- [ ] **Step 6: Commit**

```bash
git add cfb_system_maker/backtest.py cfb_system_maker/cli.py tests/test_backtest.py tests/test_cli.py
git commit -m "feat: add holdout-season evaluation split and CLI flag"
```

---

## Task 4: Web index — per-season breakdown + permutation p display

**Files:**
- Modify: `cfb_system_maker/web.py:1-19,63-80` (import `sign_consistency`, pass `season_sign_consistency` to template)
- Modify: `cfb_system_maker/templates/index.html:234-244` (permutation p article + per-season table)
- Test: `tests/test_web.py`

**Interfaces:**
- Consumes: `backtest.sign_consistency` (Task 1), `result.season_breakdown` / `result.stats.permutation_p_value` (Tasks 1-2, already on `BacktestResult`/`SystemStats` by this point).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_web.py`:

```python
def test_web_index_shows_per_season_breakdown_and_permutation_p(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    app = create_app(data_dir=tmp_path)

    response = app.test_client().get("/?side=home&favorite=on")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Per-Season Breakdown" in html
    assert "Permutation p" in html
    assert "Profitable in" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_web.py::test_web_index_shows_per_season_breakdown_and_permutation_p -v`
Expected: FAIL — `assert "Per-Season Breakdown" in html` fails (string not present).

- [ ] **Step 3: Wire `sign_consistency` into the `/` route**

In `cfb_system_maker/web.py`, update the import line:

```python
from cfb_system_maker.backtest import matches_system, run_backtest, sign_consistency
```

In the `index()` view, add `season_sign_consistency` to the `render_template("index.html", ...)` call (after `coverage=coverage,`):

```python
            coverage=coverage,
            season_sign_consistency=sign_consistency(result.season_breakdown),
        )
```

- [ ] **Step 4: Add the template markup**

In `cfb_system_maker/templates/index.html`, insert a new article inside the existing `stats-panel` section (right after the `p-value` article):

```html
            <article><span>p-value</span><strong>{{ "%.4f"|format(result.stats.p_value) }}</strong></article>
            <article><span>Permutation p</span><strong>{{ "%.4f"|format(result.stats.permutation_p_value) }}</strong></article>
```

Then, immediately after the `stats-panel` section's closing `{% endif %}` (and before the `{% if coverage %}` block), add a new section:

```html
          {% if result.season_breakdown %}
          <section class="table-wrap season-breakdown" aria-label="Per-season breakdown">
            <h3>Per-Season Breakdown</h3>
            <p>Profitable in {{ season_sign_consistency[0] }}/{{ season_sign_consistency[1] }} seasons</p>
            <table>
              <thead><tr><th>Season</th><th>W-L-P</th><th>ROI</th></tr></thead>
              <tbody>
                {% for record in result.season_breakdown %}
                  <tr>
                    <td>{{ record.season }}</td>
                    <td>{{ record.wins }}-{{ record.losses }}-{{ record.pushes }}</td>
                    <td class="{{ 'positive' if record.roi > 0 else 'negative' if record.roi < 0 else '' }}">{{ "%.2f%%"|format(record.roi * 100) }}</td>
                  </tr>
                {% endfor %}
              </tbody>
            </table>
          </section>
          {% endif %}
```

(Reuses the existing `.table-wrap`/`table`/`.positive`/`.negative` CSS classes already defined in `static/styles.css` — no new stylesheet changes needed.)

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_web.py -v`
Expected: PASS (all tests, including the pre-existing ones).

- [ ] **Step 6: Commit**

```bash
git add cfb_system_maker/web.py cfb_system_maker/templates/index.html tests/test_web.py
git commit -m "feat: show per-season breakdown and permutation p-value in web UI"
```

---

## Task 5: Web /compare — holdout toggle + permutation/profitable-seasons rows

**Files:**
- Modify: `cfb_system_maker/web.py:1-19,91-114` (import `split_holdout`, rewrite `compare()`)
- Modify: `cfb_system_maker/templates/compare.html` (holdout season picker + two new table rows)
- Test: `tests/test_web_compare.py`

**Interfaces:**
- Consumes: `backtest.split_holdout` (Task 3), `backtest.sign_consistency` (Task 1, already imported into `web.py` by Task 4).
- Produces: each `rows[i]` dict gains a `"sign_consistency": tuple[int, int]` key; the `/compare` route accepts a repeatable `holdout_season` query param.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_web_compare.py`:

```python
def test_compare_shows_holdout_columns_when_holdout_season_selected(tmp_path):
    app = _setup(tmp_path)

    html = app.test_client().get("/compare?system=home-favs&holdout_season=2023").get_data(as_text=True)

    assert "home-favs (in-sample)" in html
    assert "home-favs (holdout)" in html


def test_compare_without_holdout_season_keeps_single_column_per_system(tmp_path):
    app = _setup(tmp_path)

    html = app.test_client().get("/compare?system=home-favs").get_data(as_text=True)

    assert "home-favs (in-sample)" not in html
    assert ">home-favs<" in html


def test_compare_shows_permutation_p_and_profitable_seasons_rows(tmp_path):
    app = _setup(tmp_path)

    html = app.test_client().get("/compare?system=home-favs&system=away-dogs").get_data(as_text=True)

    assert "Permutation p" in html
    assert "Profitable seasons" in html
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_web_compare.py -v`
Expected: FAIL — `assert "home-favs (in-sample)" in html` fails (holdout param currently ignored) and `assert "Permutation p" in html` fails (row not rendered).

- [ ] **Step 3: Rewrite the `/compare` route**

In `cfb_system_maker/web.py`, update the import line:

```python
from cfb_system_maker.backtest import matches_system, run_backtest, sign_consistency, split_holdout
```

Replace the entire `compare()` view with:

```python
    @app.get("/compare")
    def compare():
        try:
            games = load_processed_games(app.config["DATA_DIR"])
        except FileNotFoundError:
            return render_template(
                "compare.html",
                error="missing_data",
                rows=[],
                selected=[],
                saved_systems=[],
                options=_empty_options(),
                holdout_seasons=set(),
            )

        feature_map = _try_load_features(app.config["DATA_DIR"])
        selected = request.args.getlist("system")
        holdout_seasons = {int(value) for value in request.args.getlist("holdout_season") if value.strip()}
        available_seasons = {game.season for game in games}
        rows = []
        for name in selected:
            try:
                system = load_system(name, app.config["DATA_DIR"])
            except FileNotFoundError:
                continue
            if holdout_seasons:
                in_sample, holdout = split_holdout(system, holdout_seasons, available_seasons)
                in_result = run_backtest(games, in_sample, feature_map=feature_map)
                holdout_result = run_backtest(games, holdout, feature_map=feature_map)
                rows.append({
                    "name": f"{name} (in-sample)",
                    "system": in_sample,
                    "result": in_result,
                    "sign_consistency": sign_consistency(in_result.season_breakdown),
                })
                rows.append({
                    "name": f"{name} (holdout)",
                    "system": holdout,
                    "result": holdout_result,
                    "sign_consistency": sign_consistency(holdout_result.season_breakdown),
                })
            else:
                result = run_backtest(games, system, feature_map=feature_map)
                rows.append({
                    "name": name,
                    "system": system,
                    "result": result,
                    "sign_consistency": sign_consistency(result.season_breakdown),
                })
        return render_template(
            "compare.html",
            error=None,
            rows=rows,
            selected=selected,
            saved_systems=list_systems(app.config["DATA_DIR"]),
            options=_options_from_games(games),
            holdout_seasons=holdout_seasons,
        )
```

- [ ] **Step 4: Add the holdout picker and new rows to the template**

In `cfb_system_maker/templates/compare.html`, replace the `compare-picker` form's tail (from `{% if saved_systems %}<button type="submit">Compare</button>{% endif %}`) with:

```html
            {% if saved_systems %}
            <label>Holdout season(s)
              <select name="holdout_season" multiple size="4">
                {% for season in options.seasons %}
                  <option value="{{ season }}" {% if season in holdout_seasons %}selected{% endif %}>{{ season }}</option>
                {% endfor %}
              </select>
            </label>
            <button type="submit">Compare</button>
            {% endif %}
```

Add two rows to the `compare-table` `<tbody>`, right after the existing `Sample` row:

```html
                <tr><td>Sample</td>{% for row in rows %}<td>{{ "Low n" if row.result.stats.low_sample else "OK" }}</td>{% endfor %}</tr>
                <tr><td>Permutation p</td>{% for row in rows %}<td>{{ "%.4f"|format(row.result.stats.permutation_p_value) }}</td>{% endfor %}</tr>
                <tr><td>Profitable seasons</td>{% for row in rows %}<td>{{ row.sign_consistency[0] }}/{{ row.sign_consistency[1] }}</td>{% endfor %}</tr>
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_web_compare.py -v`
Expected: PASS (all tests, including the pre-existing ones).

- [ ] **Step 6: Run the full test suite**

Run: `python -m pytest`
Expected: PASS (all tests across the project — this is the last task in the plan, so this is the final regression check).

- [ ] **Step 7: Commit**

```bash
git add cfb_system_maker/web.py cfb_system_maker/templates/compare.html tests/test_web_compare.py
git commit -m "feat: add holdout evaluation toggle to /compare"
```

---

## Self-Review Notes

- **Spec coverage:** roadmap item 2's three parts — per-season breakdown (Task 1), permutation test (Task 2), holdout evaluation (Task 3 CLI + Task 5 web) — are each covered, plus the "web stats panel shows per-season table + permutation p" and "/compare shows in-sample vs holdout columns side by side" UI requirements (Tasks 4-5).
- **Data-model question resolved:** the roadmap review flagged "does `BacktestResult.bet_details` already carry a `season` field?" — confirmed yes (`models.py:69`), so no data-model change was needed for per-season grouping.
- **Correctness trap caught during planning:** a naive `split_holdout` could produce an empty `seasons` set, which `matches_system` interprets as "unrestricted" rather than "match nothing" — Task 3 uses a `{-1}` sentinel and has dedicated tests for both empty-set directions (no overlap, and holdout covers everything).
- **Out of scope (per roadmap):** multiple-comparisons correction across filter combinations, and the "reconcile against real multi-season data" checkpoint — both explicitly deferred to after roadmap item 1 lands, not part of this plan.
