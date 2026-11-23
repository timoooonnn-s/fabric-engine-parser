# 0016 · A config context is opened by a known command, not found by layout

- **Status:** accepted, user may veto
- **Date:** 2026-11-22 · **Proposed by:** Claude, from the lab2 9.4 capture · **Objection:** none yet

Supersedes the "How a context is found" part of decision 0014. The record shape of 0014
(`ConfigCommand(section, context, command)`, commands kept as printed) stays.

## Decision

A context is opened by a command from a fixed list and closed by `exit`:

- `interface <kind> <id>` (GigabitEthernet, Vlan, mlt, loopback, …)
- `router isis|ospf|rip|bgp`, `router vrf <name>`
- `mgmt oob|clip`, `mgmt vlan <id>`
- `i-sid <id> elan`, `i-sid <id> elan-transparent`

Every other line is a top-level command, or part of the open context. Reported, never
guessed: an `exit` with no open context (a context opener missing from the list), a
comment or another opener while a context is open, and a context still open at the end.

## Why

0014 found a context as the run of lines ending in `exit`, starting after the last blank
line, comment or `exit`. lab2 fe-03 broke it: `interface Vlan 103` follows `vlan create`
lines with no blank line between, so `vlan create 20 …` was taken as the opener and eleven
commands got the wrong context, in strict mode, without a skipped line.

Without indentation, only the CLI grammar knows that `interface Vlan 103` opens a mode
and `vlan create 30` does not. A list taken from the captures is that knowledge; checked
on all eight 9.4 configs it gives exactly one context per `exit`. A mode the list does not
know yet surfaces as a reported line in strict mode, so the list grows from evidence.
