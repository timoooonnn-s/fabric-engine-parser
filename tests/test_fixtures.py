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
    assert result.records, "a fixture should contain at least one record"
