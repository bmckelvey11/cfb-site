---
name: stats-test-discrimination
description: When reviewing statistical/algorithmic test suites (BH correction, p-value math), check that each named property has a test vector that actually fails without the correct implementation, not just a vector that happens to satisfy the property trivially.
metadata:
  type: feedback
---

For algorithmic correctness tests (e.g. Benjamini-Hochberg step-up correction in
`cfb_system_maker/backtest.py`'s `bh_correct`), passing tests are not sufficient
evidence — verify each test actually discriminates against a plausible buggy
implementation.

**Concrete case found in MVP-001**: `bh_correct`'s monotonicity test used
`[0.2, 0.001, 0.05, 0.9, 0.01, 0.5]`. A naive implementation that omits the
reverse-cumulative-minimum step (just `p_(i) * K / i` per rank, no running min)
produces an already-monotonic result for that vector and passes the test anyway.
Only the tie test happened to catch the missing cummin step. Confirmed empirically
by writing a naive impl and running it against the suite.

**Why**: The advisor caught this by asking "trace a plausible buggy implementation
against this test" rather than just re-deriving the correct math. Passing tests
prove the correct implementation is *consistent* with the test, not that the test
would catch a *regression*.

**How to apply**: When reviewing new tests for algorithms with known failure modes
(off-by-one in rank scaling, missing monotonicity enforcement, wrong tie-breaking),
mentally write the most obvious buggy variant and check whether the existing test
vectors would catch it. For BH correction specifically, a vector like
`[0.04, 0.05]` at alpha=0.05 is a good general-purpose discriminating case — it
forces the step-up correction to actually change a rank's significance verdict,
and it also pins the inclusive `corrected_p <= alpha` boundary, which naturally
constructed "hand-verified oracle" vectors tend to avoid (they cluster values
away from round boundaries like exactly 0.05).
