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
    assert reasons == ["no 'end' line: the output looks cut off"]
    assert result.records[-1] == ConfigCommand("PORT CONFIGURATION", None, "router ospf")


def test_output_without_config_terminal_is_reported() -> None:
    result = parse_running_config("spbm\n")
    assert not result.records
    assert result.skipped[0].reason == "no 'config terminal' line"
