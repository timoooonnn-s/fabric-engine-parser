"""Layer 3: `show ip vrf`, `show ip route`, `show ip arp` and `show ip interface`."""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Iterator
from dataclasses import dataclass

from fabric_weft.output import Output, fullmatch
from fabric_weft.registry import parser
from fabric_weft.tables import Columns
from fabric_weft.values import flag, mac, optional, optional_int, port


@dataclass(frozen=True, slots=True)
class Vrf:
    """One VRF. The protocol fields are True when the protocol is set up in the VRF."""

    name: str
    vrf_id: int
    vlan_count: int
    arp_count: int
    rip: bool
    ospf: bool
    bgp: bool
    pim: bool
    ipv6_neighbor_count: int  # NBRv6 COUNT
    ripng: bool
    ospfv3: bool
    pim6: bool
    unicast_active: bool
    sd_wan_local_breakout: bool
    origin: str  # 'DYNAMIC', ... kept as printed
    segmented: bool


@dataclass(frozen=True, slots=True)
class IpRoute:
    """One route of a routing table (`show ip route [vrf X]`)."""

    vrf: str | None  # from the table title: 'GlobalRouter', 'blue'
    prefix: str  # DST and MASK together: '10.10.10.0/24'
    next_hop: str  # an address, or the host name of the BEB for routes over the fabric
    next_hop_vrf: str | None  # NH VRF/ISID; None when printed '-'
    cost: int
    interface: str  # as printed: the VLAN ('10'), the B-VLAN for IS-IS routes ('4051')
    protocol: str  # 'LOC', 'STAT', 'ISIS', ... kept as printed
    age: int
    type_flags: str  # as printed, see the TYPE legend: 'DB', 'IBS', 'IBSV'
    preference: int
    access: str  # ACCESS, as printed: 'Trusted'


@dataclass(frozen=True, slots=True)
class ArpEntry:
    """One ARP entry (`show ip arp [vrf X]`)."""

    vrf: str | None  # from the table title
    ip_address: str
    mac: str
    vlan_id: int | None  # None when printed '-' (a circuitless IP)
    port: str | None  # None when printed '-' (the switch itself)
    entry_type: str  # 'LOCAL', 'DYNAMIC', ... kept as printed
    ttl_seconds: int  # printed in units of 10 seconds: 2160 -> 21600
    tunnel: str | None  # the BEB an entry was learned through, over the fabric
    l3_access: str | None  # L3 ACCESS, as printed


@dataclass(frozen=True, slots=True)
class IpInterface:
    """One IP interface (`show ip interface [vrf X]`)."""

    vrf: str | None  # from the table title
    interface: str  # as printed: 'Vlan10', 'Clip1'
    ip_address: str
    prefix_length: int  # from NET MASK
    admin_enabled: bool
    oper_up: bool
    vlan_id: int | None  # None when printed '--' (a circuitless IP)
    brouter_port: bool
    ipsec_enabled: bool
    l3_access: str | None  # ACCESS, as printed
    ip_name: str | None


# Anchored on the numbers after the name, so a name with spaces, or one wider than
# its column, cannot shift the other values (as in `show vlan basic`).
_VRF_ROW = re.compile(
    r"(?P<name>.+?)\s+(?P<vrf_id>\d+)\s+(?P<vlans>\d+)\s+(?P<arps>\d+)\s+"
    r"(?P<rip>\S+)\s+(?P<ospf>\S+)\s+(?P<bgp>\S+)\s+(?P<pim>\S+)\s+(?P<ipv6_neighbors>\d+)\s+"
    r"(?P<ripng>\S+)\s+(?P<ospfv3>\S+)\s+(?P<pim6>\S+)\s+(?P<unicast>\S+)\s+"
    r"(?P<breakout>\S+)\s+(?P<origin>\S+)\s+(?P<segmented>\S+)"
)


@parser("show ip vrf")
def parse_vrfs(output: Output) -> Iterator[Vrf]:
    """`show ip vrf` -> one Vrf per VRF. The summary table printed above is not read."""
    table = output.table("NAME", "ID", "SEGMENTED")
    if table is None:
        return

    def build(row: str) -> Vrf:
        cells = fullmatch(_VRF_ROW, row)
        return Vrf(
            name=cells["name"],
            vrf_id=int(cells["vrf_id"]),
            vlan_count=int(cells["vlans"]),
            arp_count=int(cells["arps"]),
            rip=flag(cells["rip"]),
            ospf=flag(cells["ospf"]),
            bgp=flag(cells["bgp"]),
            pim=flag(cells["pim"]),
            ipv6_neighbor_count=int(cells["ipv6_neighbors"]),
            ripng=flag(cells["ripng"]),
            ospfv3=flag(cells["ospfv3"]),
            pim6=flag(cells["pim6"]),
            unicast_active=flag(cells["unicast"]),
            sd_wan_local_breakout=flag(cells["breakout"]),
            origin=cells["origin"],
            segmented=flag(cells["segmented"]),
        )

    yield from output.build_each(table.rows, build)


def _vrf_of(title: str) -> str | None:
    """'IP Route - GlobalRouter' -> 'GlobalRouter', 'IP Arp - VRF blue' -> 'blue'."""
    _, separator, name = title.partition(" - ")
    if not separator:
        return None
    name = name.strip()
    return name[4:].strip() if name.startswith("VRF ") else name or None


def _prefix_length(mask: str) -> int:
    return ipaddress.IPv4Network(f"0.0.0.0/{mask}").prefixlen


_ROUTE_ROW = re.compile(
    r"(?P<destination>\S+)\s+(?P<mask>\S+)\s+(?P<next_hop>\S+)\s+(?P<next_hop_vrf>\S+)\s+"
    r"(?P<cost>\d+)\s+(?P<interface>\S+)\s+(?P<protocol>\S+)\s+(?P<age>\d+)\s+(?P<type>\S+)\s+"
    r"(?P<preference>\d+)\s+(?P<access>\S+)"
)


@parser("show ip route")
def parse_ip_routes(output: Output) -> Iterator[IpRoute]:
    """`show ip route [vrf X]` -> one IpRoute per route. Every cell is one word."""
    table = output.table("DST", "MASK", "NEXT", "PROT")
    if table is None:
        return
    vrf = _vrf_of(table.title)

    def build(row: str) -> IpRoute:
        cells = fullmatch(_ROUTE_ROW, row)
        network = ipaddress.IPv4Network(f"{cells['destination']}/{cells['mask']}")
        return IpRoute(
            vrf=vrf,
            prefix=str(network),
            next_hop=cells["next_hop"],
            next_hop_vrf=optional(cells["next_hop_vrf"]),
            cost=int(cells["cost"]),
            interface=cells["interface"],
            protocol=cells["protocol"],
            age=int(cells["age"]),
            type_flags=cells["type"],
            preference=int(cells["preference"]),
            access=cells["access"],
        )

    yield from output.build_each(table.rows, build)


@parser("show ip arp")
def parse_arp_entries(output: Output) -> Iterator[ArpEntry]:
    """`show ip arp [vrf X]` -> one ArpEntry per entry.

    Cut by column: TUNNEL is empty for entries learned locally. The 'IP Arp Extn'
    table after it holds settings, not entries, and is not read.
    """
    table = output.table("IP_ADDRESS", "MAC_ADDRESS", "TUNNEL")
    if table is None:
        return
    vrf = _vrf_of(table.title)
    columns = Columns.locate(
        table.header, "IP_ADDRESS", "MAC_ADDRESS", "VLAN", "PORT", "TYPE", "TTL(10", "TUNNEL", "L3"
    )

    def build(cells: list[str]) -> ArpEntry:
        address, mac_address, vlan, port_cell, entry_type, ttl, tunnel, l3_access = cells
        ipaddress.IPv4Address(address)  # raises ValueError on anything else
        if not entry_type:
            raise ValueError("line does not have the expected format")
        return ArpEntry(
            vrf=vrf,
            ip_address=address,
            mac=mac(mac_address),
            vlan_id=optional_int(vlan),
            port=port(port_cell) if optional(port_cell) else None,
            entry_type=entry_type,
            ttl_seconds=int(ttl) * 10,
            tunnel=optional(tunnel),
            l3_access=optional(l3_access),
        )

    yield from output.build_each(map(columns.cut, table.rows), build)


@parser("show ip interface")
def parse_ip_interfaces(output: Output) -> Iterator[IpInterface]:
    """`show ip interface [vrf X]` -> one IpInterface per IP interface.

    Cut by column across both header lines: IP NAME is usually empty.
    """
    table = output.table("INTERFACE", "BROUTER", "IPSEC")
    if table is None:
        return
    vrf = _vrf_of(table.title)
    columns = Columns.locate(
        table.header,
        "INTERFACE",
        "IP",
        "NET",
        "ADMIN",
        "OPER",
        "VLAN",
        "BROUTER",
        "IPSEC",
        "ACCESS",
        "IP",
    )

    def build(cells: list[str]) -> IpInterface:
        interface, address, mask, admin, oper, vlan, brouter, ipsec, access, name = cells
        ipaddress.IPv4Address(address)  # raises ValueError on anything else
        return IpInterface(
            vrf=vrf,
            interface=interface,
            ip_address=address,
            prefix_length=_prefix_length(mask),
            admin_enabled=flag(admin),
            oper_up=flag(oper),
            vlan_id=optional_int(vlan),
            brouter_port=flag(brouter),
            ipsec_enabled=flag(ipsec),
            l3_access=optional(access),
            ip_name=optional(name),
        )

    yield from output.build_each(map(columns.cut, table.rows), build)
