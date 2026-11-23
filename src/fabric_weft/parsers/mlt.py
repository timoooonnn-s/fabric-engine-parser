"""Link aggregation: `show mlt`, `show smlt mlt`, `show virtual-ist` and `show lacp interface`."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, TypeVar

from fabric_weft.output import Output, fullmatch
from fabric_weft.registry import parser
from fabric_weft.tables import Table
from fabric_weft.values import PORT, duration, flag, int_list, mac, optional, optional_as, ports


@dataclass(frozen=True, slots=True)
class Mlt:
    mlt_id: int
    ifindex: int
    name: str
    port_type: str  # 'trunk' / 'access'
    admin_type: str  # 'norm' / 'smlt'
    current_type: str
    members: tuple[str, ...]
    vlan_ids: tuple[int, ...]
    origin: str | None = None  # 9.x ORIGIN column ('CONFIG'); None: not printed
    # From the second to fourth table; None if a release does not print that table.
    designated_port: str | None = None
    lacp_enabled: bool | None = None
    lacp_oper_up: bool | None = None
    created_on: str | None = None  # 'LOC & REM' for an SMLT known to both vIST peers
    remote_members: tuple[str, ...] | None = None
    programmed_on: str | None = None  # 'LOCAL & REMOTE', 'LOCAL', ...
    dot1q_encapsulation: bool | None = None
    lossless: bool | None = None
    private_vlan: bool | None = None
    flex_uni: bool | None = None


@dataclass(frozen=True, slots=True)
class SmltMlt:
    """One MLT configured as SMLT (`show smlt mlt`)."""

    mlt_id: int
    admin_type: str  # 'smlt', as printed
    current_type: str  # 'smlt' while the vIST is up, 'norm' otherwise, as printed


@dataclass(frozen=True, slots=True)
class VirtualIst:
    peer_ip: str
    vlan_id: int
    enabled: bool
    up: bool
    dialect: str | None = None
    state: str | None = None
    role: str | None = None  # 'Master' / 'Slave'


@dataclass(frozen=True, slots=True)
class LacpParticipant:
    """One end of a LACP link as a port sees it: itself (actor) or its neighbour (partner)."""

    system_priority: int
    system_id: str  # a MAC; 00:00:00:00:00:00 when there is no partner
    key: int
    port_number: int  # printed in hex: '0xc0' -> 192
    port_priority: int
    state: tuple[str, ...]  # the flags as printed: ('act', 'long', 'indi')


@dataclass(frozen=True, slots=True)
class LacpPort:
    """The LACP settings and state of one port, merged from the five per-port tables."""

    port: str
    actor_admin: LacpParticipant
    actor_oper_key: int
    selected_aggregator_id: int  # 0: none
    attached_aggregator_id: int  # 0: none
    aggregating: bool  # AGGR
    actor_oper_state: tuple[str, ...]
    partner_admin: LacpParticipant
    partner_oper: LacpParticipant
    lacp_enabled_admin: bool
    lacp_enabled_oper: bool
    fast_periodic_ms_admin: int
    slow_periodic_ms_admin: int
    aggregation_wait_ms_admin: int
    timeout_scale_admin: int
    fast_periodic_ms_oper: int
    slow_periodic_ms_oper: int
    aggregation_wait_ms_oper: int
    timeout_scale_oper: int


@dataclass(frozen=True, slots=True)
class LacpAggregator:
    """One LACP aggregator (an MLT), from the 'LACP Aggregator Information' tables."""

    mlt_id: int
    ifindex: int
    mac: str
    collector_max_delay: int
    aggregate_or_individual: str  # 'aggr' / 'indi', as printed
    members: tuple[str, ...]
    oper_up: bool
    last_change_uptime: timedelta  # the switch's uptime when the state last changed
    last_change_ago: timedelta | None  # how long ago that was; None when not printed
    actor_system_priority: int
    actor_system_id: str
    actor_admin_key: int
    actor_oper_key: int
    partner_system_priority: int
    partner_system_id: str  # 00:00:00:00:00:00 while there is no partner
    partner_oper_key: int


_MLT_INFO_ROW = re.compile(
    r"(?P<mlt_id>\d+)\s+(?P<ifindex>\d+)\s+(?P<name>.*?)\s+(?P<port_type>trunk|access)\s+"
    r"(?P<admin>\S+)\s+(?P<current>\S+)(?:\s+(?P<members>\S*/\S*))?"
    # 9.x adds ORIGIN before VLAN IDS; it is a word, the members contain '/'
    r"(?:\s+(?P<origin>[A-Za-z]\S*))?(?:\s+(?P<vlans>[\d ]+))?"
)
_VLAN_CONTINUATION = re.compile(r"\d+(?: +\d+)*")
_LACP_ROW = re.compile(
    r"(?P<mlt_id>\d+)\s+\d+\s+(?:(?P<designated>\S+)\s+)?(?P<admin>\S+)\s+(?P<oper>\S+)"
)
# 9.4 prints both member lists empty while no port is up; lists always contain '/'.
_DATA_PATH_ROW = re.compile(
    r"(?P<mlt_id>\d+)\s+.*?\s+(?P<created>LOC & REM|\S+)\s+"
    r"(?:(?P<local>\S*/\S*)\s+)?(?:(?P<remote>\S*/\S*)\s+)?(?P<programmed>.+)"
)
_ENCAP_ROW = re.compile(
    r"(?P<mlt_id>\d+)\s+\d+\s+(?P<dot1q>\S+)\s+(?P<lossless>\S+)\s+(?P<pvlan>\S+)\s+\S+\s+\S+\s+"
    r"(?P<flex_uni>\S+)"
)
_IST_ROW = re.compile(r"(?P<peer>\S+)\s+(?P<vlan_id>\d+)\s+(?P<enabled>\S+)\s+(?P<status>\S+)")
_IST_STATE_ROW = re.compile(r"(?P<dialect>\S+)\s+(?P<state>.+?)\s+(?P<role>\S+)")


def _lacp_columns(cells: re.Match[str]) -> dict[str, Any]:
    return {
        # 9.4 prints 'null' when no port is designated (no member is up)
        "designated_port": None if cells["designated"] in (None, "null") else cells["designated"],
        "lacp_enabled": flag(cells["admin"]),
        "lacp_oper_up": flag(cells["oper"]),
    }


def _data_path_columns(cells: re.Match[str]) -> dict[str, Any]:
    return {
        "created_on": cells["created"],
        "remote_members": ports(cells["remote"] or ""),
        "programmed_on": cells["programmed"],
    }


def _encapsulation_columns(cells: re.Match[str]) -> dict[str, Any]:
    return {
        "dot1q_encapsulation": flag(cells["dot1q"]),
        "lossless": flag(cells["lossless"]),
        "private_vlan": optional_as(flag, cells["pvlan"]),  # 9.4 prints '-' for none
        "flex_uni": flag(cells["flex_uni"]),
    }


# The tables `show mlt` prints after Mlt Info: (header labels, row pattern, column reader).
_SECONDARY_TABLES: tuple[
    tuple[tuple[str, ...], re.Pattern[str], Callable[[re.Match[str]], dict[str, Any]]], ...
] = (
    (("DESIGNATED", "LACP"), _LACP_ROW, _lacp_columns),
    (("CREATED", "PROGRAMMED"), _DATA_PATH_ROW, _data_path_columns),
    (("ENCAP", "LOSSLESS"), _ENCAP_ROW, _encapsulation_columns),
)


@parser("show mlt")
def parse_mlts(output: Output) -> Iterator[Mlt]:
    """`show mlt` -> one Mlt per MLT, merged from the four tables the command prints."""
    info = output.table("MLTID", "IFINDEX", "NAME", "MEMBERS")
    if info is None:
        return
    fields: dict[int, dict[str, Any]] = {}
    current: dict[str, Any] | None = None  # last MLT row, for wrapped VLAN IDS lines
    for row in info.rows:
        if current is not None and _VLAN_CONTINUATION.fullmatch(row.strip()):
            current["vlan_ids"] += int_list(row)
            continue
        current = None
        try:
            cells = fullmatch(_MLT_INFO_ROW, row)
            current = fields[int(cells["mlt_id"])] = {
                "mlt_id": int(cells["mlt_id"]),
                "ifindex": int(cells["ifindex"]),
                "name": cells["name"],
                "port_type": cells["port_type"],
                "admin_type": cells["admin"],
                "current_type": cells["current"],
                "members": ports(cells["members"] or ""),
                "vlan_ids": int_list(cells["vlans"] or ""),
                "origin": cells["origin"],
            }
        except ValueError as error:
            output.skip(row, str(error))

    for labels, pattern, read in _SECONDARY_TABLES:
        table = output.table(*labels, required=False)
        _merge(
            output,
            fields,
            table,
            pattern,
            read,
            key=lambda cells: int(cells["mlt_id"]),
            missing="MLT id not in the Mlt Info table",
        )
    for values in fields.values():
        yield Mlt(**values)


KeyT = TypeVar("KeyT")


def _merge(
    output: Output,
    fields: dict[KeyT, dict[str, Any]],
    table: Table | None,
    pattern: re.Pattern[str],
    read: Callable[[re.Match[str]], dict[str, Any]],
    *,
    key: Callable[[re.Match[str]], KeyT],
    missing: str,
) -> None:
    """Add the columns of a secondary table to the records its rows' keys name.

    `show mlt` and `show lacp interface` print one record over several tables. A row
    whose key is not in the first table is reported, not dropped.
    """
    for row in table.rows if table else ():
        try:
            cells = fullmatch(pattern, row)
            target = fields.get(key(cells))
            if target is None:
                raise ValueError(missing)
            target.update(read(cells))
        except ValueError as error:
            output.skip(row, str(error))


@parser("show virtual-ist")
def parse_virtual_ist(output: Output) -> Iterator[VirtualIst]:
    """`show virtual-ist` -> the vIST of this switch (no record if none is configured)."""
    table = output.table("PEER-IP", "IST")
    if table is None:
        return
    state_table = output.table("DIALECT", "STATE", required=False)
    state_rows = state_table.rows if state_table else ()

    def build(row: str) -> VirtualIst:
        cells = fullmatch(_IST_ROW, row)
        state = fullmatch(_IST_STATE_ROW, state_rows[0]) if state_rows else None
        return VirtualIst(
            peer_ip=cells["peer"],
            vlan_id=int(cells["vlan_id"]),
            enabled=flag(cells["enabled"]),
            up=flag(cells["status"]),
            dialect=optional(state["dialect"]) if state else None,
            state=state["state"] if state else None,
            role=state["role"] if state else None,
        )

    yield from output.build_each(table.rows, build)


_PARTICIPANT_ROW = re.compile(
    rf"(?P<port>{PORT})\s+(?P<priority>\d+)\s+(?P<system_id>\S+)\s+(?P<key>\d+)\s+"
    r"(?P<number>0x[0-9a-f]+)\s+(?P<port_priority>\d+)\s+(?P<state>\S.*)"
)
_ACTOR_OPER_ROW = re.compile(
    rf"(?P<port>{PORT})\s+(?P<key>\d+)\s+(?P<selected>\d+)\s+(?P<attached>\d+)\s+"
    r"(?P<aggregating>\S+)\s+(?P<state>\S.*)"
)
_EXTENSION_ROW = re.compile(rf"(?P<port>{PORT})\s+(?P<admin>\S+)\s+(?P<oper>\S+)" + r"\s+(\d+)" * 8)
_PARTICIPANT_LABELS = ("INDEX", "SYS", "KEY", "STATE")


def _participant(field: str) -> Callable[[re.Match[str]], dict[str, Any]]:
    def read(cells: re.Match[str]) -> dict[str, Any]:
        participant = LacpParticipant(
            system_priority=int(cells["priority"]),
            system_id=mac(cells["system_id"]),
            key=int(cells["key"]),
            port_number=int(cells["number"], 16),
            port_priority=int(cells["port_priority"]),
            state=tuple(cells["state"].split()),
        )
        return {field: participant}

    return read


def _actor_oper(cells: re.Match[str]) -> dict[str, Any]:
    return {
        "actor_oper_key": int(cells["key"]),
        "selected_aggregator_id": int(cells["selected"]),
        "attached_aggregator_id": int(cells["attached"]),
        "aggregating": flag(cells["aggregating"]),
        "actor_oper_state": tuple(cells["state"].split()),
    }


def _extension(cells: re.Match[str]) -> dict[str, Any]:
    timers = [int(value) for value in cells.groups()[3:]]
    names = ("fast_periodic_ms", "slow_periodic_ms", "aggregation_wait_ms", "timeout_scale")
    return {
        "lacp_enabled_admin": flag(cells["admin"]),
        "lacp_enabled_oper": flag(cells["oper"]),
        **{f"{name}_admin": value for name, value in zip(names, timers[:4], strict=True)},
        **{f"{name}_oper": value for name, value in zip(names, timers[4:], strict=True)},
    }


# (title, header labels, row pattern, column reader). Three tables share one header,
# so they are told apart by their titles.
_LACP_TABLES: tuple[
    tuple[str, tuple[str, ...], re.Pattern[str], Callable[[re.Match[str]], dict[str, Any]]], ...
] = (
    ("Actor Admin", _PARTICIPANT_LABELS, _PARTICIPANT_ROW, _participant("actor_admin")),
    ("Actor Oper", ("INDEX", "SELECTED", "ATTACHED"), _ACTOR_OPER_ROW, _actor_oper),
    ("Partner Admin", _PARTICIPANT_LABELS, _PARTICIPANT_ROW, _participant("partner_admin")),
    ("Partner Operational", _PARTICIPANT_LABELS, _PARTICIPANT_ROW, _participant("partner_oper")),
    ("LACP Extension", ("INDEX", "AGGRWAIT", "TIMEOUT"), _EXTENSION_ROW, _extension),
)


@parser("show lacp interface")
def parse_lacp_ports(output: Output) -> Iterator[LacpPort]:
    """`show lacp interface` -> one LacpPort per port, merged from the per-port tables.

    The LACP Aggregator tables after them (per MLT) are not read yet: no capture
    has shown them with rows.
    """
    tables = [
        (output.table(*labels, title=title), pattern, read)
        for title, labels, pattern, read in _LACP_TABLES
    ]
    if any(table is None for table, _, _ in tables):
        return
    (first, first_pattern, read_first), *rest = tables
    fields: dict[str, dict[str, Any]] = {}
    for row in first.rows:  # type: ignore[union-attr]
        try:
            cells = fullmatch(first_pattern, row)
            fields[cells["port"]] = {"port": cells["port"], **read_first(cells)}
        except ValueError as error:
            output.skip(row, str(error))
    for table, pattern, read in rest:
        _merge(
            output,
            fields,
            table,
            pattern,
            read,
            key=lambda cells: cells["port"],
            missing="port not in the Actor Admin table",
        )
    for values in fields.values():
        try:
            yield LacpPort(**values)
        except TypeError:
            output.skip("", f"port {values['port']} is missing from one of the LACP tables")


_DURATION_TEXT = r"\d+ days?(?:\(s\))?, \d+:\d\d:\d\d"
_AGGREGATOR_ROW = re.compile(
    r"(?P<mlt_id>\d+)\s+(?P<ifindex>\d+)\s+(?P<mac>\S+)\s+(?P<delay>\d+)\s+(?P<aggr>\S+)"
    r"(?:\s+(?P<members>\S+))?"
)
_AGGREGATOR_STATE_ROW = re.compile(
    rf"(?P<mlt_id>\d+)\s+\d+\s+(?P<state>\S+)\s+(?P<last>{_DURATION_TEXT})"
    rf"(?:\s+\((?P<ago>{_DURATION_TEXT}) ago\))?"
)
_AGGREGATOR_ACTOR_ROW = re.compile(
    r"(?P<mlt_id>\d+)\s+\d+\s+(?P<priority>\d+)\s+(?P<system_id>\S+)\s+(?P<admin_key>\d+)\s+"
    r"(?P<oper_key>\d+)"
)
_AGGREGATOR_PARTNER_ROW = re.compile(
    r"(?P<mlt_id>\d+)\s+\d+\s+(?P<priority>\d+)\s+(?P<system_id>\S+)\s+(?P<oper_key>\d+)"
)


def _aggregator_state(cells: re.Match[str]) -> dict[str, Any]:
    return {
        "oper_up": flag(cells["state"]),
        "last_change_uptime": duration(cells["last"]),
        "last_change_ago": duration(cells["ago"]) if cells["ago"] else None,
    }


def _aggregator_actor(cells: re.Match[str]) -> dict[str, Any]:
    return {
        "actor_system_priority": int(cells["priority"]),
        "actor_system_id": mac(cells["system_id"]),
        "actor_admin_key": int(cells["admin_key"]),
        "actor_oper_key": int(cells["oper_key"]),
    }


def _aggregator_partner(cells: re.Match[str]) -> dict[str, Any]:
    return {
        "partner_system_priority": int(cells["priority"]),
        "partner_system_id": mac(cells["system_id"]),
        "partner_oper_key": int(cells["oper_key"]),
    }


@parser("show lacp interface", register=False)
def parse_lacp_aggregators(output: Output) -> Iterator[LacpAggregator]:
    """`show lacp interface` -> one LacpAggregator per MLT with LACP (decision 0017).

    Called directly: `parse("show lacp interface", ...)` returns the per-port records.
    The aggregator is spread over four untitled tables after 'LACP Aggregator
    Information', merged by MLT id like `show mlt`.
    """
    info = output.table("MAC", "COLLECTOR", "MAXDELAY", required=False)
    if info is None:  # printed only on a switch that has an LACP MLT
        return
    fields: dict[int, dict[str, Any]] = {}
    for row in info.rows:
        try:
            cells = fullmatch(_AGGREGATOR_ROW, row)
            fields[int(cells["mlt_id"])] = {
                "mlt_id": int(cells["mlt_id"]),
                "ifindex": int(cells["ifindex"]),
                "mac": mac(cells["mac"]),
                "collector_max_delay": int(cells["delay"]),
                "aggregate_or_individual": cells["aggr"],
                "members": ports(cells["members"] or ""),
            }
        except ValueError as error:
            output.skip(row, str(error))
    for labels, pattern, read in (
        (("OPER", "OPERLAST"), _AGGREGATOR_STATE_ROW, _aggregator_state),
        (("ACTOR", "ADMINKEY"), _AGGREGATOR_ACTOR_ROW, _aggregator_actor),
        (("PARTNER", "OPERKEY"), _AGGREGATOR_PARTNER_ROW, _aggregator_partner),
    ):
        _merge(
            output,
            fields,
            output.table(*labels),
            pattern,
            read,
            key=lambda cells: int(cells["mlt_id"]),
            missing="MLT id not in the LACP Aggregator Information table",
        )
    for values in fields.values():
        try:
            yield LacpAggregator(**values)
        except TypeError:
            output.skip("", f"MLT {values['mlt_id']} is missing from one of the aggregator tables")


_SMLT_ROW = re.compile(r"(?P<mlt_id>\d+)\s+(?P<admin>\S+)\s+(?P<current>\S+)")


@parser("show smlt mlt")
def parse_smlt_mlts(output: Output) -> Iterator[SmltMlt]:
    """`show smlt mlt` -> one SmltMlt per MLT configured as SMLT."""
    table = output.table("MLT", "ADMIN", "CURRENT")
    if table is None:
        return

    def build(row: str) -> SmltMlt:
        cells = fullmatch(_SMLT_ROW, row)
        return SmltMlt(int(cells["mlt_id"]), cells["admin"], cells["current"])

    yield from output.build_each(table.rows, build)
