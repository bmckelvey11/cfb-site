Follow `CLAUDE.md` for shared repository rules and nearest nested `CLAUDE.md` for
unit-specific rules. This file owns no separate project conventions.

## Learned User Preferences

- Prefer notebook warehouse reads through root `db.py` (`get_table`, `pivot`) with `read_only=True` (the default).

## Learned Workspace Facts

- Root `db.py` opens `$CFB_DATA_ROOT/cfb.duckdb` via `cfb_paths.DB_PATH`; DuckDB `read_only=True` still fails if another process holds a write lock — close the writer first.
- Cursor's built-in Markdown Preview does not typeset `$`/`$$` KaTeX; correct repo math can still look broken there — use a KaTeX-capable preview (e.g. Markdown Preview Enhanced).
