"""Fabric Connect service instances: `show i-sid` and `show isis spbm i-sid all`."""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass

from fabric_weft.output import Output, fullmatch
from fabric_weft.registry import parser
from fabric_weft.tables import Columns
from fabric_weft.values import nickname, optional, optional_int, ports, system_id


@dataclass(frozen=True, slots=True)
class PortBinding:
    port: str
    customer_vid: int | None  # None: untagged traffic ('u:' in the output)


@dataclass(frozen=True, slots=True)
class MltBinding:
    mlt_id: int
    customer_vid: int | None  # None: untagged traffic


@dataclass(frozen=True, slots=True)
class Isid:
    isid: int
    isid_type: str  # 'ELAN', 'CVLAN', ... kept as printed
    port_bindings: tuple[PortBinding, ...]
    mlt_bindings: tuple[MltBinding, ...]
    # As printed: 'CONFIG' (8.x), a row of flag slots such as 'C  ---  -  ---  -  -  --' (9.x)
    origin: str
    name: str | None
    vlan_id: int | None = None  # 9.x: the platform VLAN of a CVLAN I-SID; None: 'N/A' or 8.x
    # 9.x, CVLAN I-SID: the ports and MLTs of its VLAN, printed without 'c:'/'u:'. They
    # carry the VLAN, not a customer VID, so they are not bindings.
    vlan_member_ports: tuple[str, ...] = ()
    vlan_member_mlts: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class SpbmIsid:
    """One I-SID advertised in the SPB fabric, by this switch or a remote one."""

    isid: int
    nickname: str | None  # None: the advertising node has no SPBM nickname
    bvlan: int
    system_id: str
    origin: str  # 'config' (this switch) or 'discover' (learned from the fabric)
    host_name: str | None
    # Printed by 9.x only.
    isid_name: str | None = None
    area: str | None = None  # 'HOME' / 'REMOTE' (multi-area SPB)
    area_name: str | None = None


_ISID_ROW = re.compile(
    r"(?P<isid>\d+)\s+(?P<isid_type>\S+)\s+(?P<ports>\S+)\s+(?P<mlts>\S+)\s+(?P<origin>\S+)"
    r"(?:\s+(?P<name>.+))?"
)
_BINDING = re.compile(r"(?:c(?P<vid>\d+)|u):(?P<member>.+)")


def _split_members(
    cell: str, *, vlan_id: int | None
) -> tuple[list[tuple[int | None, str]], list[str]]:
    """Split a PORT or MLT INTERFACES cell into bindings and plain VLAN members.

    'c100:1/10,u:1/11' -> bindings [(100, '1/10'), (None, '1/11')]
    'c100:1/8 u:1/7'   -> the same: 9.4 prints each further binding on its own line,
                          and the wrapped lines are joined with a space (lab3 fe-01)
    'c100:1/8,1/9'     -> bindings [(100, '1/8'), (100, '1/9')]: one binding over
                          several ports prints the prefix once and the rest of the
                          port list after it, and a wrap inside that list rejoins
                          as one comma-separated cell
    '1/4,1/6-1/8'      -> members ['1/4', '1/6-1/8'], only for a CVLAN I-SID (vlan_id set)
    '-', '- -'         -> nothing

    Within one whitespace-separated group the prefix carries across the commas; a
    new group starts a new prefix. Reading each comma-separated chunk as its own
    binding instead raised on the second port and lost the ENTIRE I-SID - service,
    name and every other endpoint - over ports it could have placed.
    """
    bindings: list[tuple[int | None, str]] = []
    members: list[str] = []
    for group in cell.split():
        prefix: tuple[int | None, ...] = ()
        for chunk in group.split(","):
            if optional(chunk) is None:
                continue
            found = _BINDING.fullmatch(chunk)
            if found:
                prefix = ((int(found["vid"]) if found["vid"] else None),)
                bindings.append((prefix[0], found["member"]))
            elif prefix:
                bindings.append((prefix[0], chunk))
            elif vlan_id is not None:
                members.append(chunk)
            else:
                raise ValueError(f"not an I-SID binding: {chunk!r}")
    return bindings, members


@parser("show i-sid")
def parse_isids(output: Output) -> Iterator[Isid]:
    """`show i-sid` -> one Isid per service, with its port and MLT bindings."""
    table = output.table("ISID", "TYPE", "ORIGIN")
    if table is None:
        return
    if table.has_columns("VLANID"):
        yield from _parse_isids_9x(output, table.header, table.rows)
        return

    def build(row: str) -> Isid:
        cells = fullmatch(_ISID_ROW, row)
        return _isid(
            cells["isid"],
            cells["isid_type"],
            cells["ports"],
            cells["mlts"],
            cells["origin"],
            name=cells["name"],
        )

    yield from output.build_each(table.rows, build)


def _parse_isids_9x(
    output: Output, header: tuple[str, ...], rows: tuple[str, ...]
) -> Iterator[Isid]:
    """9.x adds VLANID and prints ORIGIN as flag slots with spaces, so cut by column."""
    columns = Columns.locate(
        header, "ISID", "TYPE", "VLANID", "INTERFACES", "INTERFACES", "ORIGIN", "NAME"
    )

    def build(cells: list[str]) -> Isid:
        isid, isid_type, vlan_id, port_cell, mlt_cell, origin, name = cells
        if not isid.isdigit() or not origin:
            raise ValueError("line does not have the expected format")
        return _isid(
            isid,
            isid_type,
            port_cell,
            mlt_cell,
            origin,
            name=optional(name),
            vlan_id=optional_int(vlan_id),
        )

    yield from output.build_each(columns.cut_rows(rows), build)


def _isid(
    isid: str,
    isid_type: str,
    port_cell: str,
    mlt_cell: str,
    origin: str,
    *,
    name: str | None,
    vlan_id: int | None = None,
) -> Isid:
    port_bindings, member_ports = _split_members(port_cell, vlan_id=vlan_id)
    mlt_bindings, member_mlts = _split_members(mlt_cell, vlan_id=vlan_id)
    return Isid(
        isid=int(isid),
        isid_type=isid_type,
        port_bindings=tuple(
            PortBinding(single, vid) for vid, member in port_bindings for single in ports(member)
        ),
        mlt_bindings=tuple(MltBinding(int(mlt), vid) for vid, mlt in mlt_bindings),
        origin=origin,
        name=name,
        vlan_id=vlan_id,
        vlan_member_ports=ports(",".join(member_ports)),
        vlan_member_mlts=tuple(int(mlt) for mlt in member_mlts),
    )


@parser(
    "show isis spbm i-sid all",
    "show isis spbm i-sid config",
    "show isis spbm i-sid discover",
)
def parse_spbm_isids(output: Output) -> Iterator[SpbmIsid]:
    """`show isis spbm i-sid all|config|discover` -> one SpbmIsid per I-SID and node.

    Cut by column: SOURCE NAME (the nickname) can be empty, and the 9.x columns
    ISID NAME and AREA NAME can be empty or contain spaces.
    """
    table = output.table("ISID", "SYSID", "TYPE")
    if table is None:
        return
    labels = ["ISID", "SOURCE", "VLAN", "SYSID", "TYPE", "HOST_NAME"]
    if table.has_columns("AREA"):  # 9.x
        labels += ["ISID", "AREA", "AREA"]
    columns = Columns.locate(table.header, *labels)

    def build(cells: list[str]) -> SpbmIsid:
        isid, source, bvlan, system, origin, host, *names = cells
        isid_name, area, area_name = names or ("", "", "")  # 8.x: columns not printed
        if not isid.isdigit() or not origin:
            raise ValueError("line does not have the expected format")
        return SpbmIsid(
            isid=int(isid),
            nickname=nickname(source),
            bvlan=int(bvlan),
            system_id=system_id(system),
            origin=origin,
            host_name=optional(host),
            isid_name=optional(isid_name),
            area=optional(area),
            area_name=optional(area_name),
        )

    yield from output.build_each(map(columns.cut, table.rows), build)
