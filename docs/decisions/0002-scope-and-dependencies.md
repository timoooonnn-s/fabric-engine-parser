# 0002 · Text in, records out. Standard library only.

- **Status:** accepted
- **Date:** 2026-11-21 · **Proposed by:** Ines · **Objection:** none

## Decision

1. The library takes the text of a command's output and returns records. It never
   opens a connection. Getting the text is the calling tool's job (netmiko).
2. **No runtime dependencies.** Only the standard library.
3. **Python 3.10 or newer.** The work server runs 3.11. 3.10 is the floor so the Mac
   and older tools can use it too. It costs nothing: `slots=True` dataclasses and
   `X | None` are both 3.10.
4. Development extras: `pytest`, `ruff`. The capture tool needs `netmiko`
   (`pip install '.[capture]'`); the library never imports it.

## Why

- The user asked for "whatever is most efficient, uses the least lines, works best
  and is the fastest". A connection helper would be one line
  (`parse(command, connection.send_command(command))`) wrapped in a dependency
  every caller already has, and it would tie this library to netmiko's versions.
- Every pip package on the work server is a review and a thing that can break on
  patch day. A parser needs `re` and `dataclasses`, nothing else.
