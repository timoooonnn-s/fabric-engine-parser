# 0012 · A value one character left of its column header belongs to that column

- **Status:** accepted (user, 2026-11-22)
- **Date:** 2026-11-22 · **Proposed by:** Claude, from the four-node 9.4 capture · **Objection:** none yet

Extends decision 0003.

## Decision

When `Columns.cut` finds a word that starts exactly one position left of a column start
(a space before it, no space at the boundary), the cut moves one position left. Every
other cut stays where the header says.

## Why

9.4 `show lldp neighbor summary` pads SYSNAME one character shorter than its header,
so every SYSDESCR starts one position early. A strict cut gave `system_name='fe-01 … 5'`
and `system_description='520-24T-FabricEngine (9.4.0.0)'`, with no skipped line.

The rule only moves a cut when a word straddles it by exactly one character, which a
correctly aligned table never does. With the rule in place, every other column-cut
golden file (8.10 production LLDP summary, VLAN members, VLAN I-SID, port names,
`show i-sid`, SPBM I-SIDs) came out unchanged.
