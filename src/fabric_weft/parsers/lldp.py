"""LLDP neighbours: `show lldp neighbor summary` and `show lldp neighbor`."""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from fabric_weft.output import Output
from fabric_weft.registry import parser
from fabric_weft.tables import Columns, header_line_with
from fabric_weft.values import PORT, optional, port


@dataclass(frozen=True, slots=True)
class LldpNeighborSummary:
    """One row of the summary. The switch cuts long values and marks them with '~'."""

    local_port: str
    protocol: str
    address: str | None
    chassis_id: str | None
    remote_port: str
    system_name: str | None
    system_description: str | None


@dataclass(frozen=True, slots=True)
class LldpNeighbor:
    """One neighbour block of the detailed output, values complete."""

    local_port: str
    index: int
    age: str  # as printed, e.g. '10 days, 02:33:19'
    protocol: str | None = None
    chassis_id_subtype: str | None = None  # e.g. 'MAC Address'
    chassis_id: str | None = None
    port_id_subtype: str | None = None
    port_id: str | None = None
    system_name: str | None = None
    system_description: str | None = None
    system_capabilities: str | None = None
    port_description: str | None = None
    address: str | None = None


_NEIGHBOR_START = re.compile(
    rf"Port:\s*(?P<port>{PORT})\s+Index:\s*(?P<index>\d+)\s+Time:\s*(?P<age>.+)"
)
_NEIGHBOR_FIELD = re.compile(r"\s+(?P<key>\w+)\s*:\s*(?P<value>.*)")
_BLOCK_END = re.compile(r"\s*(?:-{10,}|Total Neighbors\s*:.*)?")
_SUBTYPE_AND_VALUE = re.compile(r"(?P<subtype>.+?)\s{2,}(?P<value>\S.*)")
# key printed by the switch -> LldpNeighbor field
_FIELD_NAMES = {
    "protocol": "protocol",
    "sysname": "system_name",
    "sysdescr": "system_description",
    "syscap": "system_capabilities",
    "portdescr": "port_description",
    "address": "address",
}
_IDENTIFIERS = {"chassisid": "chassis_id", "portid": "port_id"}


@parser("show lldp neighbor summary")
def parse_lldp_summary(output: Output) -> Iterator[LldpNeighborSummary]:
    """`show lldp neighbor summary` -> one LldpNeighborSummary per neighbour.

    Cells can be empty (no SYSNAME) or contain spaces, so columns are cut by position.
    """
    table = output.table("SYSNAME", "SYSDESCR")
    if table is None:
        return
    columns = Columns.locate(
        header_line_with(table, "SYSNAME"),
        "PORT",
        "PROT",
        "ADDR",
        "ID",
        "PORT",
        "SYSNAME",
        "SYSDESCR",
    )

    def build(cells: list[str]) -> LldpNeighborSummary:
        local_port, protocol, address, chassis_id, remote_port, name, description = cells
        return LldpNeighborSummary(
            local_port=port(local_port),
            protocol=protocol,
            address=optional(address),
            chassis_id=optional(chassis_id),
            remote_port=remote_port,
            system_name=name or None,
            system_description=description or None,
        )

    yield from output.build_each(columns.cut_rows(table.rows), build)


@parser("show lldp neighbor")
def parse_lldp_neighbors(output: Output) -> Iterator[LldpNeighbor]:
    """`show lldp neighbor` -> one LldpNeighbor per block. A port can have several."""
    neighbor: dict[str, Any] | None = None
    for line in output.lines:
        start = _NEIGHBOR_START.fullmatch(line.strip())
        if start:
            if neighbor:
                yield LldpNeighbor(**neighbor)
            neighbor = {
                "local_port": start["port"],
                "index": int(start["index"]),
                "age": start["age"],
            }
        elif neighbor is not None and not _BLOCK_END.fullmatch(line):
            found = _NEIGHBOR_FIELD.fullmatch(line)
            if found is None:
                output.skip(line, "line does not have the expected format")
            elif not _store_field(neighbor, found["key"], found["value"].strip()):
                output.skip(line, f"unknown LLDP field {found['key']!r}")
    if neighbor:
        yield LldpNeighbor(**neighbor)


def _store_field(neighbor: dict[str, Any], key: str, value: str) -> bool:
    """Store a 'Key: value' line in the neighbour. False if the key is unknown."""
    name = key.lower()
    if name in _IDENTIFIERS:
        prefix = _IDENTIFIERS[name]
        split = _SUBTYPE_AND_VALUE.fullmatch(value)
        neighbor[f"{prefix}_subtype"] = split["subtype"] if split else None
        neighbor[prefix] = split["value"] if split else value
    elif name in _FIELD_NAMES:
        neighbor[_FIELD_NAMES[name]] = value or None
    else:
        return False
    return True
