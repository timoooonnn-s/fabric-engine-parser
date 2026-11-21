# 0005 · Lenient by default, strict on request, switch errors always raise

- **Status:** accepted
- **Date:** 2026-11-21 · **Proposed by:** Kurt · **Objection:** Margrit (accepted as strict mode)

## Decision

| Situation | Default (`strict=False`) | `strict=True` |
|---|---|---|
| A row doesn't match, or a value doesn't convert | row skipped, added to `result.skipped` with the reason | `ParseError` |
| The table the parser needs isn't in the output | `result.skipped` gets an entry with an empty line | `ParseError` |
| The switch answered `% Invalid input ...` or another `% ...` message | `DeviceError` | `DeviceError` |
| The command has no parser, or the abbreviation is ambiguous | `UnknownCommandError` | `UnknownCommandError` |

All four exceptions derive from `WeftError`.

## Why

- **Kurt:** during an outage, 47 good ports plus one reported odd line beat a traceback.
  A skipped line is never silent: `result.complete` is False and `result.skipped` says why.
- **Margrit:** in tests and in checks that have to be exact (pre/post migration
  verification), a skipped line is a bug. So strict mode exists and the fixture tests
  always use it.
- A switch error is different: the text isn't the command's output at all. Parsing it
  as "no records" would make a missing privilege look like an empty table, which
  actually happened in the production captures of switch-migrator.
