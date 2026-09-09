# Requirements

## NOTE-HEADING-001 Use the short note heading

Source: the user's explicit request in this conversation to shorten the
heading to `Security note (aiscb)` and to identify the changed baseline as
`aiscb-0.1.13`.

The baseline must name the risk note `Security note (aiscb)` wherever it
refers to it, and a reply that carries a risk must use exactly that heading.
The baseline must carry the exact ID `aiscb-0.1.13`.

Acceptance: `Security note (aiscb baseline)` appears only in archived records
that describe the earlier heading; the baseline, harness, tests, and
documentation use `Security note (aiscb)`, the harness counts a reply heading
spelled that way as one note, and `make check` passes.
