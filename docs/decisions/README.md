# Decisions

One file per decision, numbered, never rewritten. A changed decision gets a new
record that says which one it supersedes, and the old record gets a "superseded by" line.

| # | Decision | Status |
|---|---|---|
| [0001](0001-name.md) | Name: `fabric-weft` / `fabric_weft` | accepted, user may veto |
| [0002](0002-scope-and-dependencies.md) | Text in, records out; standard library only; Python ≥ 3.10 | accepted |
| [0003](0003-parsing-approach.md) | Own table splitter plus row patterns, not TextFSM/TTP | accepted |
| [0004](0004-data-model.md) | Frozen dataclasses with normalised values | accepted |
| [0005](0005-error-policy.md) | Lenient by default, strict on request, switch errors raise | accepted |
| [0006](0006-fixtures.md) | Real captures are the evidence; golden files | accepted |
| [0007](0007-command-matching.md) | Commands matched like the CLI matches them | accepted |
| [0008](0008-port-lists.md) | How port lists are expanded | accepted |
| [0009](0009-key-value-output.md) | `Key : value` output read into sections; durations as `timedelta` | accepted, user may veto |
| [0010](0010-empty-fixtures.md) | Empty captures are fixtures only when listed | accepted, user may veto |
| [0011](0011-command-arguments.md) | A parser may say which arguments it accepts | accepted |
| [0012](0012-column-one-left.md) | A value one character left of its header belongs to that column | accepted |
| [0013](0013-vlan-zero.md) | VLAN 0 in a VLAN cell means "no VLAN" | accepted, user may veto |
| [0014](0014-running-config.md) | `show running-config`: one record per command, kept as printed | accepted, user may veto |

Template: **Status**, **Date**, **Proposed by**, **Objection**, then *Decision*, *Why*,
and the objection with its answer.
