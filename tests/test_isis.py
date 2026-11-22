from __future__ import annotations

from datetime import timedelta

from fabric_weft import parse_isis_adjacencies, parse_isis_settings, parse_spbm_instances

HEADER = """\
INTERFACE         L STATE        UPTIME PRI HOLDTIME   SYSID             HOST-NAME                 STATUS   AREA       AREA-NAME
----------------------------------------------------------------------------------------------------------------------------------
"""


def test_adjacency_uptime_with_days_and_area_name() -> None:
    row = "Port1/1           1 UP   2 day(s), 01:02:03 127  23 0c91.dc31.0084    fe-02   ACTIVE   HOME       lab area\n"
    (adjacency,) = parse_isis_adjacencies(HEADER + row, strict=True)
    assert adjacency.port == "1/1"
    assert adjacency.uptime == timedelta(days=2, hours=1, minutes=2, seconds=3)
    assert adjacency.area_name == "lab area"


def test_adjacency_without_host_name_is_reported_not_guessed() -> None:
    row = "Port1/1           1 UP         00:04:03 127         23 0c91.dc31.0084    ACTIVE   HOME\n"
    result = parse_isis_adjacencies(HEADER + row)
    assert not result.records
    assert result.skipped[0].reason == "line does not have the expected format"


def test_non_port_interface_keeps_its_name() -> None:
    row = "Mlt2              1 UP         00:04:03 127         23 0c91.dc31.0084    fe-02   ACTIVE   HOME\n"
    (adjacency,) = parse_isis_adjacencies(HEADER + row, strict=True)
    assert (adjacency.interface, adjacency.port) == ("Mlt2", None)


def test_isis_settings_missing_field_is_reported_not_guessed() -> None:
    text = "AdminState : enabled\nRouterType : Level 1\n"
    result = parse_isis_settings(text)
    assert not result.records
    assert result.skipped[0].reason.startswith("no field ")


SPBM = """\
SPBM       B-VID      PRIMARY    NICK     LSDB     IP       IPV6     MULTICAST  SPB-PIM-GW         STP-MULTI  ORIGIN
INSTANCE              VLAN       NAME     TRAP                                                     HOMING
----------------------------------------------------------------------------------------------------------------------------------
1          10,20-22   10                  disable  enable   disable  disable    disable            disable    config
"""


def test_spbm_instance_expands_bvlan_lists_and_empty_nickname() -> None:
    (instance,) = parse_spbm_instances(SPBM, strict=True)
    assert instance.bvlans == (10, 20, 21, 22)
    assert (instance.nickname, instance.ip_shortcuts) == (None, True)
    assert instance.smlt_split_beb is None  # SMLT table not printed
