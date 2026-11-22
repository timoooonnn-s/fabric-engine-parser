"""The switch itself: `show sys-info`."""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import timedelta

from fabric_weft.output import Output
from fabric_weft.registry import parser
from fabric_weft.values import duration, mac, optional, optional_int


@dataclass(frozen=True, slots=True)
class SysInfo:
    """Who the switch is and what it runs. Cards, fans, power supplies are not read yet."""

    sys_name: str
    description: str  # SysDescr as printed: '5520-24T-FabricEngine (9.4.0.0)'
    release: str | None  # '9.4.0.0', from the parentheses in SysDescr
    uptime: timedelta
    contact: str | None
    location: str | None
    model: str  # ModelName
    chassis: str
    serial_number: str | None
    hardware_revision: str | None
    part_number: str | None
    base_mac: str
    management_mac: str | None
    slot_count: int
    port_count: int
    system_mtu: int | None


_RELEASE = re.compile(r"\((?P<release>\d+(?:\.\d+)+)\)\s*$")


def _field(section: dict[str, str], key: str) -> str:
    """A field that must be there (it may still be empty)."""
    try:
        return section[key]
    except KeyError:
        raise ValueError(f"no field {key!r}") from None


@parser("show sys-info")
def parse_sys_info(output: Output) -> Iterator[SysInfo]:
    """`show sys-info` -> one SysInfo."""
    general = output.section("General Info")
    chassis = output.section("Chassis Info")
    if general is None or chassis is None:
        return

    def build() -> SysInfo:
        description = _field(general, "SysDescr")
        release = _RELEASE.search(description)
        management_mac = optional(chassis.get("MgmtMacAddr", ""))
        return SysInfo(
            sys_name=_field(general, "SysName"),
            description=description,
            release=release["release"] if release else None,
            uptime=duration(_field(general, "SysUpTime")),
            contact=optional(general.get("SysContact", "")),
            location=optional(general.get("SysLocation", "")),
            model=_field(chassis, "ModelName"),
            chassis=_field(chassis, "Chassis"),
            serial_number=optional(chassis.get("Serial#", "")),
            hardware_revision=optional(chassis.get("H/W Revision", "")),
            part_number=optional(chassis.get("Part Number", "")),
            base_mac=mac(_field(chassis, "BaseMacAddr")),
            management_mac=mac(management_mac) if management_mac else None,
            slot_count=int(_field(chassis, "NumSlots")),
            port_count=int(_field(chassis, "NumPorts")),
            system_mtu=optional_int(chassis.get("System MTU", "")),
        )

    try:
        yield build()
    except ValueError as error:  # a missing field or a value that does not convert
        output.skip("", str(error))
