from __future__ import annotations

from datetime import timedelta

import pytest

from fabric_weft import parse_sys_info, values
from fabric_weft.fields import split_sections

SYS_INFO = """\
General Info :

        SysDescr     : 5520-24T-FabricEngine (9.4.0.0)
        SysName      : sw1
        SysUpTime    : 3 day(s), 04:05:06
        SysContact   : http://example.com/contact/
        SysLocation  :

Chassis Info:

        Chassis            : 5520-24T-FabricEngine
        ModelName          : 5520-24T-FabricEngine
        Serial#            : SIM1050-0000
        BaseMacAddr        : 0c:19:10:50:00:00
        NumSlots           : 2
        NumPorts           : 27

Card Info :

        Slot#  CardType   Oper
           1   5520-24T   up
Last Statistic Reset: 0 day(s), 00:00:00
"""


def test_split_sections_reads_keys_values_and_ignores_tables() -> None:
    sections = split_sections(SYS_INFO.splitlines())
    assert sections["General Info"]["SysContact"] == "http://example.com/contact/"
    assert sections["General Info"]["SysLocation"] == ""
    assert sections["Chassis Info"]["Serial#"] == "SIM1050-0000"
    # a field line that is not indented stays in the section above
    assert sections["Card Info"] == {"Last Statistic Reset": "0 day(s), 00:00:00"}


def test_sys_info_reads_release_and_uptime() -> None:
    (info,) = parse_sys_info(SYS_INFO, strict=True)
    assert info.sys_name == "sw1"
    assert info.release == "9.4.0.0"
    assert info.uptime == timedelta(days=3, hours=4, minutes=5, seconds=6)
    assert info.location is None
    assert info.management_mac is None  # not printed here


def test_sys_info_missing_field_is_skipped_not_guessed() -> None:
    result = parse_sys_info(SYS_INFO.replace("NumPorts", "PortCount"))
    assert not result.records
    assert result.skipped[0].reason == "no field 'NumPorts'"


@pytest.mark.parametrize(
    ("cell", "expected"),
    [
        ("0 day(s), 00:09:01", timedelta(minutes=9, seconds=1)),
        ("12 day(s), 23:59:59", timedelta(days=12, hours=23, minutes=59, seconds=59)),
        ("00:04:03", timedelta(minutes=4, seconds=3)),  # IS-IS adjacency uptime
    ],
)
def test_duration(cell: str, expected: timedelta) -> None:
    assert values.duration(cell) == expected


def test_duration_rejects_other_text() -> None:
    with pytest.raises(ValueError, match="duration"):
        values.duration("9 minutes")
