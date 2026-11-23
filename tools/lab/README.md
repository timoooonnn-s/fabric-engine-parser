# Lab build 2 (2026-11-22)

The GNS3 lab the fixtures `fe-9.4-gns3-lab6-*` are captured from, rebuilt clean so every
capture has a documented starting state. One file per node: `fe-01.cli` … `fe-04.cli`.

Lines marked `[new]` have never been accepted by these switches; everything else was
accepted in an earlier round (taken from the captured running-configs). If a `[new]` line
is rejected, note the error and carry on: each file says what to drop instead.

## Limits

- GNS3 nodes can only be cabled on **mgmt and 1/1–1/7**. Ports above 1/7 are configured
  anyway where a feature shows up in the output while the port is down.
- On 9.4, an MLT's encapsulation cannot change while LACP runs on it. So every MLT here
  gets `encapsulation dot1q` first and LACP last, with the global `lacp enable` at the end.

## Topology

- **Fabric:** as today. fe-01 and fe-02 link to each other and to fe-03 and fe-04;
  fe-03 and fe-04 have no direct link.
- **vIST pair:** fe-01 and fe-02, over the fabric (VLAN 4000, no cable of its own).
- **SMLT 20:** fe-03 is the client, with one LACP link to each of fe-01 and fe-02.
- **MLT 10:** a plain LACP trunk between fe-01 and fe-02, two links.
- **L3:** CLIP and IP shortcuts on all four; VRF `blue` (L3 VSN) on fe-03 and fe-04.

| Port | fe-01 | fe-02 | fe-03 | fe-04 |
|---|---|---|---|---|
| 1/1 | NNI → fe-02 1/1 | NNI → fe-01 1/1 | NNI → fe-01 1/2 | NNI → fe-01 1/3 |
| 1/2 | NNI → fe-03 1/1 | NNI → fe-03 1/2 | NNI → fe-02 1/2 | NNI → fe-02 1/3 |
| 1/3 | NNI → fe-04 1/1 | NNI → fe-04 1/2 | VPCS, VLAN 10 | VPCS, VLAN 10 |
| 1/4 | VPCS, VLAN 40 | VPCS, VLAN 40 | VPCS, VLAN 20 | VPCS, VLAN 20 |
| 1/5 | SMLT 20 → fe-03 1/6 | SMLT 20 → fe-03 1/7 | VPCS, VLAN 30 | VPCS, VLAN 104 (VRF blue) |
| 1/6 | MLT 10 → fe-02 1/6 | MLT 10 → fe-01 1/6 | MLT 20 → fe-01 1/5 | free |
| 1/7 | MLT 10 → fe-02 1/7 | MLT 10 → fe-01 1/7 | MLT 20 → fe-02 1/5 | free |

## Cables (GNS3)

Fabric (as today): fe-01 1/1–fe-02 1/1, fe-01 1/2–fe-03 1/1, fe-01 1/3–fe-04 1/1,
fe-02 1/2–fe-03 1/2, fe-02 1/3–fe-04 1/2.
New: fe-01 1/6–fe-02 1/6, fe-01 1/7–fe-02 1/7 (MLT 10), fe-01 1/5–fe-03 1/6,
fe-02 1/5–fe-03 1/7 (SMLT 20).
VPCS: fe-01 1/4, fe-02 1/4, fe-03 1/3–1/5, fe-04 1/3–1/5 (eight hosts).

## Order

1. Build the four nodes with your Ansible base. Section 1 of each file is that base as the
   captures show it. On fe-01 and fe-02 it also needs the vIST lines before IS-IS is enabled:
   the peer's system ID (read it with `show isis system-id` on the peer after the base
   build; it changes with every new VM), the virtual B-MAC and `virtual-ist peer-ip`.
   `router isis enable` then asks y/n: answer by hand, never paste past it.
2. Apply the rest of each file, fe-01 to fe-04.
3. Check on fe-01 (and the same on fe-02):
   - `show isis adjacencies`: fe-02, fe-03, fe-04 up
   - `show virtual-ist`: peer 192.168.255.2, status up
   - `show mlt`: MLT 10 `trunk` with 1/6–1/7 and VLAN 50; MLT 20 `trunk` `smlt` with 1/5
     and VLAN 60
   - `show lacp interface`: partners filled in for 1/5–1/7
4. VPCS, then ping (MAC and ARP entries age out, so capture right after):

   | Host | `ip …` | ping |
   |---|---|---|
   | fe-01 1/4 | `ip 10.40.0.11/24` | 10.40.0.12 |
   | fe-02 1/4 | `ip 10.40.0.12/24` | 10.40.0.11 |
   | fe-03 1/3 | `ip 10.10.10.13/24 10.10.10.3` | 10.10.10.14, 10.10.10.3, 10.255.0.4 |
   | fe-04 1/3 | `ip 10.10.10.14/24 10.10.10.3` | 10.10.10.13 |
   | fe-03 1/4 | `ip 10.20.0.13/24` | 10.20.0.14 |
   | fe-04 1/4 | `ip 10.20.0.14/24` | 10.20.0.13 |
   | fe-03 1/5 | `ip 10.30.0.13/24` | (alone in VLAN 30) |
   | fe-04 1/5 | `ip 10.100.4.10/24 10.100.4.1` | 10.100.3.1 (VRF blue over the L3 VSN) |

5. Capture all four:

   ```
   python tools/capture.py --source fe-9.4-gns3-lab6 --host fe-01=10.99.0.11 \
       --host fe-02=10.99.0.12 --host fe-03=10.99.0.13 --host fe-04=10.99.0.14 --vrf blue
   ```

## What each part is for

| Part | Fills |
|---|---|
| vIST fe-01/fe-02 | `show virtual-ist` (empty in every capture so far) |
| SMLT 20 with LACP | `show smlt mlt`, SMLT rows in `show mlt`, LACP with an SMLT system ID |
| MLT 10, LACP trunk | a trunk LACP MLT with a tagged VLAN (lab5 only got an access one) |
| CLIPs + IP shortcuts on all four | `show ip route`/`ip interface` with rows on every node |
| VRF blue: VLAN 103 on MLT 20 (fe-03), VLAN 104 (fe-04) | L3 VSN routes and ARP in a VRF |
| ELAN 30100 on 1/8–1/9 | `c:`/`u:` bindings without using a cable |
| VLAN 70–78 on 1/12–1/24 | wrapped member list, overflowing port VLAN list |

## Result of build 2 (captured as `fe-9.4-gns3-lab6-*`)

Worked: fabric, IP shortcuts and CLIPs on all four (routes over IS-IS everywhere), VRF
`blue` on fe-04, **MLT 10 as a trunk LACP MLT** (encapsulation before LACP did it; the
running-config does not print `mlt 10 encapsulation dot1q`, but the MLT has it).

Did not:

1. **SMLT 20 cabling.** fe-01 1/5 is still cabled to fe-02 1/5 (left from lab3), and fe-03
   1/6–1/7 have no cable. So fe-01 and fe-02 formed MLT 20 with each other, and fe-03's
   MLT 20 (and with it VLAN 103 in VRF blue) is down.
   Fix in GNS3: remove fe-01 1/5–fe-02 1/5; add fe-01 1/5–fe-03 1/6 and fe-02 1/5–fe-03 1/7.
2. **None of the `[new]` lines took.** Not in any running-config: `system-id` (the system
   IDs are the VMs' own, e.g. fe-01 `0c52.cf92.0084`), `smlt-peer-system-id`,
   `smlt-virtual-bmac`, `virtual-ist peer-ip`, `lacp smlt-sys-id`. So there is no vIST.
   The error messages were not seen; paste them next time.

### Fix without a rebuild (the system IDs are the current ones; untested)

fe-01 (`no router isis enable` drops the adjacencies for a moment and asks for `y`):

```
configure terminal
no router isis enable
router isis
spbm 1 smlt-peer-system-id 0ce7.427f.0084
spbm 1 smlt-virtual-bmac 02:00:00:00:12:00
exit
router isis enable
virtual-ist peer-ip 192.168.255.2 vlan 4000
interface mlt 20
no lacp enable
lacp smlt-sys-id 02:00:00:00:20:00
lacp enable key 20
exit
```

fe-02: the same with `smlt-peer-system-id 0c52.cf92.0084` and `virtual-ist peer-ip
192.168.255.1 vlan 4000`.

Check `show virtual-ist` (peer up) and `show smlt mlt` (MLT 20 current type `smlt`) on both,
`show mlt` on fe-03 (MLT 20 with 1/6–1/7), then ping from fe-04 1/5 to 10.100.3.1 and capture
all four as `fe-9.4-gns3-lab7`.

For the next rebuild: the system IDs change with every new VM, so the vIST lines must use
the peer's ID as `show isis system-id` prints it after the build, unless `system-id` turns out
to work once its error is known.

### Learned while fixing (2026-11-22)

- `router isis enable` asks y/n when SMLT settings exist; a pasted next line is eaten.
- `virtual-ist peer-ip` must be set before `router isis enable`, otherwise: "Virtual IST
  requires both SPBM SMLT peer system-id & Virtual IST peer-ip to be configured".
- `lacp smlt-sys-id` is not a command under `interface mlt`.
- With the default system-id, the configured `smlt-virtual-bmac` is replaced by a generated
  one when IS-IS is enabled (a warning says so).
