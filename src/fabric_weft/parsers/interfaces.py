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
from fabric_weft.values import PORT, flag, mac, optional, port, timestamp


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
    link_trap: bool
    oper_up: bool
    duplex: str | None  # 'full' / 'half'; None while the port is down
    speed_mbps: int


@dataclass(frozen=True, slots=True)
class PortState:
    port: str
    admin_up: bool
    oper_up: bool
    reason: str | None  # who or what changed the state last, e.g. 'SSH'
    changed_at: datetime | None


_INTERFACE_ROW = re.compile(
    rf"(?P<port>{PORT})\s+(?P<ifindex>\d+)\s+(?:(?P<description>\S.*?)\s+)?"
    r"(?P<link_trap>\S+)\s+(?P<port_lock>\S+)\s+(?P<mtu>\d+)\s+(?P<mac>\S+)\s+"
    r"(?P<admin>\S+)\s+(?P<oper>\S+)"
)
_STATE_ROW = re.compile(
    rf"(?P<port>{PORT})\s+(?P<admin>\S+)\s+(?P<oper>\S+)"
    r"(?:\s+(?P<reason>.*?))?(?:\s+(?P<changed>\d\d/\d\d/\d\d \d\d:\d\d:\d\d))?"
)


@parser("show interfaces gigabitethernet", "show interfaces gigabitethernet interface")
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


@parser("show interfaces gigabitethernet name")
def parse_port_names(output: Output) -> Iterator[PortName]:
    """`show interfaces gigabitEthernet name` -> one PortName per port.

    Names may be empty or contain spaces, so the columns are cut by position.
    """
    table = output.table("NAME", "DESCRIPTION", "DUPLEX", "SPEED")
    if table is None:
        return
    columns = Columns.locate(
        header_line_with(table, "DUPLEX"),
        "NUM",
        "NAME",
        "DESCRIPTION",
        "LINKTRAP",
        "STATUS",
        "DUPLEX",
        "SPEED",
    )

    def build(cells: list[str]) -> PortName:
        number, name, description, link_trap, status, duplex, speed = cells
        oper_up = flag(status)
        return PortName(
            port=port(number),
            name=name or None,
            description=description,
            link_trap=flag(link_trap),
            oper_up=oper_up,
            duplex=optional(duplex) if oper_up else None,
            speed_mbps=int(speed),
        )

    yield from output.build_each(columns.cut_rows(table.rows), build)


@parser("show interfaces gigabitethernet state")
def parse_port_states(output: Output) -> Iterator[PortState]:
    """`show interfaces gigabitEthernet state` -> one PortState per port."""
    table = output.table("ADMINSTATUS", "PORTSTATE")
    if table is None:
        return

    def build(row: str) -> PortState:
        cells = fullmatch(_STATE_ROW, row)
        return PortState(
            port=cells["port"],
            admin_up=flag(cells["admin"]),
            oper_up=flag(cells["oper"]),
            reason=optional(cells["reason"] or ""),
            changed_at=timestamp(cells["changed"] or ""),
        )

    yield from output.build_each(table.rows, build)
