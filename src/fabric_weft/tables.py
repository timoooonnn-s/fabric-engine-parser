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


def split_tables(lines: Iterable[str], *, gaps: bool = False) -> list[Table]:
    """Cut the lines into tables. A blank line normally ends a table body.

    gaps=True: a single blank line between rows does not end the body, two in a
    row do. Fabric Engine 9.x prints `show vlan members` with a blank line after
    every VLAN. Only for tables known to do that: after a single blank line the
    header of a following table would otherwise be read as rows.
    """
    tables: list[Table] = []
    title = ""
    header: tuple[str, ...] = ()
    pending: list[str] = []  # non-blank lines since the last blank line or rule
    rows: list[str] | None = None  # None while not inside a table body
    gap = False  # the previous line was a blank line inside a body (gaps=True)

    for line in lines:
        rule = _RULE.match(line)
        if rows is not None:
            if line.strip() and not rule and not _FOOTER.match(line):
                rows.append(line)
                gap = False
                continue
            if gaps and not line.strip() and not gap:
                gap = True
                continue
            gap = False
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
    def locate(cls, header: str | Sequence[str], *labels: str) -> Columns:
        """Find each label left to right; repeated labels (two 'PORT's) are fine.

        `header` is one header line, or all of them: then each label is taken from
        whichever line has it first after the previous label (a two-line header
        such as `show i-sid` puts ORIGIN on the first line, NAME on the second).
        """
        lines = [header] if isinstance(header, str) else list(header)
        uppers = [line.upper() for line in lines]
        starts: list[int] = []
        position = 0
        for label in labels:
            pattern = re.compile(rf"(?<!\S){re.escape(label.upper())}(?!\S)")
            matches = [m for upper in uppers if (m := pattern.search(upper, position))]
            if not matches:
                raise ValueError(f"column {label!r} not found in header {lines!r}")
            found = min(matches, key=lambda match: match.start())
            starts.append(found.start())
            position = found.end()
        starts[0] = 0  # the first column always starts at the left margin
        return cls(tuple(starts))

    def cut(self, line: str) -> list[str]:
        """Cut a line at the column starts.

        A word that begins one character left of its column header belongs to that
        column: 9.x `show lldp neighbor summary` prints SYSDESCR values one position
        left of the header, which would otherwise cut '5520-24T' into '5' + '520-24T'.
        """
        starts = [self._start_in(line, start) for start in self.starts]
        ends = (*starts[1:], None)
        return [line[start:end].strip() for start, end in zip(starts, ends, strict=True)]

    @staticmethod
    def _start_in(line: str, start: int) -> int:
        if (
            2 <= start < len(line)
            and line[start - 2] == " "
            and " " not in line[start - 1 : start + 1]
        ):
            return start - 1
        return start

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
