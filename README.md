# fabric-weft

**A parser library for Extreme Networks Fabric Engine / VOSS `show` commands.** It
takes the text netmiko returns and gives you typed Python records: ports, VLANs,
I-SIDs, MLTs, LLDP neighbours, and more to come.

Standard library only · Python ≥ 3.10 · tested against real captures

```python
from netmiko import ConnectHandler
from fabric_weft import parse

with ConnectHandler(device_type="extreme_vsp", host="192.0.2.10", ...) as switch:
    command = "show mlt"
    result = parse(command, switch.send_command(command))

for mlt in result:
    print(mlt.mlt_id, mlt.name, mlt.members, mlt.lacp_oper_up)
# 35 MLT035.s.1/2/23/24 ('1/1', '1/2', '1/23', '1/24') False
```

## Install

```bash
pip install git+https://github.com/<owner>/<repo>.git   # or from the internal mirror
pip install -e '.[dev]'                                  # working on the library itself
```

## Supported commands

Every word can be abbreviated (`sh int gig name 1/1-1/4`), and arguments after the
command are ignored (`show ip route vrf RED`). Each parser can also be imported
and called directly.

| Command | Function | Record |
|---|---|---|
| `show interfaces gigabitEthernet [interface]` | `parse_port_interfaces` | `PortInterface` |
| `show interfaces gigabitEthernet name` | `parse_port_names` | `PortName` |
| `show interfaces gigabitEthernet state` | `parse_port_states` | `PortState` |
| `show vlan basic` | `parse_vlans` | `Vlan` |
| `show vlan members` | `parse_vlan_members` | `VlanMembers` |
| `show vlan i-sid` | `parse_vlan_isids` | `VlanIsid` |
| `show i-sid` | `parse_isids` | `Isid` (with `PortBinding`, `MltBinding`) |
| `show isis spbm i-sid all` / `config` / `discover` | `parse_spbm_isids` | `SpbmIsid` |
| `show mlt` | `parse_mlts` | `Mlt` (all four tables merged) |
| `show virtual-ist` | `parse_virtual_ist` | `VirtualIst` |
| `show lldp neighbor summary` | `parse_lldp_summary` | `LldpNeighborSummary` |
| `show lldp neighbor` | `parse_lldp_neighbors` | `LldpNeighbor` |

The records are frozen dataclasses. Their fields are listed in the source, one module per
command family under `src/fabric_weft/parsers/`. Next up: IS-IS adjacencies, the MAC
table, routes per VRF, `sys-info` (see `council/PLAN.md`).

## What you get back

```python
result = parse("show vlan basic", text)
result.records      # tuple of Vlan
result.complete     # False if any line could not be read
result.skipped      # (SkippedLine(line=..., reason=...), ...)
result.as_dicts()   # plain dicts, e.g. for JSON
```

What the values look like:

- `up`/`down`, `true`/`false` and `enable`/`disable` become `bool`.
- `-`, `--`, `N/A` and `NONE` become `None`.
- Port lists are expanded: `'1/1-1/3'` becomes `('1/1', '1/2', '1/3')`.
- MACs come out as `aa:bb:cc:dd:ee:ff`.
- Words the switch can extend, such as VLAN type or I-SID type, stay as printed.

## Errors

| | default | `strict=True` |
|---|---|---|
| a line that can't be read | skipped, listed in `result.skipped` | `ParseError` |
| the switch answered `% Invalid input ...` | `DeviceError` | `DeviceError` |
| no parser for the command | `UnknownCommandError` | `UnknownCommandError` |

All three exceptions derive from `WeftError`. Use `strict=True` where a missed line
must stop the run, for example in pre/post migration checks. `% Invalid input` also
shows up when the account lacks the privilege for a command.

## Development

```bash
pytest                    # every fixture is parsed in strict mode and compared to its .json
pytest --update-golden    # after adding a capture or changing a parser: review the diff!
ruff check . && ruff format --check .
python tools/capture.py --host <lab-switch> --source fe-9.4-gns3   # needs '.[capture]'
```

- `docs/adding-a-parser.md`: how a parser is built.
- `docs/decisions/`: why the code looks the way it does.
- `tests/fixtures/README.md`: where each capture came from.
- `council/`: the team, its standing rules and the plan.
