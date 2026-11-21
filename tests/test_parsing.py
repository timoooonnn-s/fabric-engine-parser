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
    parse_port_names,
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
    ],
)
def test_find_parser_accepts_abbreviations_and_arguments(typed: str, expected: object) -> None:
    assert find_parser(typed) is expected


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
