# Why the warehouse catalog test OOM'd intermittently

2026-09-16

## Question

`tests/test_warehouse_catalog.py::test_committed_catalog_matches_the_live_warehouse`
failed intermittently with `_duckdb.OutOfMemoryException: Out of Memory Error:
Allocation failure`, raised from `sample_rows()` in
`scripts/build_warehouse_catalog.py`. It passed when the file ran alone and
failed in the full suite, which pointed at the `ORDER BY ALL` sort being too
expensive. Was the sort the cause?

## Method

Replayed the builder's inner loop — `select * from "<schema>"."<table>" order by
all limit 3` over every table in `duckdb_tables()` — outside pytest, recording
per-table wall time, failures, `sum(memory_usage_bytes)` from `duckdb_memory()`,
process RSS, and `psutil.virtual_memory().available`. Then repeated it with
`set memory_limit` varied.

Data: the live warehouse at `CFB_DATA_ROOT`, `data/cfb.duckdb`, 5.3 GB, 323
tables, as of 2026-09-16. DuckDB 2.0.0.dev2609121639. Machine: 16.5 GB RAM.

## Numbers

The sort is not the cause. `raw.teams`, the table named in the traceback, is
9,364 rows over 5 columns totalling 9.1 MB of JSON — trivial to sort. Nothing in
the loop takes meaningful memory on its own; `ORDER BY ... LIMIT 3` is a
streaming top-N.

What the run actually costs, uncapped:

| Setting | Elapsed | Failures | DuckDB memory | Process RSS |
| --- | --- | --- | --- | --- |
| default (`memory_limit` 12.5 GiB) | 14.8s | 0 or many, run to run | 4.79 GB | 2.33-3.23 GB |
| `memory_limit='1GB'`, threads 4 | 9.6s | 0 | 0.98 GB | 1.14 GB |
| `memory_limit='1GB'`, threads default | 8.7s | 0 | 0.97 GB | 1.12 GB |

Capping is also the faster of the two, since a pool that never evicts is a pool
that keeps paying to hold data no later table reads.

The cause is buffer-pool residency. Sampling touches every table, so DuckDB
pages in most of the 5.3 GB file and, under a default limit of 80% of RAM
(12.5 GiB here), never has to evict. Free memory on this box sat at 2.26 GB at
the start of a failing run and 0.82 GB at the end. The allocation that fails is
whichever one lands after the pool has crowded out the rest of the machine,
which is why the failing table moved between runs and why the full suite — which
has already consumed memory — failed more often than the file alone.

One uncapped run also threw 90+ `IO Error: Could not read file` alongside the
OOMs, consistent with the buffer manager being unable to allocate to read a
block. Those vanished under the cap.

## Fix

`connect()` in `scripts/build_warehouse_catalog.py` opens the read-only
connection and sets `memory_limit='1GB'`. `build()` and
`test_sampling_is_deterministic` both go through it — the latter opened its own
connection and carried the same failure mode.

Determinism is untouched: the pragma does not change the query text, so
`ORDER BY ALL` still gives the total order the sampling docstring depends on.
Verified by running `--check` twice (both "catalog is current") and by
`test_sampling_is_deterministic`. Threads were left alone — capping memory alone
is sufficient.

## What this does not support

- It does not say 1 GB is a tuned optimum. It is the first value measured, and
  DuckDB saturating it (0.97 GB) while returning zero failures is the evidence
  that eviction works under it — not evidence that lower would fail.
- It does not generalise to other warehouse consumers. Only the catalog builder
  scans every table; a query that genuinely needs a large hash join or sort
  would be slowed or spilled by the same cap.
- It says nothing about machines with more headroom, where the default limit
  never crowds the OS and the bug would not appear at all.

## Reproducing

```
set CFB_DATA_ROOT=C:/Users/mckel/dev/cfb/data
python -m pytest tests/ -q -k "catalog or warehouse"
python scripts/build_warehouse_catalog.py --check
```

To re-measure the memory profile, run the builder's loop against
`duckdb_tables()` and read `select sum(memory_usage_bytes) from duckdb_memory()`
after it finishes, with and without the pragma.
