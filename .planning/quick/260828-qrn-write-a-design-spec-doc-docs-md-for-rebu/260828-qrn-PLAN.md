---
task: Design spec for rebuilding data/cfb.duckdb clean
status: in-progress
created: 2026-08-28
files_modified: [docs/duckdb-rebuild-spec.md]
autonomous: true
must_haves:
  truths:
    - "docs/duckdb-rebuild-spec.md exists and describes the loader that is actually in the repo today"
    - "The doc's DuckDB CLI flag list matches cli.py's duckdb subparser exactly — no invented flags, none missing"
    - "The doc states the load is a full rebuild, and locates resume/--force in the scraper layer where it actually lives"
    - "The doc names the _post_wk filename gap as a defect the rebuild will surface, and the check that proves it stays true"
  artifacts:
    - docs/duckdb-rebuild-spec.md
  key_links:
    - "doc CLI section <-> cfb_system_maker/cli.py duckdb subparser (verified by a set comparison, not by eye)"
    - "doc known-gaps section <-> duckdb_load.parse_dump_stem (verified by re-deriving the gap from disk)"
---

# Quick: DuckDB rebuild design spec

## Goal

Write `docs/duckdb-rebuild-spec.md` — a reviewed-before-implementation spec for rebuilding
`data/cfb.duckdb` clean, using the **same design `cfb_system_maker/duckdb_load.py` already
implements**. Documentation only. No code changes, no new files under `scripts/`, no edits
to `duckdb_load.py` or `cli.py`.

Match `docs/data-coverage.md`'s conventions: prose that explains *why*, tables for
enumerations, runnable commands cited so counts are regenerable rather than hand-kept, and
sections that record what a count cannot tell you.

## Why this doc exists (established during planning — use it, don't re-derive it)

The artifact on disk is **not reproducible by any current-code invocation**. Verified:

| Evidence | Value |
|---|---|
| `meta.load_report` `loaded_at` | 2026-08-27 05:51 (61 `raw` + 36 `graphql` rows) |
| `data/cfb.duckdb` mtime | 2026-08-28 11:07 |
| Live catalog | `raw` 97, `stg` 99, `meta` 1 — **no `graphql` schema at all** |
| 36 of the 97 `raw` tables | absent from the `raw` load report; 35 of them appear in the **`graphql`** load report |
| One of them | `calendar_gql` — the clash suffix `explode_payloads` mints, sitting in `raw` |
| 3 `stg` tables with no `raw` twin | `ppa_games_defense`, `venue_orientation`, `venue_orientation_labeled` |

State the rows above as **observations**; the mechanism is an open question for the reviewer.
The catalog shows the `graphql` schema's contents now sitting in `raw` while the load report
still calls them `graphql`, and three `stg` tables have no `raw` twin. A hand edit, a modified
loader run, and a MotherDuck round-trip would all leave this fingerprint — the user reviewing
the spec likely knows which, and overclaiming a hand-edit is what gets the whole
"not reproducible" section discounted. What is *not* in doubt: no current-code invocation
produces this catalog, and `meta.load_report` describes a smaller, older build than the file
now contains.

It is also **stale**. The build predates two scrapes that landed later the same day:
`data/raw/` now holds **132 `_post_wk` files** and **520 `_ngt` files** (newest 2026-08-28
16:42), none of which are in the DB. Totals on disk: 2,558 `data/raw/*.json`, 50
`data/graphql/*.json`, plus `data/raw/actionnetwork/`.

## Approach

The two hazards are inventing behavior the code does not have, and describing the rebuild as
if it will go cleanly. Both are addressed explicitly below.

### The reframe that must not be lost

The task brief asks for "resume/idempotency behavior (skip-if-exists vs `--force`)".
`build_duckdb` has **no such thing**, and the doc must not manufacture it. What it does:
builds into `{db}.building`, unlinks the old file, `replace()`s — a full rebuild, atomic at
the file level, rolled back by unlinking the temp on any exception. Idempotency here means
*the DB is a pure function of (on-disk files, flags)*. Skip-if-exists and `--force` are
`scrapers.py` vocabulary, one layer upstream, and are deliberately not mirrored in the
loader. Say that, and say why — do not silently satisfy the brief either way.

### Facts the spec must get right (all verified against source during planning)

- **`--only` is destructive, not incremental.** It filters `_plan_loads` jobs, then builds a
  fresh `.building` and replaces the existing DB. `--only games` against a 196-table DB
  yields a one-table DB. Sharpest footgun in the file.
- **`meta.load_report` is not a manifest of the DB.** `_write_meta` runs *before* the
  `if explode:` branch, so `stg` reports are returned and printed but never persisted.
  `--explode-only` and `--flatten-nested` write no report rows at all.
- **JSON root format is sniffed, not declared.** `_plan_loads` sets `format: array|object`,
  but `_load_job` only branches on `csv`; `_insert_json_file` reads the first non-space
  character per file (`_json_root_format`).
- **Two different parsers, two different jobs.** `parse_dump_stem` groups files into tables;
  a separate in-SQL `regexp_extract` on the filename fills the `season` / `week` columns.
  They can disagree — see the gap below.
- **Load order is arbitrary except in one place.** Tables are independent; the one
  order-dependent semantic is the `stg` name clash — `explode_payloads` sorts raw-first so
  `raw.calendar` wins bare `stg.calendar` and GraphQL takes `calendar_gql` (`_stg_dest_name`).
- **The tuning knobs are deliberate**, not incidental: `threads = 1`,
  `preserve_insertion_order = false`, and a per-file `maximum_object_size` sized to the file
  rather than a global gigabyte (small tables OOM otherwise).
- **`_SKIP_STEMS`** drops `user_info` (account metering, same category as `/info/usage` in
  `docs/data-coverage.md`); `_` -prefixed stems are skipped too.
- **`raw` vs `stg`.** `raw`/`graphql` keep `payload JSON, source_file, season, week` so
  season-to-season schema drift cannot break a load. `stg.*` is the exploded view:
  `json_group_structure` -> `json_transform` -> recursive `unnest` with
  `keep_parent_names`, dotted names rewritten to underscores (`offense.overall` ->
  `offense_overall`), arrays left as lists so row grain is unchanged, load filename kept as
  `_source_file`. `--flatten-nested` exists because that pass can leave STRUCT columns behind.
- **The MotherDuck mirror (`md:cfb`) is out-of-band.** There is no code for it in the repo
  (`grep -ri motherduck` hits only prose in `consolidation.md`). Describe it as the manual
  step it is; do not spec a push the codebase does not implement.

### The gap the rebuild will hit first

`_post_wk` files do not parse. Confirmed:

```
parse_dump_stem('game_team_stats_2024_post_wk1') -> ('game_team_stats_2024_post_wk1', None, None)
in-SQL filename regex on that file             -> season=None, week=1
```

`_SEASON_WEEK_RE` requires `_{season}_wk{n}` with nothing between, so the whole stem survives
as a table name. A clean rebuild today therefore mints **~132 single-file tables** with a NULL
`season` and a populated `week`, and postseason rows go missing from any
`WHERE season = 2024` on the regular table. `tests/test_duckdb_load.py` has no case for this
filename shape, which is why nothing caught it. `_ngt` files parse fine
(`ppa_games_ngt_2024` -> `('ppa_games_ngt', 2024, None)`) **except** where they are also
postseason (`ppa_players_games_ngt_2024_post_wk3`).

Spec the fix as a **decision for review, not an implementation**: optional `_post` segment in
`_SEASON_WEEK_RE`, matching change to the in-SQL regex, and a `season_type` column so the two
passes stay distinguishable. Flag that a fix changes table identity, so it is a rebuild-time
decision rather than a patch.

### Adding a new endpoint — the true answer is short

You do not touch `duckdb_load.py`. Add the `Endpoint` to `scrapers.py` `ENDPOINTS` (or the
table to `GQL_DEFAULT_TABLES`), scrape, rebuild — the loader picks it up by glob. The loader
only needs changing when a new **filename shape** appears. `_post_wk` is exactly that case,
which is what ties this section to the gap above.

## Tasks

<task type="tracer">
  <name>Task 1: Write the spec — motivation, schema, sources, load semantics, raw vs stg</name>
  <files>docs/duckdb-rebuild-spec.md</files>
  <read_first>
    cfb_system_maker/duckdb_load.py (whole file), cfb_system_maker/cli.py (`_duckdb` and the
    `duckdb_parser` block), tests/test_duckdb_load.py, docs/data-coverage.md (style),
    docs/db-migration-decision.md and consolidation.md (so the spec does not contradict the
    prior DB decision and describes the MotherDuck mirror as out-of-band).
  </read_first>
  <action>
    Create the doc end-to-end thin: every heading present, the load path narrated once from
    files to `stg`. Cover, in this order — why a clean rebuild is needed (use the
    reproducibility and staleness evidence tabulated above); sources
    (`data/raw/*.json`, `data/graphql/*.json`, `data/raw/actionnetwork/` scoreboard+history,
    `data/raw/actionnetwork_odds.csv`, and the skipped stems); schema (`raw` / `graphql`
    payload shape, `stg`, `meta.load_report` and what it does not cover); load order and its
    one order-dependent semantic; rebuild semantics framed as full-rebuild-plus-atomic-replace
    with resume located in the scraper; and the raw-vs-stg distinction with the explode and
    flatten passes. Put the loader's command-line surface in one fenced block under a heading
    named exactly `## CLI surface`, listing every flag the `duckdb` subparser accepts and
    nothing else. Four other headings are spelled exactly, because the gate string-matches
    them: `## Sources`, `## Schema`, `## Rebuild semantics`, `## raw vs stg` (lowercase
    `raw`/`stg` — they are schema names). Any other heading you want is free-form.
    Cite regeneration commands for every count the way `data-coverage.md` does,
    rather than hardcoding numbers that rot. Keep it descriptive of code that exists; anything
    proposed goes in Task 2's section, labelled as a proposal.
  </action>
  <verify>
    <automated>Run from the repo root, exactly as written (verified working during planning):

python - <<'PY'
import pathlib, re
doc = pathlib.Path('docs/duckdb-rebuild-spec.md').read_text(encoding='utf-8')
cli = pathlib.Path('cfb_system_maker/cli.py').read_text(encoding='utf-8')
actual = set(re.findall(r'duckdb_parser\.add_argument\(\s*"(--[a-z-]+)"', cli))
assert len(actual) == 7, f'cli.py parse found {actual}'
block = re.search(r'^## CLI surface\s*$.*?^```.*?^(.*?)^```', doc, re.S | re.M)
assert block, 'no fenced block under "## CLI surface"'
documented = set(re.findall(r'--[a-z][a-z-]+', block.group(1)))
assert documented == actual, f'invented={sorted(documented-actual)} missing={sorted(actual-documented)}'
for h in ['## Sources', '## Schema', '## Rebuild semantics', '## raw vs stg']:
    assert h in doc, f'missing heading {h}'
assert 'meta.load_report' in doc
assert '.building' in doc, 'atomic-replace mechanic not described (needs the .building temp name)'
print('OK', sorted(actual))
PY</automated>
  </verify>
  <done>
    `docs/duckdb-rebuild-spec.md` exists; its `## CLI surface` block lists exactly the seven
    flags `cli.py` defines for the `duckdb` subcommand; the named headings are present; the
    rebuild section describes atomic replace via the `.building` temp rather than any
    per-table skip behavior.
  </done>
</task>

<task type="auto">
  <name>Task 2: Add known gaps, the add-an-endpoint process, and the mirror note</name>
  <files>docs/duckdb-rebuild-spec.md</files>
  <action>
    Extend the doc with three sections. (1) `## Known gaps the rebuild will surface` — the
    `_post_wk` parsing defect, shown with the two parser outputs above, its blast radius
    (~132 one-off tables, NULL `season`, postseason rows invisible to a season filter), the
    absence of a test for that filename shape, the `_ngt` interaction, and the proposed fix
    presented as a decision to review with its table-identity consequence stated. Also record
    `--only` as destructive, and that `meta.load_report` omits the `stg` pass. (2)
    `## Adding a new endpoint` — registry-then-scrape-then-rebuild, with the loader untouched
    unless a new filename shape appears, naming `_post_wk` as the precedent. (3)
    `## MotherDuck mirror` — `md:cfb` is a manual, out-of-band push with no code in the repo;
    cite the grep that shows it. Add one line noting a threat model was omitted deliberately:
    documentation-only change, no trust boundary crossed, no package installed.
  </action>
  <verify>
    <automated>Run from the repo root, exactly as written (verified working during planning):

python - <<'PY'
import pathlib, glob, re
from cfb_system_maker.duckdb_load import parse_dump_stem
doc = pathlib.Path('docs/duckdb-rebuild-spec.md').read_text(encoding='utf-8')
for h in ['## Known gaps the rebuild will surface', '## Adding a new endpoint', '## MotherDuck mirror']:
    assert h in doc, f'missing heading {h}'
post = glob.glob('data/raw/*_post_wk*.json')
assert post, 'no postseason files on disk — re-check the premise'
unparsed = [p for p in post if parse_dump_stem(pathlib.Path(p).stem)[1] is None]
assert len(unparsed) == len(post), 'parser changed: the doc section must be updated'
assert '_post_wk' in doc and 'season_type' in doc
assert re.search(r'md:cfb', doc), 'mirror not named'
print(f'OK — {len(post)} postseason files still unparsed, doc records it')
PY</automated>
  </verify>
  <done>
    All three sections present; the gap section survives a live re-derivation of the parsing
    defect from disk (the check fails loudly if the parser is later fixed without the doc
    being updated); the mirror is described as manual with no code behind it.
  </done>
</task>

## Done when

- `docs/duckdb-rebuild-spec.md` is committed and both automated checks pass.
- No file outside `docs/` is modified — confirm with `git status --short` before committing.
- A reader can rebuild from the doc alone: which files feed which schema, what one command
  produces, what the two explode passes do, and which flag will silently shrink their database.
- The doc claims nothing the code does not do. Specifically, it does not attribute
  skip-if-exists behavior to the loader, and it does not describe a MotherDuck push as
  automated.
