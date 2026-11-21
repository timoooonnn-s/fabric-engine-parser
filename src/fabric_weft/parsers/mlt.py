"""Link aggregation: `show mlt` and `show virtual-ist`."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

from fabric_weft.output import Output, fullmatch
from fabric_weft.registry import parser
from fabric_weft.values import flag, int_list, optional, ports


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
