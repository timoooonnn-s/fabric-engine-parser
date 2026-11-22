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

## Done since: first 9.4 capture (`fe-9.4-gns3-sw1`, 2026-11-21)

A single lab switch, a few minutes after boot: no IS-IS neighbour, no nickname, no MLT,
no ports in VLANs. Ten commands were rejected, most likely because the capture ran in
user mode (not confirmed).

- Fixed for 9.4: `show i-sid` (VLANID column, ORIGIN as flag slots), `show isis spbm
  i-sid` (empty nickname, ISID NAME and AREA columns), `show vlan basic` (L3 ACCESS),
  `show vlan i-sid` (VLAN NAME), `show vlan members` (blank line after every VLAN).
- New parser: `show sys-info` → `SysInfo` (decision 0009).
- Empty `show mlt` and `show virtual-ist` kept as fixtures on purpose (decision 0010).
- `tools/capture.py` now enters privileged mode and captures several switches per run.

## Done since: four-node 9.4 capture (`fe-9.4-gns3-fe-01` … `fe-04`, 2026-11-22)

Four access nodes, IS-IS adjacencies between them, CVLAN I-SIDs with access ports,
captured in privileged mode. All 40 commands saved on every node.

- Every existing parser now has real 9.4 evidence except `show mlt` and `show virtual-ist`
  (no MLT, no vIST in the lab; empty on purpose).
- Fixed for 9.4: `show i-sid` CVLAN ports (`vlan_member_ports`), port names (no LINKTRAP,
  new VLAN column), port state (new FA/Flex UNI column; the date was lost before),
  `show lldp neighbor` (no Time, padded keys; it returned nothing before), LLDP summary
  (SYSDESCR one position left of its header, decision 0012).
- `show interfaces gigabitEthernet vlan|i-sid|l1-config` no longer resolve to the bare
  command (decision 0011).
- `show lldp neighbor` now checks its block count against `Total Neighbors`.

## Done: IS-IS (2026-11-22)

`show isis adjacencies` → `IsisAdjacency`, `show isis interface` → `IsisInterface`, real
9.4 evidence on all four nodes (sw1's empty tables kept as empty-on-purpose fixtures).

## Done: MAC table (2026-11-22)

`show vlan mac-address-entry` → `MacEntry`, real 9.4 evidence on all five lab captures
(76 entries). They are all the switches' own B-VLAN entries (`self`, `Port-cpp` or a
fabric port, no tunnel). **No end-device MAC was learned**, so entries learned on an
access port or through the fabric (other statuses, a tunnel) are still unseen: the
parser keeps those words as printed. A capture after the end devices send traffic
would close that gap, and it is exactly what idea #3 counts before and after a change.

## Done: SPBM nicknames and unicast FIB (2026-11-22)

`show isis spbm nick-name` → `SpbmNickname`, `show isis spbm unicast-fib` →
`SpbmUnicastRoute`, real 9.4 evidence on all five lab captures (85 entries). Both carry
`system_id`, so adjacencies, nicknames, FIB entries and SPBM I-SIDs join on one key.
System ID and nickname checks now live in `values.py` (`system_id`, `nickname`).

## Done: port VLAN settings (2026-11-22)

`show interfaces gigabitEthernet vlan` → `PortVlans`, real 9.4 evidence on fe-01 … fe-04
(104 ports). VLAN `0` reads as "no VLAN" (decision 0013). A column label the parser
cannot find is now reported as a skipped line (strict: `ParseError`), no longer a bare
`ValueError` (decision 0005). Still unseen: a VLAN list long enough to wrap.

## Done: port I-SID endpoints (2026-11-22)

`show interfaces gigabitEthernet i-sid` → `PortIsid`, real 9.4 evidence on fe-01 … fe-04
(8 endpoints, the same port/I-SID pairs `show i-sid` lists). Only CVLAN endpoints so
far: an ELAN (Switched UNI) endpoint with a customer VID, and a BPDU value, are unseen.

## Done: VRFs (2026-11-22)

`show ip vrf` → `Vrf`, real 9.4 evidence on all five lab captures (GlobalRouter and
MgmtRouter only). The summary table above the per-VRF table is not read. A VRF created
by hand (CONFIG origin, an L3 VSN) is still unseen.

## Done: LACP per port (2026-11-22)

`show lacp interface` → `LacpPort`, merged from the five per-port tables (three share a
header and are picked by title), real 9.4 evidence on all five lab captures (130 ports).
LACP is disabled everywhere in the lab, so every value is a default and every partner
is empty. The LACP Aggregator tables (per MLT) are not read: no capture has rows yet.

## Done: installed software (2026-11-22)

`show software` → `Software`, real 9.4 evidence on all five lab captures (one release
each). A switch with a backup release next to the primary is still unseen; the labels
are kept as printed.

## Done: IS-IS system ID (2026-11-22)

`show isis system-id` → `IsisSystemId` (HOME and REMOTE), real 9.4 evidence on all five
lab captures. The HOME ID is each switch's entry in its neighbours' adjacencies and in
the LSDB, so a report can name "this switch" in IS-IS output.

## Done: the rest of the four-node capture (2026-11-22)

`show isis` → `IsisSettings`, `show isis lsdb` → `IsisLsp`, `show isis spbm` →
`SpbmInstance` (three tables merged), `show interfaces gigabitEthernet l1-config` →
`PortL1Config`. Real 9.4 evidence on all five lab captures (l1-config: fe-01 … fe-04).
Units in `IsisSettings` field names (seconds, `spf_delay_ms`) follow the IS-IS defaults
the switch prints (900, 10, 2, 5, 100); the output itself names no unit.

## Next: needs a new capture

Every captured command with rows now has a parser.
Captured but empty in this lab: `show dvr`, `dvr interfaces`, `dvr members`,
`show smlt mlt`, `show ipv6 route`.

Still without rows, so still waiting for a lab change: `show ip route` / `arp` /
`interface` (no L3 in the lab), `show mlt` / `virtual-ist` with an MLT,
and a VLAN on enough ports that `show vlan members` wraps.

### What would make the lab capture most useful

Tables with rows are worth far more than empty ones. Still missing from the four-node lab:

- an **MLT with LACP** between two nodes;
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
