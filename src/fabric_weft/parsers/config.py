"""The configuration: `show running-config` (decisions 0014, 0016)."""

from __future__ import annotations

import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from fabric_weft.output import Output
from fabric_weft.registry import parser


@dataclass(frozen=True, slots=True)
class ConfigCommand:
    """One configuration command, exactly as printed, with where it stands."""

    section: str | None  # the '# ... #' block above it, e.g. 'ISIS SPBM CONFIGURATION'
    context: str | None  # the line that opened its context, e.g. 'router isis'; None at top level
    command: str


# Commands that open a context, closed again by `exit` (decision 0016). Fabric Engine
# prints no indentation, so only the command itself says that it opens a context.
# From the 9.4 captures; a context opener not in this list shows up as a reported
# "'exit' without a context to close", never as a silent misread.
_OPENER = re.compile(
    r"interface \S+ \S+"
    r"|router (?:isis|ospf|rip|bgp|vrf \S+)"
    r"|mgmt (?:oob|clip|vlan \d+)"
    r"|i-sid \d+ elan(?:-transparent)?"
)


def _is_comment(text: str) -> bool:
    return text.startswith("#")


def _section_name(lines: Sequence[str], index: int) -> str | None:
    """'# NAME' between two lines that are only '#' -> 'NAME'."""
    text = lines[index].strip()
    if not text.startswith("# ") or index == 0 or index + 1 >= len(lines):
        return None
    if lines[index - 1].strip() == "#" and lines[index + 1].strip() == "#":
        return text[1:].strip()
    return None


@parser("show running-config")
def parse_running_config(output: Output) -> Iterator[ConfigCommand]:
    """`show running-config` -> one ConfigCommand per command, in the order printed."""
    lines = output.lines
    try:
        start = lines.index("config terminal") + 1
    except ValueError:
        output.skip("", "no 'config terminal' line")
        return
    end = next((index for index in range(start, len(lines)) if lines[index] == "end"), None)
    if end is None:
        output.skip("", "no 'end' line: the output looks cut off")
        end = len(lines)
    body = lines[start:end]

    section: str | None = None
    context: str | None = None
    for index, line in enumerate(body):
        text = line.strip()
        if not text:
            continue
        if _is_comment(text):
            if context is not None:
                output.skip(line, f"context {context!r} is not closed by 'exit'")
                context = None
            section = _section_name(body, index) or section
            continue
        if text == "exit":
            if context is None:
                output.skip(line, "'exit' without a context to close")
            context = None
            continue
        if _OPENER.fullmatch(text):
            if context is not None:
                output.skip(line, f"context {context!r} is not closed by 'exit'")
            yield ConfigCommand(section, None, text)
            context = text
            continue
        yield ConfigCommand(section, context, text)
    if context is not None:
        output.skip("", f"context {context!r} is not closed by 'exit'")
