# Requirements

## REPORT-CONDENSE-001 One statement per reporting behavior

Source: the user's request in this conversation to freeze and shorten
`aiscb-REPORT-001`; `specs/archive/2026-08-23-scope-security-risk-note/`
SCOPE-003, which requires the reporting rules to read as general statements;
and the size budget in `README.md`.

`aiscb-REPORT-001` states each behavior once: review the diff itself, report
only material security risks, put a risk under the note only when the
delivered work creates or worsens it, and keep the note to ordered,
single-sentence risks. Every behavior the archived reporting changes
established survives: credential literals including precomputed hashes,
reachable surfaces, weakened tests, install and CI files, the materiality
threshold, the pre-existing-weakness scope, no relabeling as minor or
hardening, no note for fixed issues, refusals, or requested reviews unless the
delivered part still creates a risk, one statement per risk, no `none`
placeholder, no assurance, no attack walkthrough, no rule citation, no change
narration, no subfindings, and no claim that code runs without executing it.

Acceptance: the group is about three quarters of its previous token count,
every behavior listed above still follows from the text, and `make check`
passes.
