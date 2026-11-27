"""The command output while it is being parsed: cleaned lines, tables and skipped lines."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Iterator
from typing import TypeVar

from fabric_weft.errors import DeviceError, ParseError
from fabric_weft.fields import split_sections
from fabric_weft.result import SkippedLine
from fabric_weft.tables import Table, first_with, split_tables

RowT = TypeVar("RowT")
RecordT = TypeVar("RecordT")

_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
# The '****' block with 'Command Execution Time' that releases print above the output.
_EXECUTION_BANNER = re.compile(r"^\s*(?:\*{10,}|Command Execution Time:.*)$")
_ERROR_CARET = re.compile(r"^\s*\^\s*$")


def clean_lines(text: str) -> list[str]:
    """Line-split netmiko output: CR/LF unified, ANSI codes, tabs and the banner removed."""
    text = _ANSI_ESCAPE.sub("", text).replace("\r\n", "\n").replace("\r", "\n")
    return [
        line.expandtabs(8).rstrip()
        for line in text.split("\n")
        if not _EXECUTION_BANNER.match(line)
    ]


def fullmatch(pattern: re.Pattern[str], line: str) -> re.Match[str]:
    """Match a whole row (surrounding whitespace ignored) or raise ValueError."""
    found = pattern.fullmatch(line.strip())
    if found is None:
        raise ValueError("line does not have the expected format")
    return found


def _as_line(row: object) -> str:
    """A row for a skipped-line report: as printed, or its cut cells joined again."""
    if isinstance(row, str):
        return row
    if isinstance(row, Iterable):
        return "  ".join(map(str, row))
    return str(row)


class Output:
    """Handed to every parser. Collects skipped lines; raises them in strict mode."""

    __slots__ = ("_sections", "_tables", "command", "lines", "skipped", "strict")

    def __init__(self, command: str, text: str, *, strict: bool) -> None:
        self.command = command
        self.strict = strict
        self.lines = clean_lines(text)
        self.skipped: list[SkippedLine] = []
        self._tables: list[Table] | None = None
        self._sections: dict[str, dict[str, str]] | None = None
        self._raise_for_device_error()

    def _raise_for_device_error(self) -> None:
        """Fabric Engine prints errors as '% <message>' (often under a '^' marker line) or,
        for some commands, as 'Error: <message>' ('show ip route vrf X' for an unknown VRF).

        A '%' line is looked for over the WHOLE output, not just at the top. A command
        with arguments is answered in parts - `show interfaces gigabitEthernet name
        1/1-1/60` on a 48-port box prints the ports it has and THEN refuses the rest -
        and stopping at the first line of real output meant that refusal was neither
        raised nor skipped: the caller got `complete=True` over a table that is missing
        everything after the error. No real capture has a '%' line inside its output,
        which is what makes scanning for one safe.

        'Error:' stays a leading-line rule: unlike '%' it is ordinary English and could
        begin a line of someone's interface description in `show running-config`.
        """
        leading = True
        for line in self.lines:
            text = line.strip()
            if not text or _ERROR_CARET.match(text):
                continue
            if text.startswith("%"):
                raise DeviceError(self.command, text.lstrip("% "))
            if leading and text.startswith("Error:"):
                raise DeviceError(self.command, text.removeprefix("Error:").strip())
            leading = False

    @property
    def tables(self) -> list[Table]:
        if self._tables is None:
            self._tables = split_tables(self.lines)
        return self._tables

    def table(
        self, *labels: str, required: bool = True, gaps: bool = False, title: str | None = None
    ) -> Table | None:
        """The first table whose header has all labels. A missing required table is skipped.

        gaps=True: rows may be separated by single blank lines (see `split_tables`).
        title: only tables with this title (case-insensitive), for commands that print
        several tables with the same header (`show lacp interface`).
        """
        tables = split_tables(self.lines, gaps=True) if gaps else self.tables
        if title is not None:
            tables = [table for table in tables if table.title.lower() == title.lower()]
        found = first_with(tables, *labels)
        if found is None and required:
            where = f" titled {title!r}" if title else ""
            self.skip("", f"no table{where} with the columns {' '.join(labels)}")
        return found

    def section(self, name: str, *, required: bool = True) -> dict[str, str] | None:
        """The `Key : value` fields under a section header such as 'General Info :'.

        A missing required section is skipped, like a missing table.
        """
        if self._sections is None:
            self._sections = split_sections(self.lines)
        found = self._sections.get(name)
        if found is None and required:
            self.skip("", f"no section {name!r}")
        return found

    def skip(self, line: str, reason: str) -> None:
        if self.strict:
            raise ParseError(self.command, line, reason)
        self.skipped.append(SkippedLine(line, reason))

    def build_each(
        self, rows: Iterable[RowT], build: Callable[[RowT], RecordT]
    ) -> Iterator[RecordT]:
        """Build one record per row. A row whose build raises ValueError is skipped."""
        for row in rows:
            try:
                yield build(row)
            except ValueError as error:
                self.skip(_as_line(row), str(error))
