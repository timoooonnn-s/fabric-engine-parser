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
from fabric_weft.parsers.interfaces import (
    PortInterface,
    PortName,
    PortState,
    parse_port_interfaces,
    parse_port_names,
    parse_port_states,
)
from fabric_weft.parsers.isid import (
    Isid,
    MltBinding,
    PortBinding,
    SpbmIsid,
    parse_isids,
    parse_spbm_isids,
)
from fabric_weft.parsers.lldp import (
    LldpNeighbor,
    LldpNeighborSummary,
    parse_lldp_neighbors,
    parse_lldp_summary,
)
from fabric_weft.parsers.mlt import Mlt, VirtualIst, parse_mlts, parse_virtual_ist
from fabric_weft.parsers.vlan import (
    Vlan,
    VlanIsid,
    VlanMembers,
    parse_vlan_isids,
    parse_vlan_members,
    parse_vlans,
)
from fabric_weft.registry import find_parser, parse, supported_commands
from fabric_weft.result import ParseResult, SkippedLine

__version__ = "0.1.0"

__all__ = [
    "DeviceError",
    "Isid",
    "LldpNeighbor",
    "LldpNeighborSummary",
    "Mlt",
    "MltBinding",
    "ParseError",
    "ParseResult",
    "PortBinding",
    "PortInterface",
    "PortName",
    "PortState",
    "SkippedLine",
    "SpbmIsid",
    "UnknownCommandError",
    "VirtualIst",
    "Vlan",
    "VlanIsid",
    "VlanMembers",
    "WeftError",
    "find_parser",
    "parse",
    "parse_isids",
    "parse_lldp_neighbors",
    "parse_lldp_summary",
    "parse_mlts",
    "parse_port_interfaces",
    "parse_port_names",
    "parse_port_states",
    "parse_spbm_isids",
    "parse_virtual_ist",
    "parse_vlan_isids",
    "parse_vlan_members",
    "parse_vlans",
    "supported_commands",
]
