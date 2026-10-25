# Requirements

## NOTE-003 Measure the note against the existing data flow

Source: the user's request and approval in this conversation, 2026-10-25;
baseline/aiscb-core.md, aiscb-OM-001 and aiscb-OM-006 (effective controls on
the path, commits 0c03d26 and 42f9b7f); the `existing-llm-report-links` case
(same provider and data category warrant no note, commit 665984b).

Use the Security note only when the delivery, after effective controls, lets an
attacker or untrusted input cause an outcome, or a party receive a class of
data, that the affected data flow did not already allow. A new component, call,
or injection point alone does not qualify.

Acceptance: A new model call that rewrites model-written finding text for a
host that already receives finding text, with severity and locations kept by
code, produces no Security note and no restatement of that risk elsewhere.

## NOTE-004 Keep the concrete dangerous failure for changed boundaries

Source: specs/archive/2026-08-23-scope-security-risk-note/, SCOPE-004
("its concrete dangerous failure mode remains materially unverified"), shortened
without approval of a behavior change in
specs/archive/2026-09-29-core-conservative-reduction/.

A changed critical boundary triggers the Security note only when its concrete
dangerous failure stays materially unverified.

Acceptance: A changed model boundary whose dangerous failure the delivered code
and tests cover produces no Security note.

## NOTE-005 Record accepted risks only when they qualify for the note

Source: the user's request and approval in this conversation, 2026-10-25;
NOTE-001 in specs/archive/2026-10-18-material-accepted-risk-note/.

Record an accepted exposure or risk in the Security note only when Review and
Report qualifies it for the note. Acceptance alone does not qualify a risk.

Acceptance: An approved proposal that accepts a risk the delivery does not
create or worsen yields no Security note. A confirmed retrievable, non-expiring
customer-key design still receives its one accepted-risk note.
