#!/usr/bin/env python3
"""Capture show-command output from a switch as test fixtures.

    pip install -e '.[capture]'
    python tools/capture.py --host 192.0.2.10 --source fe-9.4-gns3 --vrf RED --vrf BLUE

Runs every command in tools/capture_commands.txt over SSH with netmiko (exactly
what the tools using this library do) and writes each output to
tests/fixtures/<source>/<command>.txt. Commands the switch rejects are listed at
the end and not saved. Credentials: --username or $FE_USERNAME, then
$FE_PASSWORD or a prompt.

For the lab only. Output from production switches carries real names and
addresses and must be sanitised before it goes into this public repository.
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

from netmiko import ConnectHandler

ROOT = Path(__file__).resolve().parent.parent
COMMAND_FILE = Path(__file__).with_name("capture_commands.txt")
FIXTURES = ROOT / "tests" / "fixtures"


def read_commands(path: Path, vrfs: list[str]) -> list[str]:
    commands = []
    for line in path.read_text().splitlines():
        command = line.split("#", 1)[0].strip()
        if not command:
            continue
        if "{vrf}" in command:
            commands.extend(command.format(vrf=vrf) for vrf in vrfs)
        else:
            commands.append(command)
    return commands


def fixture_name(command: str) -> str:
    """'show vlan i-sid' -> 'show_vlan_i-sid.txt' (the name tests/test_fixtures.py expects)."""
    return "_".join(command.lower().split()) + ".txt"


def main() -> int:
    arguments = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    arguments.add_argument("--host", required=True)
    arguments.add_argument("--source", required=True, help="fixture folder, e.g. fe-9.4-gns3")
    arguments.add_argument("--username", default=os.environ.get("FE_USERNAME"))
    arguments.add_argument("--vrf", action="append", default=[], help="repeat for every VRF")
    arguments.add_argument("--commands", type=Path, default=COMMAND_FILE)
    options = arguments.parse_args()

    target = FIXTURES / options.source
    target.mkdir(parents=True, exist_ok=True)
    rejected: list[tuple[str, str]] = []
    with ConnectHandler(
        device_type="extreme_vsp",
        host=options.host,
        username=options.username or input("username: "),
        password=os.environ.get("FE_PASSWORD") or getpass.getpass("password: "),
    ) as connection:
        for command in read_commands(options.commands, options.vrf):
            output = connection.send_command(command, read_timeout=120)
            first_line = next((line.strip() for line in output.splitlines() if line.strip()), "")
            if first_line.startswith(("%", "^")):
                rejected.append((command, output.strip().splitlines()[-1]))
                continue
            (target / fixture_name(command)).write_text(output + "\n")
            print(f"saved   {command}")

    for command, message in rejected:
        print(f"REJECTED {command}: {message}", file=sys.stderr)
    print(f"\n{target}: run `pytest --update-golden`, then review the new .json files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
