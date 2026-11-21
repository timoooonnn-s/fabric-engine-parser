"""The command output while it is being parsed: cleaned lines, tables and skipped lines."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Iterator
from typing import TypeVar

from fabric_weft.errors import DeviceError, ParseError
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


class Output:
    """Handed to every parser. Collects skipped lines; raises them in strict mode."""

    __slots__ = ("_tables", "command", "lines", "skipped", "strict")

    def __init__(self, command: str, text: str, *, strict: bool) -> None:
        self.command = command
        self.strict = strict
        self.lines = clean_lines(text)
        self.skipped: list[SkippedLine] = []
        self._tables: list[Table] | None = None
        self._raise_for_device_error()

    def _raise_for_device_error(self) -> None:
        """Fabric Engine prints errors as '% <message>', often under a '^' marker line."""
        for line in self.lines:
            text = line.strip()
            if not text or _ERROR_CARET.match(text):
                continue
            if text.startswith("%"):
                raise DeviceError(self.command, text.lstrip("% "))
            return

    @property
    def tables(self) -> list[Table]:
        if self._tables is None:
            self._tables = split_tables(self.lines)
        return self._tables

    def table(self, *labels: str, required: bool = True) -> Table | None:
        """The first table whose header has all labels. A missing required table is skipped."""
        found = first_with(self.tables, *labels)
        if found is None and required:
            self.skip("", f"no table with the columns {' '.join(labels)}")
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
                self.skip(row if isinstance(row, str) else "  ".join(map(str, row)), str(error))
