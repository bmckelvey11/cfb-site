# Over Zero refresh — September 11, 2026

Completed model refresh and validation on September 11.

Question: refresh current prices and remove settled games from the open board.

Method: `scripts/best_line_slate.py --json models/over_zero/site/lib/board.json`,
run from the repository root with CFB_DATA_ROOT set. Fit uses 12,988 games from
2013–2025. Current Action Network prices were fetched at 08:26 UTC; offshore
prices use the existing 06:00 UTC snapshot, with separate timestamps on the site.
The next-eight-days window now excludes games whose kickoff has passed in both
feeds. The prior one-day lookback incorrectly retained last night's Miami game.

Results: 85 market-priced games, 10 market-wide signals, 11 unique displayed
signals including playable book-only qualifiers. Model CSV and website values
match. All displayed kickoffs are after the run timestamp.

Action Network event 288898 is final: Miami 77, Florida A&M 7. The previous
published board had market total 65.5 (best available 65); both won. Adding this
win to the previously published 10–4 record gives 11–4, 15 settled, 73.3%.
This carries forward the existing Week 1 record rather than reconstructing it.

Reproduce verification with `scripts/verify_site_refresh.py` under this unit and
`node --experimental-strip-types models/over_zero/site/lib/game-views.test.mjs`.
Checks passed for values, future kickoffs, unique games, inclusion of book-only
qualifiers, price ties, and empty cases. These checks do not validate a new
betting edge or guarantee that quoted prices remain available.

Publication completed September 11: site version 23 deployed successfully.
The live page was verified at 08:26 UTC snapshot time with 11 open signals,
11–4 and 73.3%. The existing browser tab needed a cache-busting URL to load the
new publication. Build and model-to-board checks passed.
