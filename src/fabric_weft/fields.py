"""Reads `Key : value` output, such as `show sys-info`, into named sections.

Fabric Engine prints these commands like this::

    General Info :                       <- section: not indented, ends with ':'
            SysName      : sw1           <- field: key, ':', value (may be empty)
            SysLocation  :
    Card Info :
            Slot#  CardType ...          <- lines without ':' (small tables) are ignored

Keys are kept as printed (inner spaces too), so a parser asks for exactly the key
the switch prints. Only the first colon splits, so values may contain colons
(`http://...`, `09:09:50`).
"""

from __future__ import annotations

import re
from collections.abc import Iterable

_FIELD = re.compile(r"\s*(?P<key>[^:]*?)\s*:\s*(?P<value>.*)")


def split_sections(lines: Iterable[str]) -> dict[str, dict[str, str]]:
    """Section name -> {key: value}. Fields before the first section go under ''.

    A key repeated within one section keeps its first value.
    """
    sections: dict[str, dict[str, str]] = {"": {}}
    current = sections[""]
    for line in lines:
        if not line.strip():
            continue
        if not line[0].isspace() and line.endswith(":"):
            current = sections.setdefault(line[:-1].strip(), {})
            continue
        found = _FIELD.fullmatch(line)
        if found and found["key"]:
            current.setdefault(found["key"], found["value"].strip())
    return sections
