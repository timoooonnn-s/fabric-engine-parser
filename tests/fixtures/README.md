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

## Changes made while copying

- `prod-vsp7254-voss8.10/show_lldp_neighbor_summary.txt`: the neighbour host names
  were replaced with `core-sw-a`, `core-sw-b`, `dist-sw-02` and `access-sw-1`, padded
  to the same width so every column stays where it was. Nothing else was changed.
- File names now follow the rule above (`show_vlan_i_sid` → `show_vlan_i-sid`).

## Adding a capture

1. `python tools/capture.py --host <ip> --source fe-9.4-gns3` (or save netmiko output yourself).
   Several switches in one run: `--host core1=<ip> --host core2=<ip> ...` writes one
   folder per switch, `fe-9.4-gns3-core1/` and so on. `--list` shows the plan first.
2. `pytest --update-golden`
3. Read the new `.json` files. The test only proves the parser is *consistent*;
   a person has to confirm it is *right* once.
4. Add a row to the table above.
