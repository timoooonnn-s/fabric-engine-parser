"""Maps CLI commands to parsers, with the abbreviations the switch itself accepts."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any, Protocol, TypeVar

from fabric_weft.errors import UnknownCommandError
from fabric_weft.output import Output
from fabric_weft.result import ParseResult

RecordT_co = TypeVar("RecordT_co", covariant=True)


class Parser(Protocol[RecordT_co]):
    """A registered parser: raw command output in, `ParseResult` out."""

    commands: tuple[str, ...]

    def __call__(
        self, text: str, *, strict: bool = False, command: str | None = None
    ) -> ParseResult[RecordT_co]: ...


_PARSERS: dict[tuple[str, ...], Parser[Any]] = {}


def parser(*commands: str) -> Callable[[Callable[[Output], Iterable[Any]]], Parser[Any]]:
    """Register a record generator for one or more full command spellings.

    The decorated generator receives an `Output` and yields records. What the
    decorator returns is the public parser: `parse_x(text, strict=False)`.
    """

    def register(collect: Callable[[Output], Iterable[Any]]) -> Parser[Any]:
        def run(text: str, *, strict: bool = False, command: str | None = None) -> ParseResult[Any]:
            output = Output(command or commands[0], text, strict=strict)
            records = tuple(collect(output))
            return ParseResult(output.command, records, tuple(output.skipped))

        run.__name__ = run.__qualname__ = collect.__name__
        run.__doc__ = collect.__doc__
        run.__module__ = collect.__module__
        run.commands = commands  # type: ignore[attr-defined]
        for spelling in commands:
            _PARSERS[tuple(spelling.lower().split())] = run  # type: ignore[assignment]
        return run  # type: ignore[return-value]

    return register


def find_parser(command: str) -> Parser[Any]:
    """Resolve a command as typed, e.g. 'sh int gig name 1/1' or 'show ip route vrf RED'.

    Every word may be abbreviated. Words after the matched command are arguments
    (ports, VRF names) and are ignored. The longest matching command wins.
    """
    typed = command.lower().split()
    best: dict[int, Parser[Any]] = {}
    best_length = 0
    for words, run in _PARSERS.items():
        if len(words) > len(typed) or len(words) < best_length:
            continue
        if all(word.startswith(part) for word, part in zip(words, typed, strict=False)):
            if len(words) > best_length:
                best, best_length = {}, len(words)
            best[id(run)] = run
    if len(best) == 1:
        return next(iter(best.values()))
    problem = "is ambiguous" if best else "has no parser"
    raise UnknownCommandError(
        f"{command!r} {problem}; supported: {', '.join(supported_commands())}"
    )


def parse(command: str, text: str, *, strict: bool = False) -> ParseResult[Any]:
    """Parse the output of `command`. See `find_parser` for how commands are matched."""
    return find_parser(command)(text, strict=strict, command=command)


def supported_commands() -> list[str]:
    return sorted(" ".join(words) for words in _PARSERS)
