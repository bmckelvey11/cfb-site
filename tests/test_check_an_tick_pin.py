from cfb_system_maker.duckdb_load import _AN_TICK_COLUMNS
from scripts.check_an_tick_pin import schema_faults


def test_the_pinned_shape_is_clean():
    assert schema_faults(dict(_AN_TICK_COLUMNS)) == []


def test_a_sniffed_id_column_is_named_with_both_types():
    """What read_csv_auto leaves behind, and what the migration exists to undo."""
    live = dict(_AN_TICK_COLUMNS) | {"market_id": "BIGINT"}
    assert schema_faults(live) == ["market_id: BIGINT, pinned VARCHAR"]


def test_a_dropped_column_reads_as_missing_not_as_silence():
    live = {k: v for k, v in _AN_TICK_COLUMNS.items() if k != "is_live"}
    assert schema_faults(live) == ["is_live: <missing>, pinned BOOLEAN"]


def test_an_extra_column_is_reported():
    live = dict(_AN_TICK_COLUMNS) | {"scraped_at": "TIMESTAMP"}
    assert schema_faults(live) == ["unpinned column(s): scraped_at"]


def test_reordering_is_a_fault_even_when_every_type_is_right():
    """`read_csv(columns=...)` maps positionally: a reordered CSV lands every
    value in the wrong column while each type still looks correct."""
    items = list(_AN_TICK_COLUMNS.items())
    live = dict([items[1], items[0], *items[2:]])
    assert schema_faults(live) == [
        "column order drift: " + ", ".join(live)
    ]
