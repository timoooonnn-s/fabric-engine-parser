"""`show vlan basic`, `show vlan members` and `show vlan i-sid`."""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass

from fabric_weft.output import Output, fullmatch
from fabric_weft.registry import parser
from fabric_weft.tables import Columns
from fabric_weft.values import optional, ports


@dataclass(frozen=True, slots=True)
class Vlan:
    vlan_id: int
    name: str
    vlan_type: str  # 'byPort', 'spbm-bvlan', ... kept as printed
    mstp_instance: int
    protocol_id: str | None
    subnet: str | None
    subnet_mask: str | None
    vrf_id: int
    origin: str


@dataclass(frozen=True, slots=True)
class VlanMembers:
    vlan_id: int
    ports: tuple[str, ...]
    active_ports: tuple[str, ...]
    static_ports: tuple[str, ...]
    not_allowed_ports: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class VlanIsid:
    vlan_id: int
    isid: int | None  # None: the VLAN is not mapped to an I-SID
    isid_name: str | None


# Anchored on the right: every column after NAME is a single word, so a name
# with spaces, or one wider than its column, cannot shift the other values.
_VLAN_ROW = re.compile(
    r"(?P<vlan_id>\d+)\s+(?P<name>.*?)\s+(?P<vlan_type>\S+)\s+(?P<mstp>\d+)\s+"
    r"(?P<protocol>\S+)\s+(?P<subnet>\S+)\s+(?P<mask>\S+)\s+(?P<vrf>\d+)\s+(?P<origin>\S+)"
)
_VLAN_ISID_ROW = re.compile(r"(?P<vlan_id>\d+)(?:\s+(?P<isid>\d+)(?:\s+(?P<name>.+))?)?")


@parser("show vlan basic")
def parse_vlans(output: Output) -> Iterator[Vlan]:
    """`show vlan basic` -> one Vlan per VLAN."""
    table = output.table("VLAN", "NAME", "TYPE", "VRFID")
    if table is None:
        return

    def build(row: str) -> Vlan:
        cells = fullmatch(_VLAN_ROW, row)
        return Vlan(
            vlan_id=int(cells["vlan_id"]),
            name=cells["name"],
            vlan_type=cells["vlan_type"],
            mstp_instance=int(cells["mstp"]),
            protocol_id=optional(cells["protocol"]),
            subnet=optional(cells["subnet"]),
            subnet_mask=optional(cells["mask"]),
            vrf_id=int(cells["vrf"]),
            origin=cells["origin"],
        )

    yield from output.build_each(table.rows, build)


@parser("show vlan members")
def parse_vlan_members(output: Output) -> Iterator[VlanMembers]:
    """`show vlan members` -> one VlanMembers per VLAN, port lists expanded.

    Long port lists wrap onto continuation lines under their own column, so the
    columns are cut by position and the pieces joined again.
    """
    table = output.table("VLAN", "PORT", "ACTIVE", "STATIC")
    if table is None:
        return
    labels = ["VLAN", "PORT", "ACTIVE", "STATIC"]
    if table.has_columns("NOT_ALLOW"):  # not printed by every release
        labels.append("NOT_ALLOW")
    columns = Columns.locate(table.header[0], *labels)

    def build(cells: list[str]) -> VlanMembers:
        vlan_id, members, active, static, *not_allowed = cells
        return VlanMembers(
            vlan_id=int(vlan_id),
            ports=ports(members),
            active_ports=ports(active),
            static_ports=ports(static),
            not_allowed_ports=ports(not_allowed[0]) if not_allowed else (),
        )

    yield from output.build_each(columns.cut_rows(table.rows), build)


@parser("show vlan i-sid")
def parse_vlan_isids(output: Output) -> Iterator[VlanIsid]:
    """`show vlan i-sid` -> one VlanIsid per VLAN, I-SID None when unmapped."""
    table = output.table("VLAN_ID", "I-SID")
    if table is None:
        return

    def build(row: str) -> VlanIsid:
        cells = fullmatch(_VLAN_ISID_ROW, row)
        return VlanIsid(
            vlan_id=int(cells["vlan_id"]),
            isid=int(cells["isid"]) if cells["isid"] else None,
            isid_name=cells["name"],
        )

    yield from output.build_each(table.rows, build)
