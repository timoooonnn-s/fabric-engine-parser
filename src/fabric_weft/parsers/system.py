"""The switch itself: `show sys-info` and `show software`."""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import timedelta

from fabric_weft.fields import required
from fabric_weft.output import Output
from fabric_weft.registry import parser
from fabric_weft.values import duration, flag, mac, optional, optional_as, optional_int


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


@dataclass(frozen=True, slots=True)
class SoftwareRelease:
    name: str  # as printed: 'FEGNS3.9.4.0.0.GA'
    labels: tuple[
        str, ...
    ]  # as printed, without parentheses: ('Primary Release', 'Signed Release')


@dataclass(frozen=True, slots=True)
class Software:
    """The releases installed on the switch and the upgrade commit settings."""

    releases: tuple[SoftwareRelease, ...]
    primary_release: str | None  # the name of the release labelled 'Primary Release'
    auto_commit: bool | None  # None: not printed
    commit_timeout_minutes: int | None


_RELEASE_LINE = re.compile(r"(?P<name>\S+)(?P<labels>(?:\s+\([^)]*\))*)")
_LABEL = re.compile(r"\(([^)]*)\)")
_RULE = re.compile(r"\s*-{10,}\s*")
_MINUTES = re.compile(r"(?P<minutes>\d+) minutes?")
_RELEASE = re.compile(r"\((?P<release>\d+(?:\.\d+)+)\)\s*$")


@parser("show sys-info")
def parse_sys_info(output: Output) -> Iterator[SysInfo]:
    """`show sys-info` -> one SysInfo."""
    general = output.section("General Info")
    chassis = output.section("Chassis Info")
    if general is None or chassis is None:
        return

    def build() -> SysInfo:
        description = required(general, "SysDescr")
        release = _RELEASE.search(description)
        return SysInfo(
            sys_name=required(general, "SysName"),
            description=description,
            release=release["release"] if release else None,
            uptime=duration(required(general, "SysUpTime")),
            contact=optional(general.get("SysContact", "")),
            location=optional(general.get("SysLocation", "")),
            model=required(chassis, "ModelName"),
            chassis=required(chassis, "Chassis"),
            serial_number=optional(chassis.get("Serial#", "")),
            hardware_revision=optional(chassis.get("H/W Revision", "")),
            part_number=optional(chassis.get("Part Number", "")),
            base_mac=mac(required(chassis, "BaseMacAddr")),
            management_mac=optional_as(mac, chassis.get("MgmtMacAddr", "")),
            slot_count=int(required(chassis, "NumSlots")),
            port_count=int(required(chassis, "NumPorts")),
            system_mtu=optional_int(chassis.get("System MTU", "")),
        )

    try:
        yield build()
    except ValueError as error:  # a missing field or a value that does not convert
        output.skip("", str(error))


@parser("show software")
def parse_software(output: Output) -> Iterator[Software]:
    """`show software` -> one Software with every release listed.

    The release list is not a table: it is read from the title 'software releases in
    ...' to the next dashed rule. The commit settings below are `Key : value` fields.
    """
    lines = iter(output.lines)
    if not any(line.strip().startswith("software releases in") for line in lines):
        output.skip("", "no 'software releases in' list")
        return
    releases: list[SoftwareRelease] = []
    for line in lines:
        if _RULE.fullmatch(line):
            break
        if not line.strip() or set(line.strip()) == {"="}:
            continue
        found = _RELEASE_LINE.fullmatch(line.strip())
        if found is None:
            output.skip(line, "line does not have the expected format")
            continue
        labels = tuple(label.strip() for label in _LABEL.findall(found["labels"]))
        releases.append(SoftwareRelease(found["name"], labels))

    fields = output.section("", required=False) or {}
    timeout = fields.get("Commit Timeout")
    minutes = _MINUTES.fullmatch(timeout) if timeout else None
    if timeout and minutes is None:
        output.skip(f"Commit Timeout : {timeout}", "not a number of minutes")
    primary = [release.name for release in releases if "Primary Release" in release.labels]
    try:
        auto_commit = flag(fields["Auto Commit"]) if "Auto Commit" in fields else None
    except ValueError as error:
        output.skip(f"Auto Commit : {fields['Auto Commit']}", str(error))
        auto_commit = None
    yield Software(
        releases=tuple(releases),
        primary_release=primary[0] if primary else None,
        auto_commit=auto_commit,
        commit_timeout_minutes=int(minutes["minutes"]) if minutes else None,
    )
