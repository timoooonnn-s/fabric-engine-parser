"""Port tables of `show interfaces gigabitEthernet ...`.

The bare `show interfaces gigabitEthernet` prints several tables on some
releases (Port Interface, Port Name, Port Config) and is rejected on others,
where `... interface` has to be used. Each parser below looks for its own
table, so the bare command's output can be given to any of them.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime

from fabric_weft.output import Output, fullmatch
from fabric_weft.registry import parser
from fabric_weft.tables import Columns, header_line_with
from fabric_weft.values import (
    PORT,
    PORT_LIST,
    flag,
    int_list,
    mac,
    optional,
    optional_int,
    port,
    timestamp,
)


@dataclass(frozen=True, slots=True)
class PortInterface:
    port: str
    ifindex: int
    description: str  # the media type the switch reports, e.g. '10GbSR'
    link_trap: bool
    port_lock: bool
    mtu: int
    mac: str
    admin_up: bool
    oper_up: bool


@dataclass(frozen=True, slots=True)
class PortName:
    port: str
    name: str | None
    description: str
    link_trap: bool | None  # None: not printed (9.x)
    oper_up: bool
    duplex: str | None  # 'full' / 'half'; None while the port is down
    speed_mbps: int
    vlan_mode: str | None = None  # 9.x VLAN column: 'Tagged' / 'Access', as printed


@dataclass(frozen=True, slots=True)
class PortVlans:
    """How a port handles VLANs: tagging, default VLAN, memberships."""

    port: str
    tagging: bool  # TAGGING enable: the port sends and accepts 802.1Q tags
    discard_tagged_frames: bool
    discard_untagged_frames: bool
    default_vlan_id: int | None  # None when printed 0 (no default VLAN)
    vlan_ids: tuple[int, ...]  # () when printed 0 (member of no VLAN)
    port_type: str  # 'normal', ... kept as printed
    untag_default_vlan: bool
    dynamic_vlans: str | None  # as printed: 'P' (protocol enabled, see the legend)
    untagged_vlan_ids: tuple[int, ...]
    flex_uni: bool | None = None  # 9.x 'FA/Flex UNI' column; None: not printed


@dataclass(frozen=True, slots=True)
class PortIsid:
    """One I-SID endpoint on a port."""

    port: str
    ifindex: int
    isid: int
    vlan_id: int | None  # the platform VLAN of a CVLAN I-SID; None: 'N/A'
    customer_vid: int | None  # None: 'N/A' (a CVLAN I-SID has no customer VID)
    isid_type: str  # 'CVLAN', 'ELAN', ... kept as printed
    origin: str  # flag slots as printed, see `Isid.origin`
    isid_name: str | None
    bpdu: str | None  # as printed; None when empty
    mac_suni: bool


@dataclass(frozen=True, slots=True)
class PortState:
    port: str
    admin_up: bool
    oper_up: bool
    reason: str | None  # who or what changed the state last, e.g. 'SSH'
    changed_at: datetime | None
    flex_uni: bool | None = None  # 9.x 'FA/Flex UNI' column; None: not printed


_INTERFACE_ROW = re.compile(
    rf"(?P<port>{PORT})\s+(?P<ifindex>\d+)\s+(?:(?P<description>\S.*?)\s+)?"
    r"(?P<link_trap>\S+)\s+(?P<port_lock>\S+)\s+(?P<mtu>\d+)\s+(?P<mac>\S+)\s+"
    r"(?P<admin>\S+)\s+(?P<oper>\S+)"
)
_STATE_COLUMNS = (
    rf"(?P<port>{PORT})\s+(?P<admin>\S+)\s+(?P<oper>\S+)"
    r"(?:\s+(?P<reason>.*?))?(?:\s+(?P<changed>\d\d/\d\d/\d\d \d\d:\d\d:\d\d))?"
)
_STATE_ROW = re.compile(_STATE_COLUMNS)
_STATE_ROW_9X = re.compile(_STATE_COLUMNS + r"\s+(?P<flex_uni>\S+)")  # 9.x adds FA/Flex UNI


@parser(
    "show interfaces gigabitethernet",
    "show interfaces gigabitethernet interface",
    arguments=PORT_LIST,
)
def parse_port_interfaces(output: Output) -> Iterator[PortInterface]:
    """`show interfaces gigabitEthernet [interface]` -> one PortInterface per port."""
    table = output.table("INDEX", "DESCRIPTION", "MTU")
    if table is None:
        return

    def build(row: str) -> PortInterface:
        cells = fullmatch(_INTERFACE_ROW, row)
        return PortInterface(
            port=cells["port"],
            ifindex=int(cells["ifindex"]),
            description=cells["description"] or "",
            link_trap=flag(cells["link_trap"]),
            port_lock=flag(cells["port_lock"]),
            mtu=int(cells["mtu"]),
            mac=mac(cells["mac"]),
            admin_up=flag(cells["admin"]),
            oper_up=flag(cells["oper"]),
        )

    yield from output.build_each(table.rows, build)


@parser("show interfaces gigabitethernet name", arguments=PORT_LIST)
def parse_port_names(output: Output) -> Iterator[PortName]:
    """`show interfaces gigabitEthernet name` -> one PortName per port.

    Names may be empty or contain spaces, so the columns are cut by position.
    9.x drops LINKTRAP and adds VLAN (Tagged / Access).
    """
    table = output.table("NAME", "DESCRIPTION", "DUPLEX", "SPEED")
    if table is None:
        return
    has_link_trap = table.has_columns("LINKTRAP")
    has_vlan_mode = table.has_columns("VLAN")
    labels = ["NUM", "NAME", "DESCRIPTION"]
    labels += ["LINKTRAP"] if has_link_trap else []
    labels += ["STATUS", "DUPLEX", "SPEED"]
    labels += ["VLAN"] if has_vlan_mode else []
    columns = Columns.locate(header_line_with(table, "DUPLEX"), *labels)

    def build(cells: list[str]) -> PortName:
        number, name, description = cells[:3]
        link_trap = cells[3] if has_link_trap else None
        status, duplex, speed, *vlan_mode = cells[4:] if has_link_trap else cells[3:]
        oper_up = flag(status)
        return PortName(
            port=port(number),
            name=name or None,
            description=description,
            link_trap=flag(link_trap) if link_trap is not None else None,
            oper_up=oper_up,
            duplex=optional(duplex) if oper_up else None,
            speed_mbps=int(speed),
            vlan_mode=optional(vlan_mode[0]) if vlan_mode else None,
        )

    yield from output.build_each(columns.cut_rows(table.rows), build)


@parser("show interfaces gigabitethernet state", arguments=PORT_LIST)
def parse_port_states(output: Output) -> Iterator[PortState]:
    """`show interfaces gigabitEthernet state` -> one PortState per port."""
    table = output.table("ADMINSTATUS", "PORTSTATE")
    if table is None:
        return
    has_flex_uni = table.has_columns("FA/FLEX")
    pattern = _STATE_ROW_9X if has_flex_uni else _STATE_ROW

    def build(row: str) -> PortState:
        cells = fullmatch(pattern, row)
        return PortState(
            port=cells["port"],
            admin_up=flag(cells["admin"]),
            oper_up=flag(cells["oper"]),
            reason=optional(cells["reason"] or ""),
            changed_at=timestamp(cells["changed"] or ""),
            flex_uni=flag(cells["flex_uni"]) if has_flex_uni else None,
        )

    yield from output.build_each(table.rows, build)


def _vlan_ids(cell: str) -> tuple[int, ...]:
    """'4051,4052' or '4051 4052' -> (4051, 4052). '0' or empty -> () (VLAN 0 is not a VLAN)."""
    vlan_ids = int_list(cell.replace(",", " "))
    return () if vlan_ids == (0,) else vlan_ids


@parser("show interfaces gigabitethernet vlan", arguments=PORT_LIST)
def parse_port_vlans(output: Output) -> Iterator[PortVlans]:
    """`show interfaces gigabitEthernet vlan` -> one PortVlans per port.

    Cut by column: the VLAN lists can be empty, and long ones wrap onto the next line.
    """
    table = output.table("TAGGING", "DEFVLAN")
    if table is None:
        return
    has_flex_uni = table.has_columns("FLEX")
    labels = ["NUM", "TAGGING", "TAGFRAM", "UNTAGFRAM", "VLANID", "IDS", "TYPE", "DEFVLAN"]
    labels += ["VLANS", "VLANS"]  # DYNAMIC VLANS, UNTAG VLANS
    labels += ["FLEX"] if has_flex_uni else []
    columns = Columns.locate(table.header, *labels)

    def build(cells: list[str]) -> PortVlans:
        number, tagging, discard_tagged, discard_untagged, default_vlan, vlans = cells[:6]
        port_type, untag_default, dynamic, untagged, *flex_uni = cells[6:]
        default_vlan_id = int(default_vlan)
        return PortVlans(
            port=port(number),
            tagging=flag(tagging),
            discard_tagged_frames=flag(discard_tagged),
            discard_untagged_frames=flag(discard_untagged),
            default_vlan_id=default_vlan_id or None,
            vlan_ids=_vlan_ids(vlans),
            port_type=port_type,
            untag_default_vlan=flag(untag_default),
            dynamic_vlans=optional(dynamic),
            untagged_vlan_ids=_vlan_ids(untagged),
            flex_uni=flag(flex_uni[0]) if flex_uni else None,
        )

    yield from output.build_each(columns.cut_rows(table.rows), build)


@parser("show interfaces gigabitethernet i-sid", arguments=PORT_LIST)
def parse_port_isids(output: Output) -> Iterator[PortIsid]:
    """`show interfaces gigabitEthernet i-sid` -> one PortIsid per port and I-SID.

    Cut by column across both header lines: ORIGIN and NAME contain spaces, BPDU can
    be empty.
    """
    table = output.table("PORTNUM", "IFINDEX", "SUNI")
    if table is None:
        return
    columns = Columns.locate(
        table.header,
        "PORTNUM",
        "IFINDEX",
        "ID",
        "VLANID",
        "C-VID",
        "TYPE",
        "ORIGIN",
        "NAME",
        "BPDU",
        "SUNI",
    )

    def build(cells: list[str]) -> PortIsid:
        number, ifindex, isid, vlan_id, customer_vid, isid_type, origin = cells[:7]
        name, bpdu, mac_suni = cells[7:]
        if not isid_type or not origin:
            raise ValueError("line does not have the expected format")
        return PortIsid(
            port=port(number),
            ifindex=int(ifindex),
            isid=int(isid),
            vlan_id=optional_int(vlan_id),
            customer_vid=optional_int(customer_vid),
            isid_type=isid_type,
            origin=origin,
            isid_name=optional(name),
            bpdu=optional(bpdu),
            mac_suni=flag(mac_suni),
        )

    yield from output.build_each(map(columns.cut, table.rows), build)
