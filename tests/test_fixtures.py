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

import pytest

from fabric_weft import UnknownCommandError, find_parser

FIXTURES = Path(__file__).parent / "fixtures"
CAPTURES = sorted(FIXTURES.glob("*/*.txt"))
# Real captures from a switch that has none of the thing (no MLT, no vIST). They pin
# that an empty table parses to no records without a skipped line. Every other
# fixture must produce records, so a parser that silently drops everything fails.
_NO_MLT_NO_VIST = ("show_mlt", "show_virtual-ist")
EMPTY_ON_PURPOSE = {
    f"{lab}/{command}"
    for lab, commands in (
        # a lone switch a few minutes after boot: no neighbour either
        ("fe-9.4-gns3-sw1", (*_NO_MLT_NO_VIST, "show_isis_adjacencies", "show_isis_interface")),
        ("fe-9.4-gns3-fe-01", _NO_MLT_NO_VIST),
        ("fe-9.4-gns3-fe-02", _NO_MLT_NO_VIST),
        ("fe-9.4-gns3-fe-03", _NO_MLT_NO_VIST),
        ("fe-9.4-gns3-fe-04", _NO_MLT_NO_VIST),
    )
    for command in commands
}


def command_of(capture: Path) -> str:
    return capture.stem.replace("_", " ")


def as_json(records: list[dict]) -> str:
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
