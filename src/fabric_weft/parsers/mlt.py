"""Link aggregation: `show mlt`, `show virtual-ist` and `show lacp interface`."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

from fabric_weft.output import Output, fullmatch
from fabric_weft.registry import parser
from fabric_weft.values import PORT, flag, int_list, mac, optional, ports


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


_MLT_INFO_ROW = re.compile(
    r"(?P<mlt_id>\d+)\s+(?P<ifindex>\d+)\s+(?P<name>.*?)\s+(?P<port_type>trunk|access)\s+"
    r"(?P<admin>\S+)\s+(?P<current>\S+)(?:\s+(?P<members>\S*/\S*))?(?:\s+(?P<vlans>[\d ]+))?"
)
_VLAN_CONTINUATION = re.compile(r"\d+(?: +\d+)*")
_LACP_ROW = re.compile(
    r"(?P<mlt_id>\d+)\s+\d+\s+(?:(?P<designated>\d\S*)\s+)?(?P<admin>\S+)\s+(?P<oper>\S+)"
)
_DATA_PATH_ROW = re.compile(
    r"(?P<mlt_id>\d+)\s+.*?\s+(?P<created>LOC & REM|\S+)\s+(?P<local>\S+)\s+(?P<remote>\S+)\s+"
    r"(?P<programmed>.+)"
)
_ENCAP_ROW = re.compile(
    r"(?P<mlt_id>\d+)\s+\d+\s+(?P<dot1q>\S+)\s+(?P<lossless>\S+)\s+(?P<pvlan>\S+)\s+\S+\s+\S+\s+"
    r"(?P<flex_uni>\S+)"
)
_IST_ROW = re.compile(r"(?P<peer>\S+)\s+(?P<vlan_id>\d+)\s+(?P<enabled>\S+)\s+(?P<status>\S+)")
_IST_STATE_ROW = re.compile(r"(?P<dialect>\S+)\s+(?P<state>.+?)\s+(?P<role>\S+)")


def _lacp_columns(cells: re.Match[str]) -> dict[str, Any]:
    return {
        "designated_port": cells["designated"],
        "lacp_enabled": flag(cells["admin"]),
        "lacp_oper_up": flag(cells["oper"]),
    }


def _data_path_columns(cells: re.Match[str]) -> dict[str, Any]:
    return {
        "created_on": cells["created"],
        "remote_members": ports(cells["remote"]),
        "programmed_on": cells["programmed"],
    }


def _encapsulation_columns(cells: re.Match[str]) -> dict[str, Any]:
    return {
        "dot1q_encapsulation": flag(cells["dot1q"]),
        "lossless": flag(cells["lossless"]),
        "private_vlan": flag(cells["pvlan"]),
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
            }
        except ValueError as error:
            output.skip(row, str(error))

    for labels, pattern, read in _SECONDARY_TABLES:
        _merge(output, fields, labels, pattern, read)
    for values in fields.values():
        yield Mlt(**values)


def _merge(
    output: Output,
    fields: dict[int, dict[str, Any]],
    labels: tuple[str, ...],
    pattern: re.Pattern[str],
    read: Callable[[re.Match[str]], dict[str, Any]],
) -> None:
    """Add the columns of one of the secondary `show mlt` tables to the MLTs."""
    table = output.table(*labels, required=False)
    for row in table.rows if table else ():
        try:
            cells = fullmatch(pattern, row)
            target = fields.get(int(cells["mlt_id"]))
            if target is None:
                raise ValueError("MLT id not in the Mlt Info table")
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
    fields: dict[str, dict[str, Any]] = {}
    for index, (table, pattern, read) in enumerate(tables):
        for row in table.rows:  # type: ignore[union-attr]
            try:
                cells = fullmatch(pattern, row)
                if index == 0:
                    fields[cells["port"]] = {"port": cells["port"]}
                elif cells["port"] not in fields:
                    raise ValueError("port not in the Actor Admin table")
                fields[cells["port"]].update(read(cells))
            except ValueError as error:
                output.skip(row, str(error))
    for values in fields.values():
        try:
            yield LacpPort(**values)
        except TypeError:
            output.skip("", f"port {values['port']} is missing from one of the LACP tables")
