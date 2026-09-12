# Requirements

## CONFIRM-001 Use the available choice mechanism

Source: the user's approval "ok mache das so" of the recommendation to align
OM-005 with OM-004, followed by "ja" approving these specification files.

For an already-required design confirmation, use an available, permitted
interactive choice tool; otherwise ask a direct question. Present the safer
option and explicit acceptance of the named risk as distinct choices.

Acceptance: an offered and permitted question tool is called; without one,
the assistant asks directly. Neither path adds approvals for secure defaults.

## CONFIRM-002 Make the decision attributable and explicit

Source: the same approved recommendation, and existing `aiscb-ATTR-001`.

The confirmation question identifies the aiscb baseline and states the risk,
safer alternative, and cost. Do not perform dependent work until the user
explicitly answers. A preselection, timeout, or silence is not confirmation.

Acceptance: the dialog or fallback question carries that context. A returned
empty answer, timeout, or unsubmitted preselection does not authorize the
riskier design; an explicit answer remains sufficient for that one decision.

## ATTR-001 Integrate attribution into the affected explanation

Source: the user's complaint about the separate aiscb paragraph after the
shared-secret-store design, approval "ok mache das" of the proposed integration
and its specification files, and existing `aiscb-REPORT-001`.

Name the baseline within the explanation or confirmation question for the
decision it directs. Do not append a separate attribution paragraph. A final
Security note remains reserved for qualifying residual risks under REPORT-001;
do not repeat the same risk or add a note merely to explain baseline compliance.

Acceptance: the shared, persistent-secret design explains the baseline's
effect in its flow, without a separate aiscb footer or a risk note for controls
that were satisfied. A delivered design with a qualifying residual risk still
reports that risk once under Security note (aiscb).
