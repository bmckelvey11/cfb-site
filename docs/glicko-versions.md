# Glicko rating versions

Every Glicko model this repo has published or tested has a name, and that name always means
one exact model. The registry is [`scripts/glicko_versions.py`](../scripts/glicko_versions.py).
This page is its changelog: what each version changed and why it has the status it has. How
the current version works is in [`glicko-method.md`](glicko-method.md).

- **Current version (published by default): P1.1.**
- `python -m scripts.glicko_versions` lists the versions, and `--show <name>` prints one in full.
- `--check` rebuilds every frozen version from the current code. It confirms each one still
  produces its frozen forecasts, using the stored fingerprints. This needs `CFB_DATA_ROOT`.
- `python -m scripts.glicko_ratings_table --season 2026 --version <name>` builds the table for
  any version that rates the full game pool.
  - P1 and P1.1 write `glicko_ratings_<season>.csv`, because their ratings are identical.
  - Any other version writes `glicko_ratings_<season>_<name>.csv`.
  - Every file's `version` column carries the name.

**Statuses:**

| Status | Meaning |
| --- | --- |
| current | Published by default. |
| adopted | Passed its test and is in use. |
| candidate | Built and frozen; waiting for its holdout test. |
| declared | Specified, not built yet. |
| rejected | Failed its declared test. |
| retired | Replaced by a later version. |

## Versions

| Version | Status | Date | What it is | Record |
| --- | --- | --- | --- | --- |
| v1 | retired | 2026-09-24 | Rated only games that had a betting line. Replaced by P1. | [glicko-ratings-2026-09-24.md](glicko-ratings-2026-09-24.md) |
| P1 | adopted | 2026-09-24 | Rates every completed D-I game, and pulls teams toward their conference average each offseason. Has a sealed 2026 check. | [glicko-pool-2026-09-24.md](glicko-pool-2026-09-24.md) |
| **P1.1** | **current** | 2026-10-15 | Same ratings and ranks as P1, with tighter forecast ranges: σ_pred 13.5 for intervals and win probabilities, while ratings still learn with σ 15. | [glicko-p2-2026-10-15.md](glicko-p2-2026-10-15.md) |
| P2 | rejected | 2026-10-15 | Preseason prior (returning production and recruiting) plus a blowout clip. It was worse on 2021–25 and on 2026 weeks 1–7. | [glicko-p2-2026-10-15.md](glicko-p2-2026-10-15.md) |
| P3-A | candidate | 2026-10-17 | Schedule strength: credits teams for beating opponents who later prove good. | [P3 spec](superpowers/specs/2026-10-16-glicko-p3-bundles-design.md) |
| P3-B | candidate | 2026-10-17 | Conference switchers regress toward their new conference, plus a 3-season history. The returning-production weight was tuned to 0. | [P3 spec](superpowers/specs/2026-10-16-glicko-p3-bundles-design.md) |
| P3-C | candidate | 2026-10-17 | Home edge trending by season, overtime read as a tie, extra noise for bowls and FCS games, neutral sites near a campus, time zones. | [P3 spec](superpowers/specs/2026-10-16-glicko-p3-bundles-design.md) |
| P3-D | candidate | 2026-10-17 | FBS-vs-FCS expected margins shrunk by 5% (λ 0.05), σ_pred 12.5. | [P3-D spec](superpowers/specs/2026-10-17-glicko-p3d-fcs-design.md) |

## Rules

- **A version never changes.** A different parameter or a code change that moves any of a
  version's forecasts makes a new version. The fingerprint check catches a version that has
  drifted.
- **Candidates are promoted only by their holdout looks.** The interim look for P3-A to P3-D
  comes after the 2026 postseason, no earlier than 2027-01-20. The final look comes after the
  2027 postseason. If a candidate passes, it becomes a new numbered version on top of P1.1;
  passing candidates are tried together before any of them is published.
- **Changing `CURRENT`** in the registry is how a new version becomes the default. That change
  gets its own commit, and a row on this page.
