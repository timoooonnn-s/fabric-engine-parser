# 0003 · Own table splitter plus row patterns, not TextFSM or TTP

- **Status:** accepted
- **Date:** 2026-11-21 · **Proposed by:** Ines · **Objection:** Bruno

## Decision

Parsing has three layers:

1. **Clean** (`output.py`): unify CR/LF, strip ANSI codes and tabs, drop the
   `Command Execution Time` banner, and raise `DeviceError` on a `% ...` message.
2. **Split** (`tables.py`): cut the output into `Table`s (title, header lines, rows)
   at the `====` and `----` rules. One command can print several tables, and a
   parser picks its table **by column labels**, never by position.
3. **Read rows**, one of two ways per table:
   - a **row pattern** (regex, anchored on values whose format is known) when every
     cell is one word or the free-text cell can be pinned between known neighbours;
   - **`Columns`**, cut at the header positions, when cells can be empty or contain
     spaces (`show lldp neighbor summary`). `Columns.cut_rows` also joins wrapped
     continuation lines.

## Why

- Real captures break naïve approaches in ways a template language handles badly:
  - MLT names wider than their column shift every later column (`MLT001.svi.108.116`),
    so fixed positions fail and a pattern anchored on `trunk|access` works.
  - Long VLAN ID lists wrap onto a new line that **starts at column 0** and looks like a new row.
  - `show vlan members` wraps port lists *under their own column*, broken after `,` or
    inside a range (`1/17/1-` / `1/18/4`).
  - `show mlt` prints four tables that only together describe one MLT.
- TextFSM (and the ntc-templates collection) would be a dependency, has few
  Fabric Engine templates, and is a state machine in a separate language: a reader
  has to know two languages to follow one parser.
- Speed: one pass over the lines, precompiled patterns. Measured on 2026-11-21:
  the 54-port interface table parses in about 0.3 ms, `show mlt` in about 0.15 ms.
  For 300 switches that's well under a second, far less than the SSH round trips.

## Objection

*Bruno:* "With TextFSM we would get community templates for free." There are almost
none for Fabric Engine, and the ones there are don't handle the wrapping cases above.
If that changes, a parser can wrap a template behind the same `@parser` interface
without breaking a caller.
