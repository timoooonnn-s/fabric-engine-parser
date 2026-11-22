"""Behaviour shared by all parsers: command matching, cleanup, errors, lenient vs strict."""

from __future__ import annotations

from pathlib import Path

import pytest

from fabric_weft import (
    DeviceError,
    ParseError,
    UnknownCommandError,
    find_parser,
    parse,
    parse_mlts,
    parse_port_interfaces,
    parse_port_isids,
    parse_port_names,
    parse_port_vlans,
    parse_vlans,
    supported_commands,
)

FIXTURES = Path(__file__).parent / "fixtures"

VLAN_BASIC = """\
VLAN                                MSTP
ID    NAME             TYPE         INST_ID PROTOCOLID   SUBNETADDR      SUBNETMASK      VRFID ORIGIN
------------------------------------------------------------------------------------------------------------
1     Default          byPort       0       none         N/A             N/A             0     CONFIG
2     Two words name   byPort       0       none         N/A             N/A             0     CONFIG
this line is broken
"""


@pytest.mark.parametrize(
    ("typed", "expected"),
    [
        ("show mlt", parse_mlts),
        ("sh mlt", parse_mlts),
        ("SHOW VLAN BASIC", parse_vlans),
        ("sh int gig name 1/1-1/4", parse_port_names),
        ("show interfaces gigabitethernet 1/1,1/3-1/4", parse_port_interfaces),
        ("show interfaces gigabitethernet vlan 1/1-1/4", parse_port_vlans),
        ("sh int gig i-sid 1/3", parse_port_isids),
    ],
)
def test_find_parser_accepts_abbreviations_and_arguments(typed: str, expected: object) -> None:
    assert find_parser(typed) is expected


@pytest.mark.parametrize(
    "typed",
    [
        "show interfaces gigabitethernet statistics 1/1",
    ],
)
def test_subcommand_is_not_taken_for_a_port_argument(typed: str) -> None:
    # the bare command accepts port lists only, so 'statistics' is a command still to write
    with pytest.raises(UnknownCommandError):
        find_parser(typed)


def test_find_parser_prefers_the_longest_command() -> None:
    assert find_parser("show interfaces gigabitethernet name") is parse_port_names


@pytest.mark.parametrize("typed", ["show nothing", "show vlan", ""])
def test_find_parser_rejects_unknown_commands(typed: str) -> None:
    with pytest.raises(UnknownCommandError):
        find_parser(typed)


def test_supported_commands_lists_every_spelling() -> None:
    assert "show mlt" in supported_commands()
    assert "show interfaces gigabitethernet interface" in supported_commands()


def test_lenient_parse_keeps_good_rows_and_reports_the_bad_one() -> None:
    result = parse("show vlan basic", VLAN_BASIC)
    assert [vlan.name for vlan in result] == ["Default", "Two words name"]
    assert not result.complete
    assert [skipped.line for skipped in result.skipped] == ["this line is broken"]


def test_strict_parse_raises_on_the_bad_row() -> None:
    with pytest.raises(ParseError, match="this line is broken"):
        parse("show vlan basic", VLAN_BASIC, strict=True)


def test_missing_table_is_reported() -> None:
    result = parse("show mlt", "nothing useful here")
    assert result.records == ()
    assert "no table" in result.skipped[0].reason


@pytest.mark.parametrize(
    "text",
    [
        "                     ^\n% Invalid input detected at '^' marker.\n",
        "\r\n% Permission denied\r\n",
    ],
)
def test_device_errors_raise(text: str) -> None:
    with pytest.raises(DeviceError) as error:
        parse("show lldp neighbor summary", text)
    assert error.value.command == "show lldp neighbor summary"


def test_netmiko_noise_is_ignored() -> None:
    """CRLF line ends, ANSI colour codes and tabs do not change the result."""
    clean = (FIXTURES / "prod-vsp7254-voss8.10" / "show_vlan_basic.txt").read_text()
    noisy = "\x1b[0m" + clean.replace("\n", "\r\n").replace("1     Default", "1\tDefault")
    assert parse("show vlan basic", noisy, strict=True) == parse("show vlan basic", clean)


def test_result_iterates_and_converts_to_dicts() -> None:
    result = parse("show vlan basic", VLAN_BASIC)
    assert len(result) == 2
    assert result.as_dicts()[0]["vlan_id"] == 1


LLDP_9X = """\
Port: 1/1       Index    : 1
                SysName  : fe-02
           IPv6 Address  : 0:0:0:0:0:0:0:0
Port: 1/2       Index    : 2
                SysName  : fe-03
------------------------------------------------------------------------------------------
Total Neighbors : 3
"""


def test_lldp_neighbor_count_is_checked_against_the_total() -> None:
    result = parse("show lldp neighbor", LLDP_9X)
    assert [neighbor.system_name for neighbor in result] == ["fe-02", "fe-03"]
    assert result.records[0].age is None  # 9.x prints no Time
    assert result.skipped[0].reason == "2 neighbour blocks read, the switch counts 3"


MAC_TABLE = """\
VLAN            MAC                                   SMLT
ID   STATUS     ADDRESS            INTERFACE          REMOTE   TUNNEL
-------------------------------------------------------------------------------------------------------
4051 self       0c:91:dc:31:00:84  Port-1/1           false    -
4051 self       09:00:2b:00:00:05  Port-cpp           false    -
4051 self       09:00:2b:00:00:05  Port-cpp           maybe    -
"""


def test_mac_table_maps_front_ports_and_reports_unknown_words() -> None:
    result = parse("sh vlan mac", MAC_TABLE)
    first, cpu = result.records
    assert (first.port, first.mac, first.tunnel) == ("1/1", "0c:91:dc:31:00:84", None)
    assert (cpu.interface, cpu.port) == ("Port-cpp", None)
    assert result.skipped[0].reason == "not a true/false value: 'maybe'"


def test_missing_column_label_is_reported_not_raised() -> None:
    text = "PORT     TAGGING DEFVLAN\nNUM\n----------------------------------------\n1/1      enable  disable\n"
    result = parse("show interfaces gigabitethernet vlan", text)
    assert not result.records
    assert result.skipped[0].reason.startswith("column 'TAGFRAM' not found")
    with pytest.raises(ParseError):
        parse_port_vlans(text, strict=True)


PORT_VLANS = """\
PORT             DISCARD DISCARD   DEFAULT VLAN         PORT     UNTAG    DYNAMIC UNTAG  FA/
NUM      TAGGING TAGFRAM UNTAGFRAM VLANID  IDS          TYPE     DEFVLAN  VLANS   VLANS  Flex UNI
-----------------------------------------------------------------------------------------------------------
1/1      enable  false   true      1       1,10,20,     normal   enable   P       1      disable
                                           30,40
1/2      disable false   false     0       0            normal   disable  P              enable
"""


def test_port_vlans_join_wrapped_lists_and_read_vlan_0_as_none() -> None:
    trunk, unused = parse_port_vlans(PORT_VLANS, strict=True)
    assert trunk.vlan_ids == (1, 10, 20, 30, 40)
    assert (trunk.default_vlan_id, trunk.untagged_vlan_ids) == (1, (1,))
    assert (unused.default_vlan_id, unused.vlan_ids, unused.flex_uni) == (None, (), True)


VRFS = """\
VRF                  VRF  VLAN   ARP                                NBRv6                       UNICAST  SD-WAN LOCAL  VRF
NAME                 ID   COUNT  COUNT  RIP    OSPF   BGP    PIM    COUNT  RIPng  OSPFv3 PIM6   ACTIVE   BREAKOUT      ORIGIN    SEGMENTED
--------------------------------------------------------------------------------------------------------------------------------------------
GlobalRouter         0    5      0      TRUE   TRUE   TRUE   TRUE   0      TRUE   TRUE   TRUE   TRUE     FALSE         DYNAMIC   FALSE
CUSTOMER-VERY-LONG-NAME 3 12     4      FALSE  TRUE   FALSE  FALSE  0      FALSE  FALSE  FALSE  TRUE     FALSE         CONFIG    TRUE
"""


def test_vrf_name_wider_than_its_column_does_not_shift_values() -> None:
    _, customer = parse("sh ip vrf", VRFS, strict=True)
    assert (customer.name, customer.vrf_id, customer.vlan_count) == (
        "CUSTOMER-VERY-LONG-NAME",
        3,
        12,
    )
    assert (customer.ospf, customer.origin, customer.segmented) == (True, "CONFIG", True)


def _lacp(partner_oper_rows: str) -> str:
    participant_header = (
        "INDEX    SYS   SYS               KEY   PORT    PORT  STATE\n         PRIO  ID                              PRIO\n"
        + "-" * 60
        + "\n"
    )

    def titled(title: str, header: str, rows: str) -> str:
        return f"{'=' * 60}\n   {title}\n{'=' * 60}\n{header}{rows}\n"

    return (
        titled(
            "Actor Admin",
            participant_header,
            "1/1      32768 0c:04:d2:70:00:00 1216  0xc0    32768 act long indi\n",
        )
        + titled(
            "Actor Oper",
            "INDEX KEY   SELECTED ATTACHED AGGR  STATE\n" + "-" * 60 + "\n",
            "1/1      1216  0        0        false act long indi\n",
        )
        + titled(
            "Partner Admin",
            participant_header,
            "1/1      0     00:00:00:00:00:00 0     0x0     0     pas long indi\n",
        )
        + titled("Partner Operational", participant_header, partner_oper_rows)
        + titled(
            "LACP Extension",
            "INDEX    ADMIN   OPER    FAST   SLOW   AGGRWAIT TIMEOUT\n" + "-" * 60 + "\n",
            "1/1      true    true    1000   30000  2000     3       1000   30000  2000     3\n",
        )
    )


def test_lacp_tables_with_the_same_header_are_told_apart_by_title() -> None:
    partner = "1/1      32768 0c:91:dc:31:00:00 7     0xc1    32768 act long aggr sync\n"
    (port,) = parse("show lacp interface", _lacp(partner), strict=True)
    assert port.partner_admin.system_id == "00:00:00:00:00:00"
    assert port.partner_oper.system_id == "0c:91:dc:31:00:00"
    assert port.partner_oper.state == ("act", "long", "aggr", "sync")
    assert (port.actor_admin.port_number, port.lacp_enabled_oper) == (192, True)


def test_lacp_port_missing_from_one_table_is_reported() -> None:
    result = parse("show lacp interface", _lacp(""))
    assert not result.records
    assert result.skipped[0].reason == "port 1/1 is missing from one of the LACP tables"
