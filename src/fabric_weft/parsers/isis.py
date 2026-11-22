"""IS-IS, the control plane of the SPB fabric.

`show isis adjacencies` and `show isis interface` right-align their numbers under the
header (UPTIME, HOLDTIME), so the values do not start where the labels do: their rows
are read with patterns anchored on the numbers and the system ID.

`show isis spbm nick-name` and `show isis spbm unicast-fib` print every value where its
label starts, and some cells can be empty (a node without a nickname), so they are cut
by column.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import timedelta

from fabric_weft.output import Output, fullmatch
from fabric_weft.registry import parser
from fabric_weft.tables import Columns
from fabric_weft.values import PORT, SYSTEM_ID, duration, flag, mac, nickname, optional, system_id


@dataclass(frozen=True, slots=True)
class IsisAdjacency:
    """One IS-IS neighbour, seen from this switch."""

    interface: str  # as printed: 'Port1/1'
    port: str | None  # '1/1' when the interface is a port, else None
    level: str  # '1' as printed
    state: str  # 'UP', 'INIT', ... kept as printed
    uptime: timedelta
    priority: int
    hold_time_seconds: int
    system_id: str  # of the neighbour, 'xxxx.xxxx.xxxx'
    host_name: str
    status: str  # 'ACTIVE', ... kept as printed
    area: str  # 'HOME' / 'REMOTE'
    area_name: str | None


@dataclass(frozen=True, slots=True)
class IsisInterface:
    """One interface IS-IS runs on, with its SPBM metric."""

    interface: str  # as printed: 'Port1/1'
    port: str | None  # '1/1' when the interface is a port, else None
    circuit_type: str  # 'pt-pt', ... kept as printed
    level: str  # '1' from 'Level 1'
    oper_up: bool
    admin_up: bool
    adjacency_count: int  # ADJ
    up_adjacency_count: int  # UP ADJ
    admin_l1_metric: int  # ADM-SPBM L1-METRIC
    oper_l1_metric: int  # OPER-SPBM L1-METRIC
    origin: str  # 'CONFIG', ... kept as printed
    area: str
    area_name: str | None


@dataclass(frozen=True, slots=True)
class SpbmNickname:
    """One node of the SPB fabric, from its link-state packet."""

    lsp_id: str  # 'xxxx.xxxx.xxxx.00-00' as printed
    system_id: str  # the first part of the LSP ID, to join with adjacencies and FIB entries
    lifetime_seconds: int
    nickname: str | None  # None: the node has no nickname
    virtual_bmac: str  # as printed, normalised; 00:00:00:00:00:00 when the node has none
    host_name: str | None
    area: str
    area_name: str | None


@dataclass(frozen=True, slots=True)
class SpbmUnicastRoute:
    """One SPBM unicast FIB entry: how this switch reaches a backbone MAC in a B-VLAN."""

    destination_mac: str
    bvlan: int
    system_id: str  # of the node that owns the destination
    host_name: str | None
    outgoing_interface: str  # as printed: '1/2', 'cpp' (this switch itself)
    port: str | None  # '1/2' when the outgoing interface is a port, else None
    cost: int
    area: str
    area_name: str | None


_PORT_INTERFACE = re.compile(rf"Port(?P<port>{PORT})")
_LSP_ID = re.compile(rf"(?P<system_id>{SYSTEM_ID})\.[0-9a-f]{{2}}-[0-9a-f]{{2}}")
_BARE_PORT = re.compile(PORT)
# The host name is required: an adjacency printed without one would make the
# columns after it ambiguous, so such a row is reported instead of guessed.
_ADJACENCY_ROW = re.compile(
    r"(?P<interface>\S+)\s+(?P<level>\S+)\s+(?P<state>\S+)\s+(?P<uptime>.+?)\s+"
    rf"(?P<priority>\d+)\s+(?P<hold>\d+)\s+(?P<system_id>{SYSTEM_ID})\s+(?P<host>\S+)\s+"
    r"(?P<status>\S+)\s+(?P<area>\S+)(?:\s+(?P<area_name>.+))?"
)
_INTERFACE_ROW = re.compile(
    r"(?P<interface>\S+)\s+(?P<type>\S+)\s+Level\s+(?P<level>\S+)\s+(?P<oper>\S+)\s+"
    r"(?P<admin>\S+)\s+(?P<adjacencies>\d+)\s+(?P<up>\d+)\s+(?P<admin_metric>\d+)\s+"
    r"(?P<oper_metric>\d+)\s+(?P<origin>\S+)\s+(?P<area>\S+)(?:\s+(?P<area_name>.+))?"
)


def _port_of(interface: str) -> str | None:
    """'Port1/1' -> '1/1'. Other interface kinds are not mapped until a capture shows one."""
    found = _PORT_INTERFACE.fullmatch(interface)
    return found["port"] if found else None


@parser("show isis adjacencies")
def parse_isis_adjacencies(output: Output) -> Iterator[IsisAdjacency]:
    """`show isis adjacencies` -> one IsisAdjacency per neighbour."""
    table = output.table("INTERFACE", "SYSID", "HOLDTIME")
    if table is None:
        return

    def build(row: str) -> IsisAdjacency:
        cells = fullmatch(_ADJACENCY_ROW, row)
        return IsisAdjacency(
            interface=cells["interface"],
            port=_port_of(cells["interface"]),
            level=cells["level"],
            state=cells["state"],
            uptime=duration(cells["uptime"]),
            priority=int(cells["priority"]),
            hold_time_seconds=int(cells["hold"]),
            system_id=cells["system_id"],
            host_name=cells["host"],
            status=cells["status"],
            area=cells["area"],
            area_name=optional(cells["area_name"] or ""),
        )

    yield from output.build_each(table.rows, build)


@parser("show isis interface")
def parse_isis_interfaces(output: Output) -> Iterator[IsisInterface]:
    """`show isis interface` -> one IsisInterface per IS-IS interface."""
    table = output.table("INTERFACE", "ADM-SPBM", "OPER-SPBM")
    if table is None:
        return

    def build(row: str) -> IsisInterface:
        cells = fullmatch(_INTERFACE_ROW, row)
        return IsisInterface(
            interface=cells["interface"],
            port=_port_of(cells["interface"]),
            circuit_type=cells["type"],
            level=cells["level"],
            oper_up=flag(cells["oper"]),
            admin_up=flag(cells["admin"]),
            adjacency_count=int(cells["adjacencies"]),
            up_adjacency_count=int(cells["up"]),
            admin_l1_metric=int(cells["admin_metric"]),
            oper_l1_metric=int(cells["oper_metric"]),
            origin=cells["origin"],
            area=cells["area"],
            area_name=optional(cells["area_name"] or ""),
        )

    yield from output.build_each(table.rows, build)


@parser("show isis spbm nick-name")
def parse_spbm_nicknames(output: Output) -> Iterator[SpbmNickname]:
    """`show isis spbm nick-name` -> one SpbmNickname per node in the link-state database."""
    table = output.table("LSP", "NICK-NAME", "VIRTUAL-BMAC")
    if table is None:
        return
    columns = Columns.locate(
        table.header, "LSP", "LIFETIME", "NICK-NAME", "VIRTUAL-BMAC", "HOST-NAME", "AREA", "AREA"
    )

    def build(cells: list[str]) -> SpbmNickname:
        lsp_id, lifetime, nick, virtual_bmac, host, area, area_name = cells
        lsp = _LSP_ID.fullmatch(lsp_id)
        if lsp is None or not area:
            raise ValueError("line does not have the expected format")
        return SpbmNickname(
            lsp_id=lsp_id,
            system_id=lsp["system_id"],
            lifetime_seconds=int(lifetime),
            nickname=nickname(nick),
            virtual_bmac=mac(virtual_bmac),
            host_name=optional(host),
            area=area,
            area_name=optional(area_name),
        )

    yield from output.build_each(map(columns.cut, table.rows), build)


@parser("show isis spbm unicast-fib")
def parse_spbm_unicast_fib(output: Output) -> Iterator[SpbmUnicastRoute]:
    """`show isis spbm unicast-fib` -> one SpbmUnicastRoute per FIB entry."""
    table = output.table("DESTINATION", "BVLAN", "SYSID", "OUTGOING")
    if table is None:
        return
    columns = Columns.locate(
        table.header,
        "DESTINATION",
        "BVLAN",
        "SYSID",
        "HOST-NAME",
        "OUTGOING",
        "COST",
        "AREA",
        "AREA-NAME",
    )

    def build(cells: list[str]) -> SpbmUnicastRoute:
        destination, bvlan, system, host, interface, cost, area, area_name = cells
        if not interface or not area:
            raise ValueError("line does not have the expected format")
        return SpbmUnicastRoute(
            destination_mac=mac(destination),
            bvlan=int(bvlan),
            system_id=system_id(system),
            host_name=optional(host),
            outgoing_interface=interface,
            port=interface if _BARE_PORT.fullmatch(interface) else None,
            cost=int(cost),
            area=area,
            area_name=optional(area_name),
        )

    yield from output.build_each(map(columns.cut, table.rows), build)
