# Test fixtures

Each folder holds the raw output of one source, one file per command. A file is
named after the command with spaces replaced by `_` (hyphens stay):
`show vlan i-sid` → `show_vlan_i-sid.txt`. Next to every `.txt` is the `.json`
the parser must produce for it (see `tests/test_fixtures.py`).

**Rule (decision 0006):** a fixture says where it came from. A real capture and a
reconstruction are not the same evidence. Only a real capture proves a parser.

| Folder | Source | Evidence |
|---|---|---|
| `prod-vsp7254-voss8.10/` | Real production captures, copied from `switch-migrator/tests/fixtures/voss_prod/gx-11-s72-p1-priv`. A VSP 7254XSQ. The release was not captured; its vIST peer runs 8.10.9.0, so this box most likely runs 8.10.x too. | **Real** |
| `shapes-unverified/` | Copied from `switch-migrator/tests/fixtures/voss/`. Origin not recorded. Some files have a real execution banner, some were clearly edited. Realistic shape, details unverified. | Shape only |
| `doc-derived-9.x/` | Copied from `switch-migrator/tests/fixtures/voss_9x/`. Rebuilt from the Extreme command reference, **not** captured from a switch. It covers wrapped port lists and channelized ranges. | Shape only |
| `fe-9.4-gns3-sw1/` | Captured in the GNS3 lab with `tools/capture.py` on 2026-11-21, FEGNS3.9.4.0.0.GA. A lab switch with almost no config: no ports in any VLAN, no MLT, no vIST. `show_mlt` and `show_virtual-ist` are empty on purpose (`EMPTY_ON_PURPOSE` in `tests/test_fixtures.py`). | **Real** |
| `fe-9.4-gns3-fe-01/` … `fe-04/` | Captured in the GNS3 lab with `tools/capture.py` on 2026-11-22, FEGNS3.9.4.0.0.GA, privileged mode. Four access nodes with IS-IS adjacencies between them, CVLAN I-SIDs (fe-01/02: VLAN 40; fe-03/04: VLANs 10, 20, 30) and end devices. No MLT, no vIST (listed in `EMPTY_ON_PURPOSE`). `show_running-config.txt` checked: no credentials in it. | **Real** |
| `fe-9.4-gns3-lab2-fe-01/` … `fe-04/` | The same four nodes on 2026-11-22, after the lab2 config: MLT 10 with LACP on fe-01/fe-02 (links not connected, so no members), ELAN I-SID 30100 and VLANs 50, 60–68 on fe-01, IP shortcuts, a CLIP, VRF `blue` with an L3 VSN and IP interfaces on fe-03/fe-04, end-device traffic. Captured with `--vrf blue`; the `vrf blue` files of fe-01/fe-02 were removed (the switch answered `Error: The VRF Name entered does not correspond to any VRF`, kept as a unit test). fe-04 captured a second time after a lost prompt. | **Real** |
| `fe-9.4-gns3-lab3-fe-01/`, `…-fe-02/` | fe-01 and fe-02 again on 2026-11-22, after cabling 1/5–1/7 between them (the GNS3 nodes can only be cabled on 1/1–1/7) and adding `untagged-traffic port 1/7` to I-SID 30100. MLT 10 still has no members: LACP is configured on the ports but not enabled globally. | **Real** |
| `fe-9.4-gns3-lab4-fe-01/`, `…-fe-02/` | fe-01 and fe-02 on 2026-11-22 after global `lacp enable`: MLT 10 up with members 1/5–1/6 and the other switch as LACP partner. Enabling LACP also added `vlacp enable` and dropped `vlan mlt 50 10`, so MLT 10 is an access MLT without VLANs here. | **Real** |
| `fe-9.4-gns3-lab5-fe-01/`, `…-fe-02/` | fe-01 and fe-02 on 2026-11-22 after `vlan mlt 50 10` and an attempt at `mlt 10 encapsulation dot1q` (LACP off, change, LACP on). The encapsulation did not stick: MLT 10 is an access LACP MLT carrying VLAN 50 untagged on 1/5–1/6. | **Real** |
| `fe-9.4-gns3-lab6-fe-01/` … `fe-04/` | All four on 2026-11-22 after a clean rebuild from `tools/lab/` (build 2). MLT 10 is a trunk LACP MLT; MLT 20 is an SMLT whose links ended up between fe-01 and fe-02 (a leftover cable), so fe-03's MLT 20 and VRF blue VLAN 103 are down; the vIST lines did not take, so there is no vIST. `tools/lab/README.md` records what worked and what did not. | **Real** |

## Changes made while copying

- `prod-vsp7254-voss8.10/show_lldp_neighbor_summary.txt`: the neighbour host names
  were replaced with `core-sw-a`, `core-sw-b`, `dist-sw-02` and `access-sw-1`, padded
  to the same width so every column stays where it was. Nothing else was changed.
- File names now follow the rule above (`show_vlan_i_sid` → `show_vlan_i-sid`).

The lab configs from build 2 on (`fe-9.4-gns3-lab6-*`) are in `tools/lab/`, so those
captures can be traced to the exact config that produced them.

## Adding a capture

1. `python tools/capture.py --host <ip> --source fe-9.4-gns3` (or save netmiko output yourself).
   Several switches in one run: `--host core1=<ip> --host core2=<ip> ...` writes one
   folder per switch, `fe-9.4-gns3-core1/` and so on. `--list` shows the plan first.
2. `pytest --update-golden`
3. Read the new `.json` files. The test only proves the parser is *consistent*;
   a person has to confirm it is *right* once.
4. Add a row to the table above.
