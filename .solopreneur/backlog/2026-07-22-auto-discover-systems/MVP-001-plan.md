# Plan: Stats primitives — analytic p-value helper + Benjamini-Hochberg correction

## Context
`cfb_system_maker/backtest.py` currently computes a system's one-sided analytic p-value only as a byproduct of `_hit_rate_z_test(hit_rate, n, break_even_rate)`, which is called from `compute_system_stats(details: list[BetDetail], ...)` — i.e. it requires a full `BetDetail` list to reach. MVP-004 (holdout finalist grading) needs to compute an analytic p-value directly from summary counts (`wins`, `decided`, `break_even_rate`) — the same shape of data `run_backtest_summary` already returns — without constructing `BetDetail` objects, and then run a Benjamini-Hochberg multiple-testing correction across a batch of K finalists' p-values. Neither function exists yet. This ticket adds both as pure, standalone functions with no dependency on search machinery (search itself is MVP-002/003, not built yet) and with **zero involvement in the existing letter-grade path** (`compute_grade`).

**Branch**: `ticket/MVP-001` (already checked out)

**Open decision for the CEO** (ticket leaves this ambiguous — flagging per Step 1, do not silently resolve elsewhere): the ticket's technical notes suggest the extraction helper be named `_analytic_p_value(wins, decided, break_even_rate)` — this plan uses exactly that name and signature, and the public BH function is named `bh_correct(p_values: list[float], alpha: float = 0.05) -> list[dict]` per the acceptance criteria's primary suggested form. If the coding agent or CEO prefers a different name/signature, that is a deliberate deviation to flag back, not something to guess differently mid-build.

## Step 1: Extract `_analytic_p_value` from `_hit_rate_z_test` without changing `_hit_rate_z_test`'s behavior
**Files**: `cfb_system_maker/backtest.py` (modify)
**Do**:
Add a new private helper directly below `_hit_rate_z_test` (currently at the bottom of the file, around line 470-479):

```python
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
```

Do NOT modify `_hit_rate_z_test` itself, `compute_system_stats`, or `run_backtest_summary` — this is a pure addition. `_hit_rate_z_test` keeps returning `(z_score, p_value)` unchanged because `SystemStats.z_score` and `compute_grade`'s `_roi_significance_score(stats.z_score)` still depend on it; do not try to fold z_score-producing callers into the new counts-only helper.

**Acceptance**: File still imports and the existing test suite is unaffected — run `.venv\Scripts\python.exe -m pytest tests/test_backtest.py -q` and confirm the same pass count as before this step (no regressions; new function has no test yet so count is unchanged at this point).

## Step 2: Add agreement test proving `_analytic_p_value` matches `SystemStats.p_value`
**Files**: `tests/test_backtest.py` (modify)
**Do**:
Add `_analytic_p_value` to the existing import block at the top of the file (alongside `_hit_rate_z_test` style private imports — note `_hit_rate_z_test` itself is not currently imported by the test file, so add both `_analytic_p_value` to the import list from `cfb_system_maker.backtest`).

Add a new test near `test_system_stats_include_edge_and_wilson_bounds` (around line 164) that proves the extraction produces identical results to the existing `SystemStats.p_value` path for the same decided-bet counts. Use counts where `wins/decided` divides evenly to avoid rounding ambiguity in the oracle (e.g. 130 wins / 200 decided = exactly 0.65):

```python
def test_analytic_p_value_agrees_with_system_stats_p_value_for_same_counts():
    # 130 wins / 200 decided = exactly 0.65 -- avoids rounding ambiguity in the oracle.
    details = _bets(130, 70)
    stats = compute_system_stats(details, hit_rate=0.65, roi=0.1815, american_odds=-110, stake=1.0)

    direct = _analytic_p_value(wins=130, decided=200, break_even_rate=stats.break_even_rate)

    assert direct == stats.p_value


def test_analytic_p_value_returns_one_when_no_decided_bets():
    assert _analytic_p_value(wins=0, decided=0, break_even_rate=0.5238) == 1.0
```

Reuse the existing `_bets(win_count, loss_count)` helper already defined in this file (around line 279) — do not duplicate it.

**Acceptance**: Run `.venv\Scripts\python.exe -m pytest tests/test_backtest.py -k analytic_p_value -q` — both new tests pass.

## Step 3: Implement `bh_correct` (Benjamini-Hochberg, step-up/reverse-cummin form)
**Files**: `cfb_system_maker/backtest.py` (modify)
**Do**:
Add a new public function near the bottom of the file, after `_analytic_p_value` (or grouped with the other public functions near the top — place it directly after `_analytic_p_value` for locality since they're conceptually paired). Implement using the standard reverse-cumulative-minimum step-up form, which gives rank-scaled comparison, guaranteed monotonicity after order restoration, and correct tie handling all from one construction — do not implement BH as a flat `alpha / K` Bonferroni division:

```python
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
```

**Acceptance**: File still imports cleanly — run `.venv\Scripts\python.exe -c "from cfb_system_maker.backtest import bh_correct; print(bh_correct([0.5], alpha=0.05))"` and confirm it prints a single-element list with `raw_p=0.5`, `corrected_p=0.5`, `bh_significant=False`.

## Step 4: Add BH known-value, monotonicity, and tie-handling tests
**Files**: `tests/test_backtest.py` (modify)
**Do**:
Add `bh_correct` to the import block from `cfb_system_maker.backtest` (same import line touched in Step 2).

Add the following tests, grouped together near the end of the file (after the existing grade-related tests, before or after `test_run_backtest_populates_grade_field` — pick a clear location such as a new section comment `# --- Benjamini-Hochberg correction (MVP-001) ---`):

```python
# --- Benjamini-Hochberg correction (MVP-001) ----------------------------------
# bh_correct is a standalone stats primitive with NO call site in compute_grade
# or any letter-grade path -- it exists only for MVP-004's holdout finalist
# batch correction, not for per-system grading.


def test_bh_correct_known_value_vector():
    # Hand-verified oracle: p=[0.001, 0.01, 0.5, 0.8], K=4, alpha=0.05
    # rank 1: 0.001 * 4/1 = 0.004
    # rank 2: 0.01  * 4/2 = 0.02
    # rank 3: 0.5   * 4/3 = 0.6667 -> rounds to 0.667
    # rank 4: 0.8   * 4/4 = 0.8
    # reverse-cummin leaves all four unchanged here (already increasing)
    p_values = [0.001, 0.01, 0.5, 0.8]

    results = bh_correct(p_values, alpha=0.05)

    corrected = [round(r["corrected_p"], 4) for r in results]
    assert corrected == [0.004, 0.02, 0.6667, 0.8]
    assert [r["bh_significant"] for r in results] == [True, True, False, False]
    assert [r["raw_p"] for r in results] == p_values


def test_bh_correct_maps_back_to_original_input_order_when_shuffled():
    # Same oracle vector as above, shuffled -- proves restoration to ORIGINAL
    # identity/order, not sorted order.
    shuffled = [0.8, 0.001, 0.5, 0.01]  # indices: 0=0.8, 1=0.001, 2=0.5, 3=0.01

    results = bh_correct(shuffled, alpha=0.05)

    assert [r["raw_p"] for r in results] == shuffled
    corrected = [round(r["corrected_p"], 4) for r in results]
    assert corrected == [0.8, 0.004, 0.6667, 0.02]
    assert [r["bh_significant"] for r in results] == [False, True, False, True]


def test_bh_correct_adjusted_p_values_are_monotonic_after_restoration_when_sorted_by_raw_p():
    # Standard BH step-up property: once results are re-sorted by raw_p
    # ascending, corrected_p must be non-decreasing.
    raw = [0.2, 0.001, 0.05, 0.9, 0.01, 0.5]

    results = bh_correct(raw, alpha=0.05)

    by_raw_p = sorted(results, key=lambda r: r["raw_p"])
    corrected_in_rank_order = [r["corrected_p"] for r in by_raw_p]
    assert corrected_in_rank_order == sorted(corrected_in_rank_order)


def test_bh_correct_ties_receive_identical_corrected_p_and_significance():
    # Three tied p-values at the same raw_p must get the identical corrected_p
    # (and therefore identical bh_significant) under standard BH tie handling.
    p_values = [0.3, 0.01, 0.01, 0.01, 0.9]

    results = bh_correct(p_values, alpha=0.05)

    tied_corrected = {round(results[i]["corrected_p"], 6) for i in (1, 2, 3)}
    assert len(tied_corrected) == 1
    tied_significant = {results[i]["bh_significant"] for i in (1, 2, 3)}
    assert len(tied_significant) == 1


def test_bh_correct_empty_input_returns_empty_list():
    assert bh_correct([], alpha=0.05) == []


def test_bh_correct_corrected_p_never_exceeds_one():
    results = bh_correct([0.9, 0.95, 0.99, 1.0], alpha=0.05)

    assert all(r["corrected_p"] <= 1.0 for r in results)


def test_bh_correct_is_not_called_from_compute_grade_or_grading_source():
    # Guards acceptance criterion 6 structurally: bh_correct must have no call
    # site anywhere in backtest.py's grading path. This is a source-text check
    # (import-based introspection can't distinguish "referenced" from "called
    # by compute_grade" reliably), so it directly inspects the module source.
    import inspect

    from cfb_system_maker import backtest as backtest_module

    grade_source = inspect.getsource(backtest_module.compute_grade)
    assert "bh_correct" not in grade_source

    for score_fn_name in (
        "_sample_size_score",
        "_roi_significance_score",
        "_consistency_score",
        "_permutation_score",
        "_overfit_score",
    ):
        fn_source = inspect.getsource(getattr(backtest_module, score_fn_name))
        assert "bh_correct" not in fn_source
```

**Acceptance**: Run `.venv\Scripts\python.exe -m pytest tests/test_backtest.py -k bh_correct -q` — all 8 new tests pass, including the known-value vector, the shuffled-order-restoration test, the monotonicity test, the tie test, the empty-input edge case, the clamp-at-1.0 edge case, and the compute_grade isolation test.

## Step 5: Full regression run and manual grep confirmation of acceptance criterion 6
**Files**: none (verification only)
**Do**:
1. Run the complete test suite to confirm no regressions anywhere else in the codebase: `.venv\Scripts\python.exe -m pytest -q`
2. Run a direct grep across the whole `cfb_system_maker` package to double-confirm `bh_correct` has no call site outside `backtest.py`'s definition and the tests: search for `bh_correct` across `cfb_system_maker/*.py` and confirm the only match in `backtest.py` is the `def bh_correct(...)` definition line itself (no call sites anywhere in the module, including outside `compute_grade` — e.g. not called from `run_backtest`, `run_backtest_summary`, or `compute_system_stats` either, since this ticket is additive-only).
3. Confirm `_analytic_p_value` similarly has no call site yet outside its own definition and the tests added in Step 2 (MVP-004 is the ticket that wires it up — this ticket only adds the primitive).

**Acceptance**:
- Full suite passes: `.venv\Scripts\python.exe -m pytest -q` shows 0 failures, and the total test count is the prior baseline + 10 (2 from Step 2 + 8 from Step 4).
- Grep confirms `bh_correct` appears in `cfb_system_maker/backtest.py` only at its `def` line (plus the docstring's self-reference), nowhere in `compute_grade`, the five `_*_score` helper functions, `run_backtest`, `run_backtest_summary`, or `compute_system_stats`.
- Grep confirms `_analytic_p_value` appears in `cfb_system_maker/backtest.py` only at its `def` line and inside its own docstring — no other call sites in this ticket.
