from __future__ import annotations

from fabric_weft import ConfigCommand, parse_running_config

CONFIG = """\
Preparing to Display Configuration...
#
# box type             : 5520-24T-FabricEngine
#
config terminal

#
# SPBM CONFIGURATION
#

spbm
#boot config sio console baud 115200 1

#
# PORT CONFIGURATION
#

interface GigabitEthernet 1/1
encapsulation dot1q

exit
router ospf
exit
end
"""


def test_commands_keep_their_section_and_context() -> None:
    assert list(parse_running_config(CONFIG, strict=True)) == [
        ConfigCommand("SPBM CONFIGURATION", None, "spbm"),
        ConfigCommand("PORT CONFIGURATION", None, "interface GigabitEthernet 1/1"),
        ConfigCommand("PORT CONFIGURATION", "interface GigabitEthernet 1/1", "encapsulation dot1q"),
        ConfigCommand("PORT CONFIGURATION", None, "router ospf"),  # a context with nothing in it
    ]


def test_exit_without_a_context_is_reported() -> None:
    result = parse_running_config(CONFIG.replace("router ospf\n", ""))
    assert result.skipped[0].reason == "'exit' without a context to close"


def test_cut_off_output_is_reported() -> None:
    result = parse_running_config(CONFIG.removesuffix("exit\nend\n"))
    reasons = [skipped.reason for skipped in result.skipped]
    assert reasons == [
        "no 'end' line: the output looks cut off",
        "context 'router ospf' is not closed by 'exit'",
    ]
    assert result.records[-1] == ConfigCommand("PORT CONFIGURATION", None, "router ospf")


def test_output_without_config_terminal_is_reported() -> None:
    result = parse_running_config("spbm\n")
    assert not result.records
    assert result.skipped[0].reason == "no 'config terminal' line"


def test_context_opener_after_top_level_commands_without_a_blank_line() -> None:
    # lab2 fe-03: `interface Vlan 103` follows `vlan create` lines directly
    text = (
        "config terminal\n"
        'vlan create 30 name "printers" type port-mstprstp 0\n'
        "vlan members 30 1/5 portmember\n"
        "interface Vlan 103\n"
        "vrf blue\n"
        "exit\n"
        'vlan create 4051 name "bvlan-1" type spbm-bvlan\n'
        "end\n"
    )
    assert [(c.context, c.command) for c in parse_running_config(text, strict=True)] == [
        (None, 'vlan create 30 name "printers" type port-mstprstp 0'),
        (None, "vlan members 30 1/5 portmember"),
        (None, "interface Vlan 103"),
        ("interface Vlan 103", "vrf blue"),
        (None, 'vlan create 4051 name "bvlan-1" type spbm-bvlan'),
    ]


def test_exit_of_an_unknown_context_is_reported_not_guessed() -> None:
    text = "config terminal\nlogical-intf isis 1 dest-ip 10.0.0.1\nisis\nexit\nend\n"
    result = parse_running_config(text)
    assert result.skipped[0].reason == "'exit' without a context to close"
