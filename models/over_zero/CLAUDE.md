# Over-zero instructions

Scope: Arscott, saturation, floor-bias, and monitoring work under this tree. Shared data,
archive, and no-lookahead rules live in root `CLAUDE.md`.

- Run commands from repository root unless a script documents a narrower working directory.
- Resolve raw and processed data through root `cfb_paths.py` and required `CFB_DATA_ROOT`.
  Never recreate an in-repository `data/` directory.
- Historical model copies may use local sibling imports; preserve numerical behavior when
  changing paths.
- First-half builders live in this unit's `scripts/` directory. Their inputs come from
  local DuckDB Action Network tables; outputs go under
  `$CFB_DATA_ROOT/processed/over_zero/`.
- This unit has no dedicated pytest suite. Verify changed scripts end to end against local
  data and inspect generated row counts/files.
