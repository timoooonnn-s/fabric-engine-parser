"""`show vlan basic`, `show vlan members`, `show vlan i-sid` and `show vlan mac-address-entry`."""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass

from fabric_weft.output import Output, fullmatch
from fabric_weft.registry import parser
from fabric_weft.tables import Columns
from fabric_weft.values import flag, mac, optional, optional_int, port_of, ports


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
    l3_access: str | None = None  # 9.x 'L3 ACCESS' column ('GlobalRouter'); None on 8.x


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
    vlan_name: str | None = None  # printed by 9.x only


@dataclass(frozen=True, slots=True)
class MacEntry:
    """One forwarding database entry."""

    vlan_id: int
    status: str  # 'self', ... kept as printed
    mac: str
    interface: str  # as printed: 'Port-1/1', 'Port-cpp' (the switch's own CPU)
    port: str | None  # '1/1' when the interface is a front port, else None
    smlt_remote: bool
    tunnel: str | None  # None when printed '-'


# Anchored on the right: every column after NAME is a single word, so a name
# with spaces, or one wider than its column, cannot shift the other values.
_VLAN_COLUMNS = (
    r"(?P<vlan_id>\d+)\s+(?P<name>.*?)\s+(?P<vlan_type>\S+)\s+(?P<mstp>\d+)\s+"
    r"(?P<protocol>\S+)\s+(?P<subnet>\S+)\s+(?P<mask>\S+)\s+(?P<vrf>\d+)\s+(?P<origin>\S+)"
)
_VLAN_ROW = re.compile(_VLAN_COLUMNS)
_MAC_ROW = re.compile(
    r"(?P<vlan_id>\d+)\s+(?P<status>\S+)\s+(?P<mac>\S+)\s+(?P<interface>\S+)\s+"
    r"(?P<smlt_remote>\S+)\s+(?P<tunnel>\S+)"
)
_VLAN_ROW_9X = re.compile(_VLAN_COLUMNS + r"\s+(?P<l3_access>\S+)")  # 9.x adds L3 ACCESS


@parser("show vlan basic")
def parse_vlans(output: Output) -> Iterator[Vlan]:
    """`show vlan basic` -> one Vlan per VLAN."""
    table = output.table("VLAN", "NAME", "TYPE", "VRFID")
    if table is None:
        return
    has_l3_access = table.has_columns("ACCESS")
    pattern = _VLAN_ROW_9X if has_l3_access else _VLAN_ROW

    def build(row: str) -> Vlan:
        cells = fullmatch(pattern, row)
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
            l3_access=optional(cells["l3_access"]) if has_l3_access else None,
        )

    yield from output.build_each(table.rows, build)


@parser("show vlan members")
def parse_vlan_members(output: Output) -> Iterator[VlanMembers]:
    """`show vlan members` -> one VlanMembers per VLAN, port lists expanded.

    Long port lists wrap onto continuation lines under their own column, so the
    columns are cut by position and the pieces joined again. 9.x prints a blank
    line after every VLAN, hence gaps=True.
    """
    table = output.table("VLAN", "PORT", "ACTIVE", "STATIC", gaps=True)
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
    """`show vlan i-sid` -> one VlanIsid per VLAN, I-SID None when unmapped.

    Cut by column: names can contain spaces, and 9.x adds a VLAN NAME column.
    """
    table = output.table("VLAN_ID", "I-SID")
    if table is None:
        return
    has_vlan_name = table.has_columns("VLAN", "NAME")
    labels = (
        ["VLAN_ID", "I-SID", "VLAN", "I-SID"] if has_vlan_name else ["VLAN_ID", "I-SID", "I-SID"]
    )
    columns = Columns.locate(table.header, *labels)

    def build(cells: list[str]) -> VlanIsid:
        vlan_id, isid, *names = cells
        vlan_name, isid_name = names if has_vlan_name else ("", *names)
        return VlanIsid(
            vlan_id=int(vlan_id),
            isid=optional_int(isid),
            isid_name=optional(isid_name),
            vlan_name=optional(vlan_name),
        )

    yield from output.build_each(map(columns.cut, table.rows), build)


@parser("show vlan mac-address-entry")
def parse_mac_entries(output: Output) -> Iterator[MacEntry]:
    """`show vlan mac-address-entry` -> one MacEntry per FDB entry."""
    table = output.table("VLAN", "MAC", "INTERFACE", "TUNNEL")
    if table is None:
        return

    def build(row: str) -> MacEntry:
        cells = fullmatch(_MAC_ROW, row)
        return MacEntry(
            vlan_id=int(cells["vlan_id"]),
            status=cells["status"],
            mac=mac(cells["mac"]),
            interface=cells["interface"],
            port=port_of(cells["interface"]),
            smlt_remote=flag(cells["smlt_remote"]),
            tunnel=optional(cells["tunnel"]),
        )

    yield from output.build_each(table.rows, build)
