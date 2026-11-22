# 0010 · A capture without records is a fixture only when listed as empty on purpose

- **Status:** accepted, user may veto
- **Date:** 2026-11-21 · **Proposed by:** Claude, from the 9.4 lab capture · **Objection:** none yet

Extends decision 0006.

## Decision

`tests/test_fixtures.py` still requires every fixture to produce at least one record,
except the captures named in `EMPTY_ON_PURPOSE`. Those must produce **none**.

## Why

- A real switch with no MLT or no vIST is real evidence too: it proves that a table
  with a header but no rows parses to no records without a skipped line.
- Without the list, a parser that silently drops every row would pass with an empty
  golden file. With it, an empty result is a claim someone made by name and a
  reviewer can check against the `.txt`.
