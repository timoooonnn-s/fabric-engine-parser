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

## Done: running-config (2026-11-22)

`show running-config` → `ConfigCommand(section, context, command)`, decision 0014. Real
9.4 evidence on fe-01 … fe-04 (136–138 commands each, every command in order, every
context closed where the capture's `exit` is). Commands are not interpreted; that is the
config linter's job. Still unseen: nested contexts.

## Done: lab2 capture (2026-11-22)

Real 9.4 evidence for L3 and the shapes lab 1 could not show. New parsers: `show ip route`
→ `IpRoute`, `show ip arp` → `ArpEntry`, `show ip interface` → `IpInterface` (each with the
VRF from the table title, with and without `vrf X`).

Fixed because of it:
- `show running-config` gave eleven commands the wrong context when `interface Vlan X`
  follows `vlan create` lines (decision 0016 replaces the layout rule of 0014).
- `show interfaces gigabitEthernet vlan`: a long VLAN list overflows its column instead of
  wrapping; read with a row pattern now. The wrap test was a guess and is gone.
- `show mlt` on 9.4: ORIGIN column, designated port `null`, empty member lists, PVLAN `-`.
- `Error: …` answers (unknown VRF) are a `DeviceError` now, like `% …`; the capture tool
  rejects them instead of saving them.
- `tools/capture.py`: fixed prompt pattern, buffer cleared and empty output retried, one
  lost command no longer loses the rest of the switch.

Seen for the first time and reading correctly: wrapped `show vlan members` lists, `c100:1/8`
I-SID bindings, an ELAN endpoint with a customer VID, MACs learned through the fabric
(`tunnel`), routes over IS-IS with a BEB host name as next hop.

## Done: lab3 capture (2026-11-22)

fe-01 and fe-02 with 1/5–1/7 cabled. Fixed: `show i-sid` on 9.4 prints a further binding
of an I-SID on its own line (`u:1/7` under `c100:1/8`); it was read as a broken row.
`PortIsid` gets `untagged_traffic` (C-VID printed `untag`), so an untagged endpoint is not
confused with a CVLAN one (`N/A`). ELAN 30100 is advertised now that 1/7 is up.

MLT 10 is still empty: 1/5–1/6 are up (LLDP sees fe-02) and LACP is configured on them,
but `# LACP CONFIGURATION` has no global `lacp enable`, so LACP is not running.

## Done: lab4 capture and LACP aggregators (2026-11-22)

Global `lacp enable` brought MLT 10 up (members 1/5–1/6, partner the other switch,
port state `act short aggr sync col dis`). New: `parse_lacp_aggregators` →
`LacpAggregator`, one per MLT with LACP, from the four aggregator tables of
`show lacp interface`; a second, unregistered parser for the same output (decision 0017).
Checked against `show mlt` on every capture.

## Done: lab5 capture (2026-11-22)

fe-01 and fe-02 with VLAN 50 on MLT 10, untagged: a LACP MLT carrying a VLAN. Read without
a change; the only differences to lab4 are VLAN 50 on the MLT, its ports and its members.

## Done: lab6 capture, build 2 (2026-11-22)

All four nodes rebuilt from `tools/lab/`. New: `show smlt mlt` → `SmltMlt`. First trunk LACP
MLT, first SMLT (admin `smlt`), routes over IP shortcuts on every node, ARP over the fabric
(`tunnel`). No parser change was needed for any of it. Not reached: the vIST (no `[new]`
line took) and SMLT 20 to fe-03 (a leftover cable); fixes in `tools/lab/README.md`.

## Next: finish build 2 (vIST, SMLT to fe-03), capture as lab7

The lab is rebuilt clean from `tools/lab/fe-0X.cli` (cabling, order and checks in
`tools/lab/README.md`), then captured as `fe-9.4-gns3-lab6-*` on all four nodes with
`--vrf blue`. It adds what no capture has yet: vIST (fe-01/fe-02), SMLT 20 with LACP to
fe-03, a trunk LACP MLT (MLT 10, encapsulation before LACP), CLIPs and IP shortcuts on all
four nodes, and VRF `blue` on an MLT-carried VLAN. Earlier lab facts are folded in: ports
1/1–1/7 only, encapsulation before LACP, global `lacp enable` last, `flex-uni enable` on
Switched UNI ports. Lines never accepted by these switches yet are marked `[new]`.

Still without a plan: DVR, IPv6, a capture before and after a change (idea #3).

## Later

- BOSS/ERS output (for #4, the migration assistant) is a different OS family. Not in
  this library unless the user decides otherwise.
- Captures from 8.10 and 9.3 at work would cover the mixed fleet. They can't come here
  (the repository is public and work output stays at work). An engineer can run
  `pytest` against them locally at work.
