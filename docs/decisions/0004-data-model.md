# 0004 · Records are frozen dataclasses with normalised values

- **Status:** accepted
- **Date:** 2026-11-21 · **Proposed by:** Vera · **Objection:** Kurt (partly accepted)

## Decision

- Every record is a `@dataclass(frozen=True, slots=True)`. They're immutable,
  hashable, small in memory and typed. A parser yields one record type.
- Every parser returns a `ParseResult`: `.records`, `.skipped`, `.complete`,
  `.as_dicts()`, and it can be iterated directly.
- Values are normalised:
  - numbers → `int`, states (`up/down`, `true/false`, `enable/disable`) → `bool`
  - placeholders (`-`, `--`, `N/A`, `NONE`) → `None`
  - port lists → expanded `tuple[str, ...]` of single ports (`'1/1'`, `'1/17/2'`), see 0008
  - MAC addresses → `aa:bb:cc:dd:ee:ff`. IS-IS system IDs stay `xxxx.xxxx.xxxx`: they
    are identifiers, not MACs.
  - timestamps → naive `datetime`. The switch prints no time zone.
- **Open vocabularies stay strings exactly as printed** (VLAN type `byPort`, I-SID type
  `ELAN`, MLT type `smlt`). A release that adds a value must not make records disappear.
- Field names are spelled out (`admin_up`, `customer_vid`, `dot1q_encapsulation`), not
  the switch's column headers.

## Changed from the first proposal

The first proposal said "raw line kept on each record". Dropped: an `Mlt` is merged
from four tables and a `VlanMembers` from wrapped lines, so a single raw line would be
misleading. Lines that could not be read are reported in `ParseResult.skipped` instead.

## Objection

*Kurt:* "A bool for port state loses a third state like `testing`." Accepted halfway:
an unknown word doesn't become `False`. The converter raises, the line is reported as
skipped, and the next capture shows us the new word.
