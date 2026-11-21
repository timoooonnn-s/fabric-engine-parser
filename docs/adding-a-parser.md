# Adding a parser

Start from a real capture (decision 0006). Without one, wait.

## 1. Put the capture in place

```
tests/fixtures/<source>/show_isis_adjacencies.txt
```

`pytest` now lists it as *skipped: parser still to write*.

## 2. Write the record and the parser

Pick the module for the command family under `src/fabric_weft/parsers/`, or add one
and import it in `parsers/__init__.py`. The pattern:

```python
@dataclass(frozen=True, slots=True)
class IsisAdjacency:
    interface: str
    state_up: bool
    system_id: str
    host_name: str | None


_ADJACENCY_ROW = re.compile(r"(?P<interface>\S+)\s+\d\s+(?P<state>\S+)\s+...")


@parser("show isis adjacencies")
def parse_isis_adjacencies(output: Output) -> Iterator[IsisAdjacency]:
    """`show isis adjacencies` -> one IsisAdjacency per neighbour."""
    table = output.table("INTERFACE", "SYSID")  # find the table by its column labels
    if table is None:
        return  # already reported as skipped

    def build(row: str) -> IsisAdjacency:
        cells = fullmatch(_ADJACENCY_ROW, row)  # ValueError -> row reported as skipped
        return IsisAdjacency(
            interface=cells["interface"],
            state_up=flag(cells["state"]),
            system_id=cells["system_id"],
            host_name=optional(cells["host"]),
        )

    yield from output.build_each(table.rows, build)
```

Choosing how to read rows (decision 0003):

- **Row pattern** when each cell is one word, or a free-text cell sits between cells of
  known format. Anchor on what you're sure of (`trunk|access`, a MAC, a number).
- **`Columns.locate(header_line, ...)` + `columns.cut_rows(rows)`** when cells can be
  empty or contain spaces, or when lists wrap under their own column.

Use the converters in `values.py` (`flag`, `optional`, `ports`, `mac`, `int_list`,
`timestamp`) so the same value looks the same in every record (decision 0004). Keep open
vocabularies as strings.

## 3. Export it

Add the record and the `parse_...` function to `src/fabric_weft/__init__.py`.

## 4. Golden file, review, docs

```
pytest --update-golden
```

Read the generated `.json` against the `.txt` once, by eye. Then add the command to the
README table and to `council/PLAN.md`.
