"""Converters from the raw text of one table cell to a Python value.

Every converter raises `ValueError` on input it does not understand. The parser
then reports the whole line as skipped (or raises `ParseError` in strict mode),
so an unknown value never turns silently into a wrong one.
"""

from __future__ import annotations

import re
from datetime import datetime

# Placeholders Fabric Engine prints for "no value".
_EMPTY_MARKERS = frozenset({"", "-", "--", "n/a", "none"})

_TRUE_WORDS = frozenset({"true", "enable", "enabled", "up", "yes"})
_FALSE_WORDS = frozenset({"false", "disable", "disabled", "down", "no"})

# slot/port or slot/port/sub-port (channelized). A pattern string, for use inside row patterns.
PORT = r"\d+/\d+(?:/\d+)?"
_PORT = re.compile(PORT)
_MAC_DIGITS = re.compile(r"[0-9a-f]{12}")


def optional(cell: str) -> str | None:
    """Return the cell, or None for a placeholder such as '-', '--', 'N/A' or 'NONE'."""
    cell = cell.strip()
    return None if cell.lower() in _EMPTY_MARKERS else cell


def optional_int(cell: str) -> int | None:
    value = optional(cell)
    return None if value is None else int(value)


def flag(cell: str) -> bool:
    """'true'/'enable'/'up' -> True, 'false'/'disable'/'down' -> False."""
    word = cell.strip().lower()
    if word in _TRUE_WORDS:
        return True
    if word in _FALSE_WORDS:
        return False
    raise ValueError(f"not a true/false value: {cell!r}")


def mac(cell: str) -> str:
    """Normalise any common MAC notation to lower-case 'aa:bb:cc:dd:ee:ff'."""
    digits = re.sub(r"[:.\-]", "", cell.strip().lower())
    if not _MAC_DIGITS.fullmatch(digits):
        raise ValueError(f"not a MAC address: {cell!r}")
    return ":".join(digits[i : i + 2] for i in range(0, 12, 2))


def int_list(cell: str) -> tuple[int, ...]:
    """'174 695 696' -> (174, 695, 696); empty -> ()."""
    return tuple(int(token) for token in cell.split())


def ports(cell: str) -> tuple[str, ...]:
    """Expand a Fabric Engine port list into single ports.

    '1/1-1/3,1/10'   -> ('1/1', '1/2', '1/3', '1/10')
    '1/17/1-1/17/4'  -> ('1/17/1', '1/17/2', '1/17/3', '1/17/4')
    'NONE', '-', ''  -> ()

    See docs/decisions/0008-port-lists.md for the channelized-range rule and why
    a range across slots is rejected instead of guessed.
    """
    if optional(cell) is None:
        return ()
    expanded: list[str] = []
    for chunk in filter(None, cell.strip().split(",")):
        first, _, last = chunk.partition("-")
        expanded.extend(_port_range(first, last) if last else (port(first),))
    return tuple(expanded)


def port(cell: str) -> str:
    """Validate a single port such as '1/1' or '1/17/2'."""
    cell = cell.strip()
    if not _PORT.fullmatch(cell):
        raise ValueError(f"not a port: {cell!r}")
    return cell


def _port_range(first: str, last: str) -> list[str]:
    start = [int(part) for part in port(first).split("/")]
    end = [int(part) for part in port(last).split("/")]
    if len(start) != len(end) or start[0] != end[0] or start > end:
        raise ValueError(f"port range cannot be expanded: {first}-{last}")
    slot = start[0]
    if len(start) == 2:
        return [f"{slot}/{port}" for port in range(start[1], end[1] + 1)]
    # Channelized range. When it spans several parent ports, the last sub-port
    # of the range is taken as the channel count (decision 0008).
    channels = end[2]
    if start[2] > channels:
        raise ValueError(f"port range cannot be expanded: {first}-{last}")
    return [
        f"{slot}/{parent}/{sub}"
        for parent in range(start[1], end[1] + 1)
        for sub in range(
            start[2] if parent == start[1] else 1,
            (end[2] if parent == end[1] else channels) + 1,
        )
    ]


def timestamp(cell: str, layout: str = "%m/%d/%y %H:%M:%S") -> datetime | None:
    """Parse a switch timestamp (no time zone information is printed)."""
    value = optional(cell)
    return None if value is None else datetime.strptime(value, layout)
