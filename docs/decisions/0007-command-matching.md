# 0007 · Commands are matched like the CLI matches them

- **Status:** accepted
- **Date:** 2026-11-21 · **Proposed by:** Bruno · **Objection:** none

## Decision

`parse(command, text)` finds the parser for the command as the caller typed it:

- every word may be abbreviated, case-insensitive (`sh int gig name`);
- words after the matched command are arguments and are ignored
  (`show interfaces gigabitEthernet name 1/1-1/4`, `show ip route vrf RED`);
- the longest registered command wins (`... name` beats the bare `... gigabitEthernet`);
- two different parsers matching equally → `UnknownCommandError` (ambiguous);
- one parser can register several spellings (`show interfaces gigabitEthernet` and
  `... interface` print the same table on different releases).

Each parser is also importable directly (`parse_mlts(text)`), for callers that want the
precise return type.

## Why

The calling tool already has the command string it sent to the switch. Making it
translate that string into a function name is busywork and a source of mismatches.
