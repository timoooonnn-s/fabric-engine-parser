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
    parse_lacp_aggregators,
    parse_lacp_ports,
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
    text = (
        "NUM      NAME     DESCRIPTION  DUPLEX   SPEED\n"
        + "-" * 50
        + "\n1/1               1000BaseTX   full     1000\n"
    )
    result = parse("show interfaces gigabitethernet name", text)
    assert not result.records
    assert result.skipped[0].reason.startswith("column 'STATUS' not found")
    with pytest.raises(ParseError):
        parse_port_names(text, strict=True)


PORT_VLANS = """\
PORT             DISCARD DISCARD   DEFAULT VLAN         PORT     UNTAG    DYNAMIC UNTAG  FA/
NUM      TAGGING TAGFRAM UNTAGFRAM VLANID  IDS          TYPE     DEFVLAN  VLANS   VLANS  Flex UNI
-----------------------------------------------------------------------------------------------------------
1/1      enable  false   true      1       1,10,20,30,40,50,60,70 normal   enable   P       1      disable
1/2      disable false   false     0       0            normal   disable  P              enable
"""


def test_port_vlans_read_an_overflowing_list_and_vlan_0_as_none() -> None:
    # 9.4 lets a long VLAN IDS list run into the next columns instead of wrapping it
    trunk, unused = parse_port_vlans(PORT_VLANS, strict=True)
    assert trunk.vlan_ids == (1, 10, 20, 30, 40, 50, 60, 70)
    assert (trunk.port_type, trunk.untag_default_vlan) == ("normal", True)
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


UNKNOWN_VRF = """\
************************************************************************************
\t\tCommand Execution Time: Sun Nov 22 12:53:48 2026 UTC
************************************************************************************
Error: The VRF Name entered does not correspond to any VRF
"""


def test_error_line_after_the_banner_is_a_device_error() -> None:
    # lab2 fe-01, `show ip route vrf blue` on a switch without VRF blue
    with pytest.raises(DeviceError, match="does not correspond to any VRF"):
        parse("show ip route vrf blue", UNKNOWN_VRF)


ISIDS_9X = """\
ISID      ISID              PORT               MLT                ORIGIN                      ISID
ID        TYPE     VLANID   INTERFACES         INTERFACES                                     NAME
----------------------------------------------------------------------------------------------------------------------------------
30100     ELAN     N/A      c100:1/8           -                  C  ---  -  ---  -  -  --    ISID-30100
                            u:1/7              -
16777001  ELAN     N/A      -                  -                  C  ---  -  ---  -  -  --    FAN-ISID
"""


def test_isid_binding_on_its_own_line_joins_the_row_above() -> None:
    # lab3 fe-01: 9.4 prints each further binding of an I-SID on a line of its own
    elan, fan = parse("show i-sid", ISIDS_9X, strict=True)
    assert [(b.port, b.customer_vid) for b in elan.port_bindings] == [("1/8", 100), ("1/7", None)]
    assert (elan.mlt_bindings, fan.port_bindings) == ((), ())


def test_unregistered_second_parser_does_not_take_over_the_command() -> None:
    assert find_parser("show lacp interface") is parse_lacp_ports
    assert parse_lacp_aggregators.commands == ("show lacp interface",)


def test_smlt_mlt_rows() -> None:
    text = "MLT   ADMIN    CURRENT\nID    TYPE     TYPE\n" + "-" * 60 + "\n20    smlt     norm\n"
    (smlt,) = parse("show smlt mlt", text, strict=True)
    assert (smlt.mlt_id, smlt.admin_type, smlt.current_type) == (20, "smlt", "norm")


REFUSED_HALFWAY = """\
====================================================================================================
                                   Vlan I-SID
====================================================================================================
VLAN_ID    I-SID                I-SID NAME
-----------------------------------------------------------------------------------------------------------
1
31         1531100              ISID-1531100

% Invalid input detected at '^' marker.
"""


def test_an_error_after_the_output_is_still_a_device_error() -> None:
    """A command with arguments is answered in parts: the switch prints what it
    has and THEN refuses the rest. Looking for '%' only before the first line of
    real output meant that refusal was neither raised nor skipped - the caller
    got complete=True over a table missing everything after the error, which is
    the one thing this library promises never to do.
    """
    with pytest.raises(DeviceError, match="Invalid input detected"):
        parse("show vlan i-sid", REFUSED_HALFWAY)


def test_error_prefixed_text_inside_output_is_not_an_error() -> None:
    """'Error:' is ordinary English and could open a line of someone's interface
    description, so unlike '%' it stays a leading-line rule."""
    text = (
        'config terminal\ninterface GigabitEthernet 1/1\nname "Error: see ticket 4711"\n'
        "exit\nend\n"
    )
    result = parse("show running-config", text, strict=True)
    assert [command.command for command in result] == [
        "interface GigabitEthernet 1/1",
        'name "Error: see ticket 4711"',
    ]


ISID_PORT_LIST = """\
ISID      ISID              PORT               MLT                ORIGIN                      ISID
ID        TYPE     VLANID   INTERFACES         INTERFACES                                     NAME
----------------------------------------------------------------------------------------------------------------------------------
30100     ELAN     N/A      c100:1/8,1/9,      c100:20,21         C  ---  -  ---  -  -  --    ISID-30100
                            1/10
"""


def test_one_binding_over_several_ports_keeps_its_customer_vid() -> None:
    """`c-vid 100 port 1/8,1/9,1/10` prints the 'c100:' once and the rest of the
    port list behind it, and a wrap inside that list rejoins as one cell. Reading
    every comma-separated chunk as its own binding raised on '1/9' - and because
    that raise is per ROW, it lost the whole I-SID: the service, its name and
    every other endpoint, over ports it could have placed.
    """
    (elan,) = parse("show i-sid", ISID_PORT_LIST, strict=True)
    assert [(b.port, b.customer_vid) for b in elan.port_bindings] == [
        ("1/8", 100),
        ("1/9", 100),
        ("1/10", 100),
    ]
    assert [(b.mlt_id, b.customer_vid) for b in elan.mlt_bindings] == [(20, 100), (21, 100)]
    assert elan.vlan_member_ports == ()
