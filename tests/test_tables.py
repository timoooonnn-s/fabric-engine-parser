from __future__ import annotations

from fabric_weft.tables import Columns, split_tables

TWO_TABLES = """\
====================
       Demo Info
====================
ID   NAME
--------------------
1    one
2    two

All 2 out of 2 Total displayed

     SECOND
ID   VALUE
--------------------
1    a
--------------------
 Total: 1
"""


def test_split_tables_finds_titled_and_untitled_tables() -> None:
    first, second, *_ = split_tables(TWO_TABLES.splitlines())
    assert first.title == "Demo Info"
    assert first.header == ("ID   NAME",)
    assert first.rows == ("1    one", "2    two")
    assert second.has_columns("ID", "value")
    assert second.header == ("     SECOND", "ID   VALUE")
    assert second.rows == ("1    a",)


def test_columns_locates_repeated_labels_and_cuts_empty_cells() -> None:
    header = "PORT   NAME      PORT   DESCR"
    columns = Columns.locate(header, "PORT", "NAME", "PORT", "DESCR")
    assert columns.starts == (0, 7, 17, 24)
    assert columns.cut("1/1              1/9    some text") == ["1/1", "", "1/9", "some text"]


def test_cut_rows_joins_wrapped_port_lists() -> None:
    columns = Columns((0, 9, 31))
    rows = [
        "1        1/1-1/16,1/17/1-      1/1-1/16",
        "         1/18/4,2/1",
        "100      1/5                   1/5",
    ]
    assert columns.cut_rows(rows) == [
        ["1", "1/1-1/16,1/17/1-1/18/4,2/1", "1/1-1/16"],
        ["100", "1/5", "1/5"],
    ]


def test_gaps_keeps_rows_separated_by_one_blank_line() -> None:
    # Fabric Engine 9.x `show vlan members`: a blank line after every VLAN
    lines = ["VLAN PORT", "--------------------", "1", "", "4048", "", "", "Later text"]
    (default,) = split_tables(lines)
    (gapped,) = split_tables(lines, gaps=True)
    assert default.rows == ("1",)
    assert gapped.rows == ("1", "4048")


def test_columns_locates_labels_across_header_lines() -> None:
    # `show i-sid` on 9.x: ORIGIN on the first header line, NAME on the second
    header = (
        "ISID      ISID     PORT   ORIGIN      ISID",
        "ID        TYPE     IFS                NAME",
    )
    columns = Columns.locate(header, "ISID", "TYPE", "IFS", "ORIGIN", "NAME")
    assert columns.starts == (0, 10, 19, 26, 38)


def test_cut_takes_a_word_starting_one_left_of_its_header() -> None:
    # 9.x `show lldp neighbor summary`: SYSDESCR values start one position early
    columns = Columns.locate("SYSNAME    SYSDESCR", "SYSNAME", "SYSDESCR")
    assert columns.cut("fe-01     5520-24T (9.4.0.0)") == ["fe-01", "5520-24T (9.4.0.0)"]
    assert columns.cut("fe-01      5520-24T") == ["fe-01", "5520-24T"]
