# 0014 · `show running-config` becomes one record per command, kept as printed

- **Status:** accepted, user may veto
- **Date:** 2026-11-22 · **Proposed by:** Claude, from the four-node 9.4 capture · **Objection:** none yet

## Decision

`parse("show running-config", text)` yields one `ConfigCommand(section, context, command)`
per configuration command, in the order printed:

- `command` is the line exactly as printed (quotes and all). No command is interpreted.
- `section` is the name in the `# … #` comment block above it (`ISIS SPBM CONFIGURATION`),
  `None` before the first one.
- `context` is the line that opened the context the command is in
  (`interface GigabitEthernet 1/1`, `router isis`), `None` at the top level. The opening
  line is itself a top-level command. The same context can appear in several sections.

Left out: the comment header before `config terminal`, `config terminal`, `end`,
comment lines (`#…`, including commented-out commands) and `exit`.

How a context is found: Fabric Engine prints no indentation. A context is the run of
commands that ends with `exit`; it starts after the previous `exit`, comment line or
blank line. Blank lines directly before `exit` belong to the context (9.4 prints one
there). An `exit` with nothing to close, or a context still open at the end, is
reported as a skipped line.

## Why

- The config linter, the first user, asks "is `no spanning-tree` set on every fabric
  port?" or "is `ssh` enabled?". That needs every command with the context it is in,
  not a model of every Fabric Engine feature. A model per command would be thousands of
  record types, each an open vocabulary (decision 0004).
- Keeping the command text exact means nothing is lost or reformatted; a caller can
  match on it with the same strings an engineer types.

## Not seen yet

Nested contexts (two `exit`s in a row) and a blank line in the middle of a context.
Both would be read wrongly by the rule above. Neither appears in the 9.4 captures; when a
capture shows one, the rule gets a test and, if needed, a new decision.
