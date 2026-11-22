# 0011 · A parser may say which arguments it accepts

- **Status:** accepted (user, 2026-11-22)
- **Date:** 2026-11-22 · **Proposed by:** Claude, from the four-node 9.4 capture · **Objection:** none yet

Extends decision 0007.

## Decision

`@parser(..., arguments=PATTERN)` names what may follow the command. The words after
the command must match the pattern, or the parser is not a candidate. Without
`arguments`, any words are accepted, as before.

The `show interfaces gigabitEthernet` parsers (bare, `interface`, `name`, `state`)
accept a port list (`values.PORT_LIST`, e.g. `1/1,1/3-1/4`).

## Why

Under 0007 alone, `show interfaces gigabitEthernet vlan` resolved to the bare
`show interfaces gigabitEthernet` parser, with `vlan` taken as an argument. That parser
then failed on a table it was never meant to read. The same happened with `i-sid` and
`l1-config`. Those are commands without a parser yet. They must raise
`UnknownCommandError` (and show up as skipped fixtures, the backlog), not be parsed as
something else.
