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
