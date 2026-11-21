"""Splits cleaned command output into tables.

Fabric Engine prints its tables like this::

    ==========================          <- title block (optional, one per command)
                Mlt Info
    ==========================
    MLTID IFINDEX NAME  ...             <- header: one or more lines
    --------------------------          <- dashed rule: header ends, rows start
    1   6144  MLT001  ...               <- rows, until a blank line, a rule or a footer
    All 8 out of 8 Total Num of mlt displayed

One command can print several tables (`show mlt` prints four), so parsers pick
the table they need by its column labels, never by position in the output.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

_RULE = re.compile(r"^\s*([=-])\1{9,}\s*$")
_FOOTER = re.compile(r"^\s*(?:All\s+)?\d+\s+out\s+of\s+\d+\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class Table:
    title: str
    header: tuple[str, ...]
    rows: tuple[str, ...]

    def has_columns(self, *labels: str) -> bool:
        """True when every label appears as a word in the header (case-insensitive)."""
        words = set(" ".join(self.header).upper().split())
        return all(label.upper() in words for label in labels)


def split_tables(lines: Iterable[str]) -> list[Table]:
    tables: list[Table] = []
    title = ""
    header: tuple[str, ...] = ()
    pending: list[str] = []  # non-blank lines since the last blank line or rule
    rows: list[str] | None = None  # None while not inside a table body

    for line in lines:
        rule = _RULE.match(line)
        if rows is not None:
            if line.strip() and not rule and not _FOOTER.match(line):
                rows.append(line)
                continue
            tables.append(Table(title, header, tuple(rows)))
            rows = None
            if not rule:
                pending = []
                continue
        if rule:
            if rule.group(1) == "=":
                if pending:
                    title = " ".join(text.strip() for text in pending)
            elif pending:
                header, rows = tuple(pending), []
            pending = []
        elif line.strip():
            pending.append(line)
        else:
            pending = []

    if rows is not None:
        tables.append(Table(title, header, tuple(rows)))
    return tables


@dataclass(frozen=True, slots=True)
class Columns:
    """Fixed-width columns, located by their labels in a header line.

    Used for tables whose cells may be empty or contain spaces, where splitting
    on whitespace cannot tell the columns apart (`show lldp neighbor summary`).
    """

    starts: tuple[int, ...]

    @classmethod
    def locate(cls, header_line: str, *labels: str) -> Columns:
        """Find each label left to right; repeated labels (two 'PORT's) are fine."""
        upper = header_line.upper()
        starts: list[int] = []
        position = 0
        for label in labels:
            found = re.compile(rf"(?<!\S){re.escape(label.upper())}(?!\S)").search(upper, position)
            if found is None:
                raise ValueError(f"column {label!r} not found in header {header_line!r}")
            starts.append(found.start())
            position = found.end()
        starts[0] = 0  # the first column always starts at the left margin
        return cls(tuple(starts))

    def cut(self, line: str) -> list[str]:
        ends = (*self.starts[1:], None)
        return [line[start:end].strip() for start, end in zip(self.starts, ends, strict=True)]

    def cut_rows(self, rows: Iterable[str]) -> list[list[str]]:
        """Cut every row and fold wrapped continuation lines into the row above.

        A continuation line has an empty first cell. Its cells are appended to
        the cells above: directly after a trailing ',' or '-' (a port list broken
        mid-list), otherwise separated by a space.
        """
        merged: list[list[str]] = []
        for cells in map(self.cut, rows):
            if cells[0] or not merged:
                merged.append(cells)
                continue
            above = merged[-1]
            for index, cell in enumerate(cells):
                if cell:
                    above[index] = _join_wrapped(above[index], cell)
        return merged


def _join_wrapped(head: str, tail: str) -> str:
    if not head or head.endswith((",", "-")):
        return head + tail
    return f"{head} {tail}"


def header_line_with(table: Table, label: str) -> str:
    """The header line that contains the label (for multi-line headers)."""
    for line in reversed(table.header):
        if label.upper() in line.upper().split():
            return line
    raise ValueError(f"column {label!r} not found in header of table {table.title!r}")


def first_with(tables: Sequence[Table], *labels: str) -> Table | None:
    return next((table for table in tables if table.has_columns(*labels)), None)
