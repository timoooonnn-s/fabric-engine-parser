"""Exceptions raised by fabric_weft. All of them derive from `WeftError`."""


class WeftError(Exception):
    """Base class for every error this library raises."""


class UnknownCommandError(WeftError, LookupError):
    """No parser is registered for the command, or the abbreviation is ambiguous."""


class DeviceError(WeftError):
    """The switch answered with an error message instead of the command's output.

    Typical causes: a typo in the command, a command this release does not know,
    or an account without the privilege to run it (`% Invalid input detected`).
    """

    def __init__(self, command: str, message: str) -> None:
        super().__init__(f"{command!r}: switch reported: {message}")
        self.command = command
        self.message = message


class ParseError(WeftError, ValueError):
    """Strict mode only: a line could not be parsed or an expected table is missing."""

    def __init__(self, command: str, line: str, reason: str) -> None:
        super().__init__(f"{command!r}: {reason}: {line!r}")
        self.command = command
        self.line = line
        self.reason = reason
