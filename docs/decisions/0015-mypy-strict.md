# 0015 · mypy in strict mode is a development check

- **Status:** accepted (user, 2026-11-22)
- **Date:** 2026-11-22 · **Proposed by:** Claude · **Objection:** none

Extends decision 0002, point 4 (development extras).

## Decision

`mypy>=1.10` joins `pytest` and `ruff` in the `dev` extra. `[tool.mypy]` in
`pyproject.toml` runs it in strict mode on `src` and `tests`, for Python 3.10. A change
is done when `pytest`, `ruff check .`, `ruff format --check .` and `mypy` all pass.

It is a development dependency only: the library still has no runtime dependencies.

## Why

- Named benefit (rule R2): the first strict run found two real typing errors in core
  code that tests cannot catch. `Parser` returned `ParseResult`, which was invariant in
  its record type while the protocol was covariant, and `Output.build_each` joined row
  cells without the type saying a row is iterable.
- The package ships `py.typed`. Callers type-check against our records, so wrong or
  loose annotations become their errors.
