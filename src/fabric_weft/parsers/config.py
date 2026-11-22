"""The configuration: `show running-config` (decision 0014)."""

from __future__ import annotations

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


def _is_comment(text: str) -> bool:
    return text.startswith("#")


def _context_openers(lines: Sequence[str]) -> set[int]:
    """Indexes of the lines that open a context: the first command of a run ending in `exit`.

    A run starts after the previous `exit`, comment or blank line. Blank lines directly
    before `exit` belong to the run (9.4 prints one there).
    """
    openers: set[int] = set()
    for end, line in enumerate(lines):
        if line.strip() != "exit":
            continue
        index = end - 1
        while index >= 0 and not lines[index].strip():
            index -= 1
        while index >= 0 and lines[index].strip() and not _is_comment(lines[index].strip()):
            if lines[index].strip() == "exit":
                break
            index -= 1
        if index + 1 < end and lines[index + 1].strip():
            openers.add(index + 1)
    return openers


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
    openers = _context_openers(body)

    section: str | None = None
    context: str | None = None
    for index, line in enumerate(body):
        text = line.strip()
        if not text:
            continue
        if _is_comment(text):
            section = _section_name(body, index) or section
            continue
        if text == "exit":
            if context is None:
                output.skip(line, "'exit' without a context to close")
            context = None
            continue
        if index in openers:
            yield ConfigCommand(section, None, text)
            context = text
            continue
        yield ConfigCommand(section, context, text)
    if context is not None:
        output.skip("", f"context {context!r} is not closed by 'exit'")
