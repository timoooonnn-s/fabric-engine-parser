"""Layer 3: `show ip vrf`."""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass

from fabric_weft.output import Output, fullmatch
from fabric_weft.registry import parser
from fabric_weft.values import flag


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
