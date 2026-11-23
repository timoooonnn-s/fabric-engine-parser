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
| `show interfaces gigabitEthernet vlan` | `parse_port_vlans` | `PortVlans` |
| `show interfaces gigabitEthernet i-sid` | `parse_port_isids` | `PortIsid` |
| `show interfaces gigabitEthernet l1-config` | `parse_port_l1_config` | `PortL1Config` |
| `show vlan basic` | `parse_vlans` | `Vlan` |
| `show vlan members` | `parse_vlan_members` | `VlanMembers` |
| `show vlan i-sid` | `parse_vlan_isids` | `VlanIsid` |
| `show vlan mac-address-entry` | `parse_mac_entries` | `MacEntry` |
| `show i-sid` | `parse_isids` | `Isid` (with `PortBinding`, `MltBinding`) |
| `show isis spbm i-sid all` / `config` / `discover` | `parse_spbm_isids` | `SpbmIsid` |
| `show mlt` | `parse_mlts` | `Mlt` (all four tables merged) |
| `show virtual-ist` | `parse_virtual_ist` | `VirtualIst` |
| `show smlt mlt` | `parse_smlt_mlts` | `SmltMlt` |
| `show lacp interface` | `parse_lacp_ports` | `LacpPort` (with `LacpParticipant`) |
| `show lacp interface` (aggregator tables) | `parse_lacp_aggregators`, called directly | `LacpAggregator` |
| `show lldp neighbor summary` | `parse_lldp_summary` | `LldpNeighborSummary` |
| `show lldp neighbor` | `parse_lldp_neighbors` | `LldpNeighbor` |
| `show sys-info` | `parse_sys_info` | `SysInfo` (name, release, model, uptime, MACs) |
| `show software` | `parse_software` | `Software` (with `SoftwareRelease`) |
| `show isis adjacencies` | `parse_isis_adjacencies` | `IsisAdjacency` |
| `show isis interface` | `parse_isis_interfaces` | `IsisInterface` |
| `show isis system-id` | `parse_isis_system_ids` | `IsisSystemId` |
| `show isis` | `parse_isis_settings` | `IsisSettings` |
| `show isis lsdb` | `parse_isis_lsdb` | `IsisLsp` |
| `show isis spbm` | `parse_spbm_instances` | `SpbmInstance` |
| `show isis spbm nick-name` | `parse_spbm_nicknames` | `SpbmNickname` |
| `show isis spbm unicast-fib` | `parse_spbm_unicast_fib` | `SpbmUnicastRoute` |
| `show ip vrf` | `parse_vrfs` | `Vrf` |
| `show ip route [vrf X]` | `parse_ip_routes` | `IpRoute` |
| `show ip arp [vrf X]` | `parse_arp_entries` | `ArpEntry` |
| `show ip interface [vrf X]` | `parse_ip_interfaces` | `IpInterface` |
| `show running-config` | `parse_running_config` | `ConfigCommand` (section, context, command as printed) |

The records are frozen dataclasses. Their fields are listed in the source, one module per
command family under `src/fabric_weft/parsers/`. Next up: vIST/SMLT
(see `council/PLAN.md`).

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
- Uptimes come out as `datetime.timedelta`.
- Numbers printed in hex (`0xc0`) become `int`. VLAN `0` means "no VLAN": `None` or `()`.
- IS-IS system IDs stay `xxxx.xxxx.xxxx`, and every IS-IS and SPBM record carries
  `system_id`, so adjacencies, nicknames, FIB entries and the LSDB join on it.
- Interfaces keep their printed name (`Port1/1`, `Port-cpp`); records that have one
  also give `port` (`'1/1'`, or `None` when it is not a front port).
- Words the switch can extend, such as VLAN type or I-SID type, stay as printed.
- `show running-config` is not interpreted: one `ConfigCommand` per line, with the
  section and context it stands in (decision 0014).

## Errors

| | default | `strict=True` |
|---|---|---|
| a line that can't be read | skipped, listed in `result.skipped` | `ParseError` |
| the switch answered `% Invalid input ...` or `Error: ...` | `DeviceError` | `DeviceError` |
| no parser for the command | `UnknownCommandError` | `UnknownCommandError` |

All three exceptions derive from `WeftError`. Use `strict=True` where a missed line
must stop the run, for example in pre/post migration checks. `% Invalid input` also
shows up when the account lacks the privilege for a command.

## Development

```bash
pytest                    # every fixture is parsed in strict mode and compared to its .json
pytest --update-golden    # after adding a capture or changing a parser: review the diff!
ruff check . && ruff format --check .
mypy                      # strict, on src and tests (decision 0015)
python tools/capture.py --host <lab-switch> --source fe-9.4-gns3   # needs '.[capture]'
```

- `docs/adding-a-parser.md`: how a parser is built.
- `docs/decisions/`: why the code looks the way it does.
- `tests/fixtures/README.md`: where each capture came from.
- `council/`: the team, its standing rules and the plan.
