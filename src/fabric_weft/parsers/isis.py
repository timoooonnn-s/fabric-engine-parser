"""IS-IS, the control plane of the SPB fabric.

`show isis adjacencies` and `show isis interface` right-align their numbers under the
header (UPTIME, HOLDTIME), so the values do not start where the labels do: their rows
are read with patterns anchored on the numbers and the system ID.

`show isis spbm nick-name`, `show isis spbm unicast-fib` and `show isis system-id` print
every value where its label starts, and some cells can be empty (a node without a
nickname), so they are cut by column.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from fabric_weft.fields import required
from fabric_weft.output import Output, fullmatch
from fabric_weft.registry import parser
from fabric_weft.tables import Columns
from fabric_weft.values import (
    PORT,
    SYSTEM_ID,
    duration,
    flag,
    mac,
    nickname,
    optional,
    optional_int,
    system_id,
)


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
class IsisSystemId:
    """This switch's IS-IS system ID in one area. HOME is the one its neighbours see."""

    system_id: str
    area: str  # 'HOME' / 'REMOTE'
    area_name: str | None


@dataclass(frozen=True, slots=True)
class IsisSettings:
    """Global IS-IS settings of this switch (`show isis`). Empty values become None."""

    admin_enabled: bool
    router_type: str  # 'Level 1', ... kept as printed
    system_id: str
    max_lsp_gen_interval_seconds: int
    metric: str  # 'wide' / 'narrow'
    overload_on_startup_seconds: int
    overload: bool
    csnp_interval_seconds: int
    psnp_interval_seconds: int
    retransmit_lsp_interval_seconds: int
    spf_delay_ms: int
    router_name: str | None
    ip_source_address: str | None
    ipv6_source_address: str | None
    ip_tunnel_source_address: str | None
    tunnel_vrf: str | None
    ip_tunnel_mtu: int | None
    interface_count: int
    area_address_count: int
    inband_mgmt_clip_ip: str | None
    backbone_enabled: bool
    dynamically_learned_area: str | None
    fan_member: bool
    hello_padding: bool
    multi_area_oper_enabled: bool
    multi_area_flags: str | None  # 'home-always-up', ... kept as printed
    designated_bn_host_name: str | None
    designated_bn_home_system_id: str | None
    designated_bn_remote_system_id: str | None


@dataclass(frozen=True, slots=True)
class SpbmInstance:
    """One SPBM instance (`show isis spbm`), merged from its three tables."""

    instance: int
    bvlans: tuple[int, ...]
    primary_bvlan: int
    nickname: str | None  # None: no nickname yet
    lsdb_trap: bool
    ip_shortcuts: bool  # IP
    ipv6_shortcuts: bool  # IPV6
    multicast: bool
    spb_pim_gateway: bool
    stp_multi_homing: bool
    origin: str  # 'config' / 'dynamic', kept as printed
    # ISIS SPBM SMLT Info; None if the table is not printed
    smlt_split_beb: str | None = None  # 'primary' / 'secondary'
    smlt_virtual_bmac: str | None = None  # 00:00:00:00:00:00 without vIST
    smlt_peer_system_id: str | None = None
    smlt_peer_nickname: str | None = None
    smlt_peer_host_name: str | None = None
    # ISIS Remote SPBM Info (multi-area); as printed, '0.00.00' when not used
    remote_nickname: str | None = None


@dataclass(frozen=True, slots=True)
class IsisLsp:
    """One link-state packet in the IS-IS database (`show isis lsdb`)."""

    lsp_id: str  # 'xxxx.xxxx.xxxx.00-00' as printed
    system_id: str  # of the node that sent it
    level: str  # '1', as printed
    lifetime_seconds: int
    sequence_number: int  # printed in hex: '0x4' -> 4
    checksum: int  # printed in hex
    host_name: str | None
    area: str


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


@parser("show isis system-id")
def parse_isis_system_ids(output: Output) -> Iterator[IsisSystemId]:
    """`show isis system-id` -> one IsisSystemId per area (HOME, REMOTE)."""
    table = output.table("SYSTEM-ID", "AREA")
    if table is None:
        return
    columns = Columns.locate(table.header, "SYSTEM-ID", "AREA", "AREA-NAME")

    def build(cells: list[str]) -> IsisSystemId:
        system, area, area_name = cells
        if not area:
            raise ValueError("line does not have the expected format")
        return IsisSystemId(system_id(system), area, optional(area_name))

    yield from output.build_each(map(columns.cut, table.rows), build)


@parser("show isis")
def parse_isis_settings(output: Output) -> Iterator[IsisSettings]:
    """`show isis` -> one IsisSettings. The output is `Key : value` lines (decision 0009)."""
    fields = output.section("")
    if fields is None:
        return

    def text(key: str) -> str | None:
        return optional(required(fields, key))

    def number(key: str) -> int:
        return int(required(fields, key))

    def enabled(key: str) -> bool:
        return flag(required(fields, key))

    try:
        system = text("Designated BN Home System ID")
        remote = text("Designated BN Remote System ID")
        yield IsisSettings(
            admin_enabled=enabled("AdminState"),
            router_type=required(fields, "RouterType"),
            system_id=system_id(required(fields, "System ID")),
            max_lsp_gen_interval_seconds=number("Max LSP Gen Interval"),
            metric=required(fields, "Metric"),
            overload_on_startup_seconds=number("Overload-on-startup"),
            overload=enabled("Overload"),
            csnp_interval_seconds=number("Csnp Interval"),
            psnp_interval_seconds=number("PSNP Interval"),
            retransmit_lsp_interval_seconds=number("Rxmt LSP Interval"),
            spf_delay_ms=number("spf-delay"),
            router_name=text("Router Name"),
            ip_source_address=text("ip source-address"),
            ipv6_source_address=text("ipv6 source-address"),
            ip_tunnel_source_address=text("ip tunnel source-address"),
            tunnel_vrf=text("Tunnel vrf"),
            ip_tunnel_mtu=optional_int(required(fields, "ip tunnel mtu")),
            interface_count=number("Num of Interfaces"),
            area_address_count=number("Num of Area Addresses"),
            inband_mgmt_clip_ip=text("Inband Mgmt Clip Ip"),
            backbone_enabled=enabled("backbone"),
            dynamically_learned_area=text("Dynamically Learned Area"),
            fan_member=enabled("FAN Member"),
            hello_padding=enabled("Hello Padding"),
            multi_area_oper_enabled=enabled("Multi-Area OperState"),
            multi_area_flags=text("Multi-Area Flags"),
            designated_bn_host_name=text("Designated BN Hostname"),
            designated_bn_home_system_id=system_id(system) if system else None,
            designated_bn_remote_system_id=system_id(remote) if remote else None,
        )
    except ValueError as error:  # a missing field or a value that does not convert
        output.skip("", str(error))


def _vlan_ranges(cell: str) -> tuple[int, ...]:
    """'4051-4052' or '4051,4052' -> (4051, 4052)."""
    vlans: list[int] = []
    for chunk in filter(None, cell.split(",")):
        first, _, last = chunk.partition("-")
        vlans.extend(range(int(first), int(last or first) + 1))
    return tuple(vlans)


@parser("show isis spbm")
def parse_spbm_instances(output: Output) -> Iterator[SpbmInstance]:
    """`show isis spbm` -> one SpbmInstance per instance, merged from its three tables.

    Cut by column: the nickname is empty until one is assigned.
    """
    info = output.table("B-VID", "PRIMARY", "NICK")
    if info is None:
        return
    smlt = output.table("SMLT-SPLIT-BEB", "SMLT-VIRTUAL-BMAC", required=False)
    remote = output.table("SPBM", "NICK", title="ISIS Remote SPBM Info", required=False)
    fields: dict[int, dict[str, Any]] = {}

    info_columns = Columns.locate(
        info.header,
        "SPBM",
        "B-VID",
        "PRIMARY",
        "NICK",
        "LSDB",
        "IP",
        "IPV6",
        "MULTICAST",
        "SPB-PIM-GW",
        "STP-MULTI",
        "ORIGIN",
    )
    for row in info.rows:
        try:
            instance, bvlans, primary, nick, trap, ip, ipv6, multicast, pim_gw, stp, origin = (
                info_columns.cut(row)
            )
            if not origin:
                raise ValueError("line does not have the expected format")
            fields[int(instance)] = {
                "instance": int(instance),
                "bvlans": _vlan_ranges(bvlans),
                "primary_bvlan": int(primary),
                "nickname": nickname(nick),
                "lsdb_trap": flag(trap),
                "ip_shortcuts": flag(ip),
                "ipv6_shortcuts": flag(ipv6),
                "multicast": flag(multicast),
                "spb_pim_gateway": flag(pim_gw),
                "stp_multi_homing": flag(stp),
                "origin": origin,
            }
        except ValueError as error:
            output.skip(row, str(error))

    def merge(row: str, instance: str, values: dict[str, Any]) -> None:
        target = fields.get(int(instance))
        if target is None:
            raise ValueError("SPBM instance not in the ISIS SPBM Info table")
        target.update(values)

    if smlt is not None:
        smlt_columns = Columns.locate(
            smlt.header,
            "SPBM",
            "SMLT-SPLIT-BEB",
            "SMLT-VIRTUAL-BMAC",
            "SMLT-PEER-SYSTEM-ID",
            "SMLT-PEER-NICK-NAME",
            "SMLT-PEER-HOST-NAME",
        )
        for row in smlt.rows:
            try:
                instance, split_beb, virtual_bmac, peer, peer_nick, peer_host = smlt_columns.cut(
                    row
                )
                peer_system = optional(peer)
                merge(
                    row,
                    instance,
                    {
                        "smlt_split_beb": optional(split_beb),
                        "smlt_virtual_bmac": mac(virtual_bmac) if optional(virtual_bmac) else None,
                        "smlt_peer_system_id": system_id(peer_system) if peer_system else None,
                        "smlt_peer_nickname": nickname(peer_nick),
                        "smlt_peer_host_name": optional(peer_host),
                    },
                )
            except ValueError as error:
                output.skip(row, str(error))

    if remote is not None:
        remote_columns = Columns.locate(remote.header, "SPBM", "NICK")
        for row in remote.rows:
            try:
                instance, nick = remote_columns.cut(row)
                merge(row, instance, {"remote_nickname": nickname(nick)})
            except ValueError as error:
                output.skip(row, str(error))

    for values in fields.values():
        yield SpbmInstance(**values)


@parser("show isis lsdb")
def parse_isis_lsdb(output: Output) -> Iterator[IsisLsp]:
    """`show isis lsdb` -> one IsisLsp per link-state packet."""
    table = output.table("LSP", "SEQNUM", "CHKSUM")
    if table is None:
        return
    columns = Columns.locate(
        table.header, "LSP", "LEVEL", "LIFETIME", "SEQNUM", "CHKSUM", "HOST-NAME", "AREA"
    )

    def build(cells: list[str]) -> IsisLsp:
        lsp_id, level, lifetime, sequence, checksum, host, area = cells
        lsp = _LSP_ID.fullmatch(lsp_id)
        if lsp is None or not level or not area:
            raise ValueError("line does not have the expected format")
        return IsisLsp(
            lsp_id=lsp_id,
            system_id=lsp["system_id"],
            level=level,
            lifetime_seconds=int(lifetime),
            sequence_number=int(sequence, 16),
            checksum=int(checksum, 16),
            host_name=optional(host),
            area=area,
        )

    yield from output.build_each(map(columns.cut, table.rows), build)
