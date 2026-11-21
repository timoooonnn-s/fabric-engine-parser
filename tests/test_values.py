from __future__ import annotations

from datetime import datetime

import pytest

from fabric_weft import values


@pytest.mark.parametrize(
    ("cell", "expected"),
    [
        ("1/1-1/3,1/10", ("1/1", "1/2", "1/3", "1/10")),
        ("1/17/1-1/17/3", ("1/17/1", "1/17/2", "1/17/3")),
        ("1/17/3-1/18/4", ("1/17/3", "1/17/4", "1/18/1", "1/18/2", "1/18/3", "1/18/4")),
        ("1/1,", ("1/1",)),
        ("NONE", ()),
        ("-", ()),
        ("", ()),
    ],
)
def test_ports_expands_lists(cell: str, expected: tuple[str, ...]) -> None:
    assert values.ports(cell) == expected


@pytest.mark.parametrize("cell", ["1/47-2/2", "1/5-1/1", "1/1-1/2/1", "1/17/3-1/18/2", "49", "1/x"])
def test_ports_rejects_what_it_cannot_expand(cell: str) -> None:
    with pytest.raises(ValueError, match="port"):
        values.ports(cell)


@pytest.mark.parametrize("cell", ["B0:AD:AA:41:B4:01", "b0ad.aa41.b401", "b0-ad-aa-41-b4-01"])
def test_mac_normalises(cell: str) -> None:
    assert values.mac(cell) == "b0:ad:aa:41:b4:01"


def test_mac_rejects_garbage() -> None:
    with pytest.raises(ValueError, match="not a MAC"):
        values.mac("b0:ad:aa")


@pytest.mark.parametrize(("cell", "expected"), [("true", True), ("Enable", True), ("down", False)])
def test_flag(cell: str, expected: bool) -> None:
    assert values.flag(cell) is expected


def test_flag_rejects_unknown_words() -> None:
    with pytest.raises(ValueError, match="true/false"):
        values.flag("testing")


@pytest.mark.parametrize("cell", ["-", "--", "N/A", "none", "  "])
def test_optional_placeholders_become_none(cell: str) -> None:
    assert values.optional(cell) is None


def test_timestamp() -> None:
    assert values.timestamp("03/08/26 08:13:38") == datetime(2026, 3, 8, 8, 13, 38)
    assert values.timestamp("--") is None
