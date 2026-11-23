"""Converters from the raw text of one table cell to a Python value.

Every converter raises `ValueError` on input it does not understand. The parser
then reports the whole line as skipped (or raises `ParseError` in strict mode),
so an unknown value never turns silently into a wrong one.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import TypeVar

# Placeholders Fabric Engine prints for "no value".
_EMPTY_MARKERS = frozenset({"", "-", "--", "n/a", "none"})

_TRUE_WORDS = frozenset({"true", "enable", "enabled", "up", "yes"})
_FALSE_WORDS = frozenset({"false", "disable", "disabled", "down", "no"})

# slot/port or slot/port/sub-port (channelized). A pattern string, for use inside row patterns.
PORT = r"\d+/\d+(?:/\d+)?"
_PORT = re.compile(PORT)
# The front port in an interface name: 'Port1/1' (IS-IS), 'Port-1/1' (FDB), '1/1' (SPBM FIB).
_INTERFACE_PORT = re.compile(rf"(?:Port-?)?(?P<port>{PORT})")
# '1/1', '1/1-1/4,2/1': a port list as typed after a command.
PORT_LIST = rf"{PORT}(?:-{PORT})?(?:,{PORT}(?:-{PORT})?)*"
_MAC_DIGITS = re.compile(r"[0-9a-f]{12}")
# IS-IS system ID 'xxxx.xxxx.xxxx' and SPBM nickname 'x.xx.xx'. Pattern strings, for row patterns.
SYSTEM_ID = r"[0-9a-f]{4}\.[0-9a-f]{4}\.[0-9a-f]{4}"
NICKNAME = r"[0-9a-f]\.[0-9a-f]{2}\.[0-9a-f]{2}"
_SYSTEM_ID = re.compile(SYSTEM_ID)
_NICKNAME = re.compile(NICKNAME)
_DURATION = re.compile(r"(?:(?P<days>\d+) days?(?:\(s\))?,\s*)?(?P<h>\d+):(?P<m>\d\d):(?P<s>\d\d)")


def optional(cell: str) -> str | None:
    """Return the cell, or None for a placeholder such as '-', '--', 'N/A' or 'NONE'."""
    cell = cell.strip()
    return None if cell.lower() in _EMPTY_MARKERS else cell


ValueT = TypeVar("ValueT")


def optional_as(convert: Callable[[str], ValueT], cell: str) -> ValueT | None:
    """Convert the cell, or None for a placeholder: optional_as(mac, '-') -> None."""
    value = optional(cell)
    return None if value is None else convert(value)


def optional_int(cell: str) -> int | None:
    return optional_as(int, cell)


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


def port_of(interface: str) -> str | None:
    """The front port an interface name refers to, None for anything else.

    'Port1/1', 'Port-1/1', '1/1' -> '1/1'; 'Port-cpp', 'cpp', 'Mlt2' -> None. Other
    interface kinds keep their name in the record until a capture shows their form.
    """
    found = _INTERFACE_PORT.fullmatch(interface.strip())
    return found["port"] if found else None


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


def duration(cell: str) -> timedelta:
    """'3 day(s), 04:05:06' (sys-info uptime) or '00:04:03' (IS-IS uptime) -> timedelta."""
    found = _DURATION.fullmatch(cell.strip())
    if found is None:
        raise ValueError(f"not a duration: {cell!r}")
    return timedelta(
        days=int(found["days"] or 0),
        hours=int(found["h"]),
        minutes=int(found["m"]),
        seconds=int(found["s"]),
    )


def system_id(cell: str) -> str:
    """Validate an IS-IS system ID such as '0c91.dc31.0084' (kept as printed, decision 0004)."""
    cell = cell.strip()
    if not _SYSTEM_ID.fullmatch(cell):
        raise ValueError(f"not a system ID: {cell!r}")
    return cell


def nickname(cell: str) -> str | None:
    """Validate an SPBM nickname such as '0.00.12'. Empty (no nickname) -> None."""
    value = optional(cell)
    if value is not None and not _NICKNAME.fullmatch(value):
        raise ValueError(f"not an SPBM nickname: {cell!r}")
    return value
