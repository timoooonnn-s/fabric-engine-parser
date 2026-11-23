#!/usr/bin/env python3
"""Capture show-command output from a switch as test fixtures.

    pip install -e '.[capture]'
    python tools/capture.py --host 192.0.2.10 --source fe-9.4-gns3 --vrf RED --vrf BLUE

    # several switches in one run, one fixture folder each (<source>-<name>):
    python tools/capture.py --source fe-9.4-gns3 \
        --host core1=192.0.2.11 --host core2=192.0.2.12 \
        --host access1=192.0.2.21 --host access2=192.0.2.22 --vrf RED

Runs every command in tools/capture_commands.txt over SSH with netmiko (exactly
what the tools using this library do) and writes each output to
tests/fixtures/<folder>/<command>.txt. Before the commands it runs `enable` (which
`show running-config` and others need) and `terminal more disable`; a switch where
either fails is skipped. --no-enable stays in user mode. Commands the switch rejects
are listed at the end and not saved.
Credentials, asked once for all switches: --username or $FE_USERNAME, then
$FE_PASSWORD or a prompt; an enable password, if the switch has one, from $FE_SECRET.
--list prints what would be captured without connecting.

For the lab only. Output from production switches carries real names and
addresses and must be sanitised before it goes into this public repository.
"""

from __future__ import annotations

import argparse
import getpass
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from netmiko import ConnectHandler
from netmiko.exceptions import ReadTimeout

ROOT = Path(__file__).resolve().parent.parent
COMMAND_FILE = Path(__file__).with_name("capture_commands.txt")
FIXTURES = ROOT / "tests" / "fixtures"


def read_commands(path: Path, vrfs: list[str]) -> list[str]:
    commands: list[str] = []
    for line in path.read_text().splitlines():
        command = line.split("#", 1)[0].strip()
        if not command:
            continue
        if "{vrf}" in command:
            commands.extend(command.format(vrf=vrf) for vrf in vrfs)
        else:
            commands.append(command)
    return commands


@dataclass(frozen=True)
class Target:
    host: str
    folder: Path


def read_targets(hosts: list[str], source: str) -> list[Target]:
    """'192.0.2.10' -> <source>/; 'core1=192.0.2.11' -> <source>-core1/.

    One unnamed host is fine. With several, every host needs a name, so their
    captures cannot overwrite each other.
    """
    targets = []
    for spec in hosts:
        name, _, address = spec.rpartition("=")
        if len(hosts) > 1 and not name:
            raise SystemExit(f"--host {spec}: with several hosts, give each a name (core1={spec})")
        targets.append(Target(address, FIXTURES / (f"{source}-{name}" if name else source)))
    folders = [target.folder for target in targets]
    if len(set(folders)) != len(folders):
        raise SystemExit("two --host entries share a name")
    return targets


def fixture_name(command: str) -> str:
    """'show vlan i-sid' -> 'show_vlan_i-sid.txt' (the name tests/test_fixtures.py expects)."""
    return "_".join(command.lower().split()) + ".txt"


def main() -> int:
    arguments = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    arguments.add_argument(
        "--host", action="append", required=True, help="address, or name=address; repeatable"
    )
    arguments.add_argument("--source", required=True, help="fixture folder, e.g. fe-9.4-gns3")
    arguments.add_argument("--username", default=os.environ.get("FE_USERNAME"))
    arguments.add_argument("--vrf", action="append", default=[], help="repeat for every VRF")
    arguments.add_argument("--commands", type=Path, default=COMMAND_FILE)
    arguments.add_argument("--no-enable", action="store_true", help="stay in user mode")
    arguments.add_argument("--list", action="store_true", help="show the plan, do not connect")
    options = arguments.parse_args()

    targets = read_targets(options.host, options.source)
    commands = read_commands(options.commands, options.vrf)
    if options.list:
        for target in targets:
            print(f"{target.host} -> {target.folder.relative_to(ROOT)}/")
        print(*(f"  {command}" for command in commands), sep="\n")
        return 0

    username = options.username or input("username: ")
    password = os.environ.get("FE_PASSWORD") or getpass.getpass("password: ")
    failed = 0
    for target in targets:
        print(f"\n=== {target.host} -> {target.folder.relative_to(ROOT)}/")
        try:
            with ConnectHandler(
                device_type="extreme_vsp",
                host=target.host,
                username=username,
                password=password,
                secret=os.environ.get("FE_SECRET", ""),
            ) as connection:
                prepare(connection, privileged=not options.no_enable)
                rejected, lost = capture(connection, commands, target.folder)
        except Exception as error:  # one dead switch must not stop the rest
            print(f"FAILED  {target.host}: {error}", file=sys.stderr)
            failed += 1
            continue
        for command, message in rejected:
            print(f"REJECTED {command}: {message}", file=sys.stderr)
        for command, message in lost:
            print(f"LOST    {command}: {message}", file=sys.stderr)
        failed += bool(lost)

    folders = " ".join(str(target.folder.relative_to(ROOT)) for target in targets)
    print(f"\n{folders}: run `pytest --update-golden`, then review the new .json files")
    return 1 if failed else 0


def prepare(connection: Any, *, privileged: bool) -> None:
    """`enable`, then `terminal more disable`, before any show command.

    netmiko already sends `terminal more disable` at login, but in user mode. It is sent
    again after `enable` so no output stops at a --More-- prompt. A switch where either
    step fails is not captured: user-mode output would be incomplete fixtures.
    """
    if privileged:
        connection.enable()
        if not connection.check_enable_mode():
            raise RuntimeError("enable did not reach privileged mode (#)")
        print("ok      enable")
    answer = connection.send_command("terminal more disable")
    if answer.strip().startswith(("%", "^")):
        raise RuntimeError(f"terminal more disable rejected: {answer.strip()}")
    print("ok      terminal more disable")


def capture(
    connection: Any, commands: list[str], folder: Path
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Run the commands and save each output.

    Returns the commands the switch rejected, and the ones whose output was lost
    (empty twice, or no prompt within the timeout). Neither is saved: an empty or cut
    file would become a wrong fixture. One lost command does not stop the others.
    """
    folder.mkdir(parents=True, exist_ok=True)
    # The prompt is matched by this pattern, never found again per command: on a slow
    # switch netmiko's own prompt search read leftover output as the prompt (fe-04,
    # 2026-11-22) and every later command then waited for that line.
    prompt = re.escape(connection.base_prompt) + r"[^\n]*[>#]"
    rejected: list[tuple[str, str]] = []
    lost: list[tuple[str, str]] = []
    for command in commands:
        output = run(connection, command, prompt)
        if output is None:
            lost.append((command, "no output after a retry; run this switch again"))
            continue
        if is_rejected(output):
            rejected.append((command, output.strip().splitlines()[-1]))
            continue
        (folder / fixture_name(command)).write_text(output + "\n")
        print(f"saved   {command}")
    return rejected, lost


def is_rejected(output: str) -> bool:
    """The switch refused the command: '% Invalid input …' or 'Error: …', after the banner."""
    for line in output.splitlines():
        text = line.strip()
        if not text or text.startswith(("*", "Command Execution Time")):
            continue
        return text.startswith(("%", "^", "Error:"))
    return False


def run(connection: Any, command: str, prompt: str) -> str | None:
    """One command's output, or None if it came back empty twice or timed out.

    The buffer is cleared first, so a stray prompt from the command before cannot end
    this one early with empty output.
    """
    for _attempt in range(2):
        connection.clear_buffer()
        try:
            output: str = connection.send_command(command, expect_string=prompt, read_timeout=120)
        except ReadTimeout:
            continue
        if output.strip():
            return output
    return None


if __name__ == "__main__":
    sys.exit(main())
