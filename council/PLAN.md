# Plan

## Done: v0.1.0 (2026-11-21)

Core (cleanup, table splitter, columns, converters, registry) and twelve command
spellings with parsers, each checked against a fixture:

| Command | Record | Evidence |
|---|---|---|
| `show interfaces gigabitEthernet [interface]` | `PortInterface` | real (8.10 prod) |
| `show interfaces gigabitEthernet name` | `PortName` | shape only |
| `show interfaces gigabitEthernet state` | `PortState` | shape only |
| `show vlan basic` | `Vlan` | real (8.10 prod) |
| `show vlan members` | `VlanMembers` | shape only (+ doc-derived 9.x wrapping) |
| `show vlan i-sid` | `VlanIsid` | real (8.10 prod) |
| `show i-sid` | `Isid` | shape only |
| `show isis spbm i-sid all/config/discover` | `SpbmIsid` | shape only |
| `show mlt` | `Mlt` | real (8.10 prod) |
| `show virtual-ist` | `VirtualIst` | real (8.10 prod) |
| `show lldp neighbor summary` | `LldpNeighborSummary` | real (8.10 prod) |
| `show lldp neighbor` | `LldpNeighbor` | shape only |

## Next: lab capture on Fabric Engine 9.4 (needs the user)

`tools/capture.py` runs everything in `tools/capture_commands.txt`. That will:

1. **check the twelve parsers against 9.4.** Every "shape only" row becomes real or gets fixed.
2. **give us real output for the parsers still to write.** In order of what the backlog needs:

| Parser to write | Needed by |
|---|---|
| `show sys-info` (release, model, uptime) | all: every report says what it ran against |
| `show isis adjacencies`, `show isis interface` | #3 pre/post verification, L2 VSN verifier |
| `show vlan mac-address-entry` | #3 (MAC count before/after), #4 |
| `show ip route` + `vrf`, `show ip arp` + `vrf` | #3 |
| `show ip vrf`, `show ip interface` + `vrf` | #3, #4 |
| `show interfaces gigabitEthernet vlan` (tagging, default VLAN) | #4, L2 VSN builder |
| `show interfaces gigabitEthernet i-sid` | L2 VSN verifier |
| `show isis spbm`, `nick-name`, `unicast-fib` | L2 VSN verifier |
| `show lacp interface` | #3 |
| `show dvr ...` | only if DVR is used at work |

### What would make the lab capture most useful

The lab has two switches with IS-IS and LLDP. Tables with rows are worth far more than empty ones:

- an **MLT with LACP** between the two switches;
- two or three **VLANs with I-SIDs** (L2 VSNs), a port in each, and **one VLAN on many
  ports** so the member list wraps;
- one **VRF with an L3 VSN** and a static route, so `show ip route vrf` has content;
- a little **traffic** (VPCS hosts pinging each other), so the MAC table and ARP have entries;
- if possible, one capture *before* and one *after* a change. That is exactly what idea #3 compares.

## Later

- `show running-config` is a different shape (a config, not tables). It needs a parser
  for the config standards linter, and that needs its own decision.
- BOSS/ERS output (for #4, the migration assistant) is a different OS family. Not in
  this library unless the user decides otherwise.
- Captures from 8.10 and 9.3 at work would cover the mixed fleet. They can't come here
  (the repository is public and work output stays at work). An engineer can run
  `pytest` against them locally at work.
