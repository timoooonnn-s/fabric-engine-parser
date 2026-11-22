# 0013 · VLAN 0 in a VLAN cell means "no VLAN"

- **Status:** accepted, user may veto
- **Date:** 2026-11-22 · **Proposed by:** Claude, from the four-node 9.4 capture · **Objection:** none yet

Extends decision 0004.

## Decision

Where the switch prints `0` in a VLAN ID cell, the value is "no VLAN": a single VLAN ID
becomes `None`, a VLAN list becomes `()`. First used by `show interfaces gigabitEthernet
vlan` (DEFAULT VLANID `0` on a trunk, VLAN IDS `0` on an unused port).

## Why

0 is not a VLAN: 802.1Q reserves it for priority-tagged frames, and Fabric Engine
cannot configure it. Passing `0` through would make every caller test for it, and a
caller that forgets would count "member of VLAN 0" as a membership. This is the same
rule as the placeholders `-`, `N/A` and `NONE` becoming `None` in decision 0004.
