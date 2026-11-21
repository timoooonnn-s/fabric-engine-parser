"""Fabric Connect service instances: `show i-sid` and `show isis spbm i-sid all`."""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass

from fabric_weft.output import Output, fullmatch
from fabric_weft.registry import parser
from fabric_weft.values import optional, ports


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
    origin: str
    name: str | None


@dataclass(frozen=True, slots=True)
class SpbmIsid:
    """One I-SID advertised in the SPB fabric, by this switch or a remote one."""

    isid: int
    nickname: str
    bvlan: int
    system_id: str
    origin: str  # 'config' (this switch) or 'discover' (learned from the fabric)
    host_name: str | None


_ISID_ROW = re.compile(
    r"(?P<isid>\d+)\s+(?P<isid_type>\S+)\s+(?P<ports>\S+)\s+(?P<mlts>\S+)\s+(?P<origin>\S+)"
    r"(?:\s+(?P<name>.+))?"
)
_BINDING = re.compile(r"(?:c(?P<vid>\d+)|u):(?P<member>.+)")
_SPBM_ISID_ROW = re.compile(
    r"(?P<isid>\d+)\s+(?P<nickname>[0-9a-f]\.[0-9a-f]{2}\.[0-9a-f]{2})\s+(?P<bvlan>\d+)\s+"
    r"(?P<system_id>[0-9a-f]{4}\.[0-9a-f]{4}\.[0-9a-f]{4})\s+(?P<origin>\S+)(?:\s+(?P<host>\S+))?"
)


def _bindings(cell: str) -> Iterator[tuple[int | None, str]]:
    """'c100:1/10,c100:1/11' -> (100, '1/10'), (100, '1/11'). '-' -> nothing."""
    if optional(cell) is None:
        return
    for chunk in cell.split(","):
        found = _BINDING.fullmatch(chunk)
        if found is None:
            raise ValueError(f"not an I-SID binding: {chunk!r}")
        yield (int(found["vid"]) if found["vid"] else None), found["member"]


@parser("show i-sid")
def parse_isids(output: Output) -> Iterator[Isid]:
    """`show i-sid` -> one Isid per service, with its port and MLT bindings."""
    table = output.table("ISID", "TYPE", "ORIGIN")
    if table is None:
        return

    def build(row: str) -> Isid:
        cells = fullmatch(_ISID_ROW, row)
        return Isid(
            isid=int(cells["isid"]),
            isid_type=cells["isid_type"],
            port_bindings=tuple(
                PortBinding(single, vid)
                for vid, member in _bindings(cells["ports"])
                for single in ports(member)
            ),
            mlt_bindings=tuple(MltBinding(int(mlt), vid) for vid, mlt in _bindings(cells["mlts"])),
            origin=cells["origin"],
            name=cells["name"],
        )

    yield from output.build_each(table.rows, build)


@parser(
    "show isis spbm i-sid all",
    "show isis spbm i-sid config",
    "show isis spbm i-sid discover",
)
def parse_spbm_isids(output: Output) -> Iterator[SpbmIsid]:
    """`show isis spbm i-sid all|config|discover` -> one SpbmIsid per I-SID and node."""
    table = output.table("ISID", "SYSID", "TYPE")
    if table is None:
        return

    def build(row: str) -> SpbmIsid:
        cells = fullmatch(_SPBM_ISID_ROW, row)
        return SpbmIsid(
            isid=int(cells["isid"]),
            nickname=cells["nickname"],
            bvlan=int(cells["bvlan"]),
            system_id=cells["system_id"],
            origin=cells["origin"],
            host_name=cells["host"],
        )

    yield from output.build_each(table.rows, build)
