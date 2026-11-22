# 0009 · `Key : value` output is read into sections; durations become `timedelta`

- **Status:** accepted, user may veto
- **Date:** 2026-11-21 · **Proposed by:** Claude, from the 9.4 lab capture · **Objection:** none yet

## Decision

- Some commands print no table but sections of fields (`show sys-info`):

      General Info :
              SysName      : sw1

  `fields.split_sections` reads them into `{section: {key: value}}`, and
  `Output.section(name)` hands a parser one section. It sits next to the table splitter
  as a second way to *split* output (decision 0003, layer 2).
- Keys stay exactly as printed (`Serial#`, `H/W Revision`). Only the first colon splits,
  so values keep their own colons (`http://...`, `09:09:50`). Lines without a colon,
  such as the small tables inside `show sys-info`, are ignored by this reader.
- A field the parser needs but cannot find is reported like a missing table: skipped
  in lenient mode, `ParseError` in strict mode (decision 0005). Fields that are printed
  empty become `None`.
- Durations (`0 day(s), 00:09:01`) become `datetime.timedelta`. This extends decision
  0004, which covers points in time but not lengths of time.

## Why

- A row pattern per field would repeat the same regex twenty times. Splitting once and
  looking fields up by key is shorter and reads like the output.
- Looking a field up by section *and* key keeps repeated keys apart (`Status` appears in
  several `show sys-info` sections).
- `timedelta` compares and adds without parsing again, which is what an uptime check
  ("did the switch reboot during the change?") needs. In the golden JSON it shows as
  `0:09:01`.
