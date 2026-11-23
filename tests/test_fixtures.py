"""Every captured output under tests/fixtures is parsed and compared with its golden file.

Layout: tests/fixtures/<source>/<command>.txt, where the file name is the command
with spaces replaced by '_' (hyphens stay): 'show_vlan_i-sid.txt' -> 'show vlan i-sid'.
The expected records live next to it in '<command>.json'. A new capture needs no
new test code: add the .txt, run `pytest --update-golden`, review the .json, commit.
Captures of commands without a parser yet show up as skipped tests: the backlog.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from fabric_weft import UnknownCommandError, find_parser, parse_lacp_aggregators

FIXTURES = Path(__file__).parent / "fixtures"
CAPTURES = sorted(FIXTURES.glob("*/*.txt"))
# Real captures from a switch that has none of the thing (no MLT, no vIST). They pin
# that an empty table parses to no records without a skipped line. Every other
# fixture must produce records, so a parser that silently drops everything fails.
_NO_MLT_NO_VIST = ("show_mlt", "show_smlt_mlt", "show_virtual-ist")
_NO_SMLT_NO_VIST = ("show_smlt_mlt", "show_virtual-ist")
_NO_L3 = ("show_ip_arp", "show_ip_interface", "show_ip_route")
EMPTY_ON_PURPOSE = {
    f"{lab}/{command}"
    for lab, commands in (
        # a lone switch a few minutes after boot: no neighbour either
        (
            "fe-9.4-gns3-sw1",
            (*_NO_MLT_NO_VIST, *_NO_L3, "show_isis_adjacencies", "show_isis_interface"),
        ),
        ("fe-9.4-gns3-fe-01", (*_NO_MLT_NO_VIST, *_NO_L3)),
        ("fe-9.4-gns3-fe-02", (*_NO_MLT_NO_VIST, *_NO_L3)),
        ("fe-9.4-gns3-fe-03", (*_NO_MLT_NO_VIST, *_NO_L3)),
        ("fe-9.4-gns3-fe-04", (*_NO_MLT_NO_VIST, *_NO_L3)),
        # lab2-lab5: MLT 10 only between fe-01 and fe-02, L3 only on fe-03 and fe-04
        ("fe-9.4-gns3-lab2-fe-01", (*_NO_SMLT_NO_VIST, *_NO_L3)),
        ("fe-9.4-gns3-lab2-fe-02", (*_NO_SMLT_NO_VIST, *_NO_L3)),
        ("fe-9.4-gns3-lab2-fe-03", _NO_MLT_NO_VIST),
        ("fe-9.4-gns3-lab2-fe-04", _NO_MLT_NO_VIST),
        ("fe-9.4-gns3-lab3-fe-01", (*_NO_SMLT_NO_VIST, *_NO_L3)),
        ("fe-9.4-gns3-lab3-fe-02", (*_NO_SMLT_NO_VIST, *_NO_L3)),
        ("fe-9.4-gns3-lab4-fe-01", (*_NO_SMLT_NO_VIST, *_NO_L3)),
        ("fe-9.4-gns3-lab4-fe-02", (*_NO_SMLT_NO_VIST, *_NO_L3)),
        ("fe-9.4-gns3-lab5-fe-01", (*_NO_SMLT_NO_VIST, *_NO_L3)),
        ("fe-9.4-gns3-lab5-fe-02", (*_NO_SMLT_NO_VIST, *_NO_L3)),
        # lab6 (tools/lab/): the vIST lines did not take, fe-03's SMLT links were not cabled,
        # so its VLAN 103 (VRF blue) is down; fe-04 has no MLT
        ("fe-9.4-gns3-lab6-fe-01", ("show_virtual-ist",)),
        ("fe-9.4-gns3-lab6-fe-02", ("show_virtual-ist",)),
        ("fe-9.4-gns3-lab6-fe-03", (*_NO_SMLT_NO_VIST, "show_ip_arp_vrf_blue")),
        ("fe-9.4-gns3-lab6-fe-04", _NO_MLT_NO_VIST),
    )
    for command in commands
}


def command_of(capture: Path) -> str:
    return capture.stem.replace("_", " ")


def as_json(records: list[dict[str, Any]]) -> str:
    return json.dumps(records, indent=2, default=str) + "\n"


@pytest.mark.parametrize("capture", CAPTURES, ids=lambda path: f"{path.parent.name}/{path.stem}")
def test_capture_matches_golden(capture: Path, request: pytest.FixtureRequest) -> None:
    command = command_of(capture)
    try:
        run = find_parser(command)
    except UnknownCommandError:
        pytest.skip(f"captured, parser still to write: {command}")
    # strict: a capture in the repository must parse without a single skipped line
    result = run(capture.read_text(), strict=True, command=command)
    actual = as_json(result.as_dicts())
    golden = capture.with_suffix(".json")
    if request.config.getoption("--update-golden"):
        golden.write_text(actual)
    assert golden.exists(), f"no golden file, run: pytest --update-golden ({golden.name})"
    assert actual == golden.read_text()
    if f"{capture.parent.name}/{capture.stem}" in EMPTY_ON_PURPOSE:
        assert not result.records, "listed in EMPTY_ON_PURPOSE but has records"
    else:
        assert result.records, "a fixture should contain at least one record"


# Second record types read from the same output, called directly (decision 0017). Their
# golden file is '<command>.<name>.json' next to the capture.
ALSO_PARSED = {"show lacp interface": ("aggregators", parse_lacp_aggregators)}
ALSO_CAPTURES = [capture for capture in CAPTURES if command_of(capture) in ALSO_PARSED]


@pytest.mark.parametrize(
    "capture", ALSO_CAPTURES, ids=lambda path: f"{path.parent.name}/{path.stem}"
)
def test_second_record_type_matches_golden(capture: Path, request: pytest.FixtureRequest) -> None:
    command = command_of(capture)
    name, run = ALSO_PARSED[command]
    result = run(capture.read_text(), strict=True, command=command)
    actual = as_json(result.as_dicts())
    golden = capture.with_suffix(f".{name}.json")
    if request.config.getoption("--update-golden"):
        golden.write_text(actual)
    assert golden.exists(), f"no golden file, run: pytest --update-golden ({golden.name})"
    assert actual == golden.read_text()
    # every MLT with LACP has an aggregator: a dropped one fails here, not silently
    mlts = capture.parent / "show_mlt.json"
    if mlts.exists():
        with_lacp = [mlt["mlt_id"] for mlt in json.loads(mlts.read_text()) if mlt["lacp_enabled"]]
        assert [record["mlt_id"] for record in json.loads(actual)] == with_lacp
