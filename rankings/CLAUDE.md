# Rankings instructions

Scope: **team ratings**. This unit owns the Glicko margin rating, which is the published team
rating, plus its theory, plans, preregistered specs, method, version history and dated
results. Shared data, archive and no-lookahead rules live in root `CLAUDE.md`.

`docs/README.md` indexes every document in this tree, sorted into theory, plans, method and
versions, and records. Start there.

- **Code stays in `scripts/` for now** (`scripts/glicko_*.py`, `scripts/glicko_*_frozen.json`).
  Moving it would break imports, and the frozen JSONs and sealed fingerprints record script
  paths. Move code only in a commit that re-verifies every fingerprint.
- **What is published:** `scripts/glicko_versions.py` names every version, and `CURRENT`
  (P1.1) is what the ratings table writes by default. `docs/glicko-versions.md` is its
  changelog. Add a registry entry before publishing any other version.
- **Sealed and declared tests are binding.** P1's 2026 confirmation and the P3 bundles'
  holdouts each have a frozen file and a dated "not before" look. Never read a holdout early,
  never edit a `*_frozen.json` or `*_declared.json`, and declare any new candidate in
  `docs/specs/` before tuning it.
- **Theory vs plans.** Theory docs say what is believed and why; plans say what to build or
  test next and how it will be judged. A finding goes in a dated record, not in either.
- Treat a rating as descriptive. Neither a rating nor a forecast is a betting edge until it
  clears the market-information gates in the roadmap.

**Verify:**

```bash
python -m pytest -q tests/test_glicko_*.py tests/test_docs_math.py tests/test_docs_index.py
python -m scripts.glicko_versions --check
```

The second command needs `CFB_DATA_ROOT` and rebuilds every frozen version.
