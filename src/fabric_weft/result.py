"""What every parser returns."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import asdict, dataclass
from typing import Any, Generic, TypeVar

RecordT = TypeVar("RecordT")


@dataclass(frozen=True, slots=True)
class SkippedLine:
    """A line the parser could not read, and why. Empty line = a missing table."""

    line: str
    reason: str


@dataclass(frozen=True, slots=True)
class ParseResult(Generic[RecordT]):
    """The records of one command's output, plus every line that was skipped.

    Iterating the result iterates the records, so `for mlt in parse(...)` works.
    """

    command: str
    records: tuple[RecordT, ...]
    skipped: tuple[SkippedLine, ...] = ()

    def __iter__(self) -> Iterator[RecordT]:
        return iter(self.records)

    def __len__(self) -> int:
        return len(self.records)

    @property
    def complete(self) -> bool:
        """True when no line was skipped."""
        return not self.skipped

    def as_dicts(self) -> list[dict[str, Any]]:
        """The records as plain dicts (nested records become dicts as well)."""
        return [asdict(record) for record in self.records]  # type: ignore[call-overload]
