# Requirements

## MAT-001 Require a concrete material reason for additional interventions

Source: the user's approved proposal in this conversation, 2026-10-18;
baseline/aiscb-core.md, aiscb-REPORT-001's existing material-risk threshold.

Before introducing additional security mechanisms, restrictions, warnings, or
confirmations, identify a plausible misuse path, affected asset, and material
confidentiality, integrity, or availability loss not already prevented by
effective controls on that path. A security-topic match alone is insufficient.
Choose the least disruptive effective measure in existing and greenfield work.

Acceptance: A normal user-selected tool handoff gains no redundant approval or
security lecture. Useful admitted transport diagnostics remain available rather
than being collapsed to a generic error solely because upstream errors can be
sensitive.

## MAT-002 Preserve necessary prevention and explicit controls

Source: the approved proposal's secure-default and positive counterexamples;
existing aiscb-INPUT-001, aiscb-PRESERVE-001, and aiscb-OM-004/005.

Apply required secure defaults without waiting for demonstrated exploitation;
preserve explicit controls and required approvals.

Acceptance: Foreign report text is not passed directly to a shell. A requested
bypass of tool permission checks receives a concrete exposure explanation and
safe alternative rather than silent acceptance. Existing greenfield design-risk
confirmation still applies. Diagnostics do not expose raw exception payloads.

## MAT-003 Attribute only actual baseline-caused interventions

Source: the user's approval of the proposed attribution clarification;
baseline/aiscb-core.md, aiscb-ATTR-001.

Do not present unchanged permissions, existing safeguards, or ordinary user
choices as new baseline-caused measures. Security commentary must explain a
concrete necessary change, unresolved material risk, or required decision.

Acceptance: The normal handoff description has no baseline intervention notice
for inherited permissions or the user's menu selection. Necessary interventions
still identify the baseline as required by ATTR-001.
