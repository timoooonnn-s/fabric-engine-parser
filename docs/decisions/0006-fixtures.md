# 0006 · Real captures are the evidence; every fixture has a golden file

- **Status:** accepted
- **Date:** 2026-11-21 · **Proposed by:** Margrit · **Objection:** none

## Decision

1. A parser is written only from a real capture of its command. Reconstructions from
   documentation may pin edge cases, but they never prove a parser right.
   `tests/fixtures/README.md` records each fixture folder's source and whether it is real.
2. Layout: `tests/fixtures/<source>/<command>.txt`, where `<command>` is the command with
   spaces replaced by `_`. Next to it is `<command>.json` with the expected records.
3. One test (`tests/test_fixtures.py`) parses every capture **in strict mode** and compares
   it with its golden file. Adding a capture needs no test code:
   `pytest --update-golden`, review the JSON, commit.
4. A capture of a command without a parser shows up as a **skipped** test. The skip list
   is the parser backlog.
5. The repository is public. Lab output goes in as it is. Production output only after
   sanitising (host names, anything identifying), keeping every column at its width.
6. Captures come from `tools/capture.py`, which uses netmiko like the real tools do.

## Why

Earlier projects (switch-migrator, switch-backup) learned the hard way that a fixture
without provenance gets trusted as a real capture sooner or later. Golden files make a
change in parser output visible in the diff, field by field, across every release we
have a capture of.
