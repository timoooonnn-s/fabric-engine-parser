# 0008 · How port lists are expanded

- **Status:** accepted
- **Date:** 2026-11-21 · **Proposed by:** Vera · **Objection:** Kurt (on rule 3)

## Decision

`values.ports()` expands Fabric Engine port lists into single ports:

1. `1/1-1/3,1/10` → `1/1, 1/2, 1/3, 1/10`. `NONE`, `-` and an empty cell → nothing.
   A trailing comma (left over from wrapping) is ignored.
2. **Channelized ranges** spanning several parent ports (`1/17/1-1/18/4`) can't be
   enumerated from the text alone, because the number of channels isn't printed. The
   **last sub-port of the range is taken as the channel count**: Fabric Engine writes such
   a range to the end of the last parent port, so `1/17/1-1/18/4` means 4 channels.
   A range that contradicts this (`1/17/3-1/18/2`) is rejected.
3. A range across **slots** (`1/47-2/2`) is rejected with `ValueError`, so the line is
   reported as skipped and not guessed.

## Objection

*Kurt:* "Rule 3 throws away a whole VLAN row for one odd range." Accepted as a
trade-off: no capture has shown a cross-slot range (the switch compresses ranges per
slot), and a guessed port list in a migration verifier is worse than a reported line.
If a capture ever shows one, this decision gets a successor.
