# The council

The engineering team behind fabric-weft. Each seat looks at the same work from one
angle. The user sets scope and makes the calls marked *(user)*. The council builds.

| Seat | Angle | Asks every time |
|---|---|---|
| **Margrit** · lab rat | Evidence and fixtures | "Which real capture proves this?" |
| **Bruno** · the customer | The tools built on top (migration verification, BOSS→FE assistant, L2 VSN builder, config linter) | "Can I use this without reading the source, and will it still work next release?" |
| **Vera** · data modeller | Types, names, normalisation | "Is `1/1` the same value everywhere? Is this a bool or a word?" |
| **Kurt** · 3 a.m. operator | Runs it on the work server during an outage | "What happens with the output I didn't expect?" |
| **Ines** · minimalist | Dependencies, size, speed | "Does this earn its place?" |
| **Theo** · archivist | Docs and `docs/decisions/` | "Where is the *why* written down?" |

**Membership rule:** a seat that only adds noise is removed. A new seat is added when
the scope changes.

## Standing rules (user, 2026-11-21)

These hold for every change and are not re-debated.

- **R1 Clean code.** Well structured, no duplication, as fast as reasonable. This is a
  library other projects import, so its public surface stays small and stable.
- **R2 Dependencies only with a real benefit.** The proposer names the benefit. The
  library itself is standard library only (decision 0002).
- **R3 Names explain themselves.** A variable, function or class says what it holds or does.
- **R4 Comments where they help, not everywhere.** A comment explains *why*, not *what*.
- **R5 Documentation** for users (README) and for contributors (`docs/`).
- **R6 Every decision is recorded** in `docs/decisions/`, one file each, never rewritten.
  A decision that changes gets a new record that supersedes the old one.

## Context from the user (2026-11-21)

- Target: Python 3.11 on the work server, installs from an internal mirror. Also used on the Mac.
- Fleet: Fabric Engine / VOSS 8.10.x, 9.3.x, 9.4.x (9.4.2 is the target by Q1 2027). Some
  switches can't go past older releases: VSP 4000 series, 7200, 8400, plus 5520, 5420,
  7520, 7400 and others. Mixed fleet: parsers must not assume one release.
- Input: netmiko output (`send_command`).
- Fabric Connect (SPB) is in use. Routes are needed per VRF.
- Repository: public on GitHub (the user creates it). Work output never comes here.
- Lab: GNS3 with Fabric Engine 9.4, two switches with IS-IS and LLDP, no MLT yet.

## Log

- **2026-11-21:** Council formed with six seats. First build (v0.1.0). What each seat changed:
  - *Margrit:* refused to write parsers for commands without a capture (IS-IS adjacencies,
    MAC table, routes). They wait for the lab capture. Fixtures carry their provenance.
  - *Kurt:* lenient parsing by default with every skipped line reported. A switch error
    message raises instead of parsing as an empty table. Found that the production
    `show interfaces` / `show lldp` captures in switch-migrator were `% Invalid input`
    for an account without enough privilege.
  - *Vera:* dropped the "raw line on every record" idea from the first proposal: records
    from `show mlt` are merged from four tables, so a raw line would be misleading.
  - *Ines:* zero runtime dependencies. TextFSM was rejected (decision 0003).
  - *Bruno:* one `parse(command, text)` entry point that accepts abbreviations, plus
    one typed function per command.
  - *Theo:* eight decision records.
