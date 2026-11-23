# 0017 · A second record type from the same output gets its own, unregistered parser

- **Status:** accepted, user may veto
- **Date:** 2026-11-22 · **Proposed by:** Claude, from the lab4 9.4 capture · **Objection:** none yet

Extends decisions 0004 (a parser yields one record type) and 0007 (command matching).

## Decision

When one command prints two kinds of records, the second kind gets its own parser,
declared with `@parser(command, register=False)`. It is called directly
(`parse_lacp_aggregators(text)`); `parse(command, text)` keeps returning the first kind.
It is registered for a command of its own only once a capture of that command exists.

The fixture test checks it like any parser, in strict mode, against a second golden file
next to the capture: `<command>.<name>.json` (`show_lacp_interface.aggregators.json`),
listed in `ALSO_PARSED` in `tests/test_fixtures.py`.

First use: `show lacp interface` prints five tables per port (`LacpPort`) and four per MLT
(`LacpAggregator`).

## Why

- One record type per parser keeps `ParseResult` typed and simple for callers.
- Folding the aggregators into `LacpPort`, or both into one wrapper record, would change
  a published record for every caller to add data most of them do not need.
- `show lacp interface mlt` probably prints the aggregator tables alone, but no capture
  shows it. Registering the parser for it now would be the guess decision 0006 rules out.
