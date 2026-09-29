# Tasks

- [x] Update aiscb-ATTR-001 for ATTR-CONCRETE-001 and ATTR-CONCRETE-002.
- [x] Update affected model checks and deterministic scorer tests.
- [x] Update specs/requirements.md, documentation and measured context budgets.
- [x] Regenerate the complete baseline and run make check.
- [x] Run affected model cases or record why they were not run.
- [x] Review the final diff and archive this change.

Model cases were not run: this change updates the reporting contract and its
checks; paid stochastic runs are deferred, and no new model-compliance evidence
is claimed. Existing deterministic checks exercise attribution presence, missing
attribution, misuse of the Security note heading, and unnecessary confirmation.
The first make check exposed the session-loader capacity limit; compact wording
keeps the complete artifact within that unchanged limit.

## Approved follow-up after the targeted model run

The user approved correcting the observed placement ambiguity on 2026-09-29.
This restores ATTR-CONCRETE-002's existing acceptance criterion rather than
adding a requirement. The core now explicitly requires the name in the question
itself. HTTP Basic's compound judge question is split into five independently
scored checks: attribution, risk, safer alternative, cost and distinct acceptance.
Structural scoring rejects attribution placed only in option descriptions or a
header; regression tests cover both wrong placement and attribution in the question.
The later model attempt and quota interruption are documented in
`docs/core-attribution-regression-2026-09-29.md`. No further model calls were made
because the weekly limit was reached; the correction has no fresh model evidence.
