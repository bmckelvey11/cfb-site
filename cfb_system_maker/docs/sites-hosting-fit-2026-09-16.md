# System Maker and Sites hosting

Date: 2026-09-16.

Question: Can the existing System Maker app run on Sites, and what can Sites support?

Method: Read current System Maker instructions and web.py, Over Zero's page.tsx, installed Sites 0.1.65 hosting/building guidance, storage references, and Sites connector contracts. This is a compatibility assessment, not a deployment or performance test. No statistical dataset, date range, or numerical benchmark applies.

Findings:

- System Maker currently uses Python/Flask, server-rendered pages, Python backtests, and local persisted data. Its documented serving inputs are games.csv and features.json; DuckDB is the warehouse, not the direct serving requirement.
- Sites accepts static websites or compatible Cloudflare Worker web applications. The documented deployment contract does not accept this existing Flask application unchanged.
- Sites supports interactive pages, server routes, persistent structured records through D1, files through R2, authentication, access controls, HTTP service integrations, and custom domains.
- Over Zero's page imports a published board.json snapshot. Hosting that page does not run its Python prediction pipeline.
- Practical options: publish exported System Maker reports; build a Sites interface connected to a separately hosted Python service; or port the app and required data workflows to the Sites runtime.
- For preserving current calculations with the least rewrite, host the existing app on a Python-capable server. If Sites is desired for the interface, keep Python calculations in a separately hosted service.

Limits: No workload sizing, cost, account quotas, external-host selection, migration, or live deployment was evaluated. Storage support does not establish that large searches or training jobs will fit the hosted runtime. Sites cannot directly read this machine's data files.

Reproduction: Inspect cfb_system_maker/web.py imports and /api/backtest, cfb_system_maker/CLAUDE.md pipeline description, models/over_zero/site/app/page.tsx board import, and installed Sites skills' hosting, starter-capabilities, and persistence-and-storage documents. No executable analysis script is needed for this documentation/code compatibility review.
