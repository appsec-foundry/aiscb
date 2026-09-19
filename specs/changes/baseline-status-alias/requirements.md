# Requirements

## STATUS-ALIAS-001 Recognize the aiscb status question

Source: the user's request to allow `aiscb` alongside `baseline`, followed by
confirmation that `aiscb?` should show whether aiscb is loaded in Codex.

When implemented, `aiscb` and `aiscb?` must trigger the same answer as
`baseline?`: baseline identity, source, loaded modules, and overlays, using
only the current context without reading files first.

Acceptance: in separate fresh sessions with the baseline loaded, each of the
three triggers produces the same status fields without file reads. The
existing `baseline?` behavior remains available.

## STATUS-ALIAS-002 Keep this change pending

Source: the user's instruction to prepare the change first and consider
whether more changes should be included in the next release.

Record the proposal without changing normative text, choosing a version,
or replacing published 0.1.16 assets.

Acceptance: this preparation changes only the three files in this change
directory; implementation and release tasks remain open.
