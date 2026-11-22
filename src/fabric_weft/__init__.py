"""fabric_weft: Extreme Fabric Engine / VOSS `show` output in, typed Python records out.

    from fabric_weft import parse

    result = parse("show mlt", netmiko_output)
    for mlt in result:
        print(mlt.mlt_id, mlt.members)
    if not result.complete:
        print(result.skipped)

Every parser can also be called directly, e.g. `parse_mlts(text)`.
"""

from fabric_weft.errors import DeviceError, ParseError, UnknownCommandError, WeftError
from fabric_weft.parsers.config import ConfigCommand, parse_running_config
from fabric_weft.parsers.interfaces import (
    PortInterface,
    PortIsid,
    PortL1Config,
    PortName,
    PortState,
    PortVlans,
    parse_port_interfaces,
    parse_port_isids,
    parse_port_l1_config,
    parse_port_names,
    parse_port_states,
    parse_port_vlans,
)
from fabric_weft.parsers.ip import Vrf, parse_vrfs
from fabric_weft.parsers.isid import (
    Isid,
    MltBinding,
    PortBinding,
    SpbmIsid,
    parse_isids,
    parse_spbm_isids,
)
from fabric_weft.parsers.isis import (
    IsisAdjacency,
    IsisInterface,
    IsisLsp,
    IsisSettings,
    IsisSystemId,
    SpbmInstance,
    SpbmNickname,
    SpbmUnicastRoute,
    parse_isis_adjacencies,
    parse_isis_interfaces,
    parse_isis_lsdb,
    parse_isis_settings,
    parse_isis_system_ids,
    parse_spbm_instances,
    parse_spbm_nicknames,
    parse_spbm_unicast_fib,
)
from fabric_weft.parsers.lldp import (
    LldpNeighbor,
    LldpNeighborSummary,
    parse_lldp_neighbors,
    parse_lldp_summary,
)
from fabric_weft.parsers.mlt import (
    LacpParticipant,
    LacpPort,
    Mlt,
    VirtualIst,
    parse_lacp_ports,
    parse_mlts,
    parse_virtual_ist,
)
from fabric_weft.parsers.system import (
    Software,
    SoftwareRelease,
    SysInfo,
    parse_software,
    parse_sys_info,
)
from fabric_weft.parsers.vlan import (
    MacEntry,
    Vlan,
    VlanIsid,
    VlanMembers,
    parse_mac_entries,
    parse_vlan_isids,
    parse_vlan_members,
    parse_vlans,
)
from fabric_weft.registry import find_parser, parse, supported_commands
from fabric_weft.result import ParseResult, SkippedLine

__version__ = "0.1.0"

__all__ = [
    "ConfigCommand",
    "DeviceError",
    "Isid",
    "IsisAdjacency",
    "IsisInterface",
    "IsisLsp",
    "IsisSettings",
    "IsisSystemId",
    "LacpParticipant",
    "LacpPort",
    "LldpNeighbor",
    "LldpNeighborSummary",
    "MacEntry",
    "Mlt",
    "MltBinding",
    "ParseError",
    "ParseResult",
    "PortBinding",
    "PortInterface",
    "PortIsid",
    "PortL1Config",
    "PortName",
    "PortState",
    "PortVlans",
    "SkippedLine",
    "Software",
    "SoftwareRelease",
    "SpbmInstance",
    "SpbmIsid",
    "SpbmNickname",
    "SpbmUnicastRoute",
    "SysInfo",
    "UnknownCommandError",
    "VirtualIst",
    "Vlan",
    "VlanIsid",
    "VlanMembers",
    "Vrf",
    "WeftError",
    "find_parser",
    "parse",
    "parse_isids",
    "parse_isis_adjacencies",
    "parse_isis_interfaces",
    "parse_isis_lsdb",
    "parse_isis_settings",
    "parse_isis_system_ids",
    "parse_lacp_ports",
    "parse_lldp_neighbors",
    "parse_lldp_summary",
    "parse_mac_entries",
    "parse_mlts",
    "parse_port_interfaces",
    "parse_port_isids",
    "parse_port_l1_config",
    "parse_port_names",
    "parse_port_states",
    "parse_port_vlans",
    "parse_running_config",
    "parse_software",
    "parse_spbm_instances",
    "parse_spbm_isids",
    "parse_spbm_nicknames",
    "parse_spbm_unicast_fib",
    "parse_sys_info",
    "parse_virtual_ist",
    "parse_vlan_isids",
    "parse_vlan_members",
    "parse_vlans",
    "parse_vrfs",
    "supported_commands",
]
