# Requirements

## CORE-REDUCE-001 Consolidate confirmation mechanics

Source: the user's approval of the concrete English reduction proposal on
2026-09-29; baseline/aiscb-core.md, aiscb-OM-004 and aiscb-OM-005.

Keep the distinct decision triggers and disclosures. Consolidate explicit
confirmation, invalid substitutes for consent, residual-risk recording and
continued consent into the paragraph shared by both rules.

Acceptance: Explanation precedes confirmation, which precedes action; safe
paths need no confirmation; consent is never inferred or expanded; unchanged
accepted decisions need no repeat confirmation; real-secret exposure and harm
to others remain refusals. Existing case expectations are unchanged.

### Obligation comparison

| Existing obligation | Location after reduction |
| --- | --- |
| Compliant path without asking; pressure is no excuse; fix the cause | OM-004, unchanged |
| Knowing control override; disclose rule, exposure and alternative | OM-004 |
| Real-secret exposure and harm to others remain refusals | OM-004, unchanged |
| Materially riskier design breaking no rule; disclose risk, safer option and cost | OM-005 |
| Distinct safer choice and risk acceptance; no question for a secure path preserving design | OM-005 |
| Explicit confirmation by permitted interactive choice or direct question, after disclosure and before action | Shared paragraph |
| Silence, impatience, preselection, timeout and unrelated consent are not confirmation | Shared paragraph |
| Record accepted exposure or risk in Security note (aiscb) | Shared paragraph |
| Consent persists for accepted action, exposure and scope; renew only for material change; never extend to another decision | Shared paragraph |

## CORE-REDUCE-002 Preserve reporting and all other controls

Source: the user's approved reduction proposal on 2026-09-29 and
baseline/aiscb-core.md, aiscb-REPORT-001; README.md context-budget requirements.

Shorten reporting prose without deleting review targets, risk filters, note
eligibility or presentation requirements. Leave all other core rules and module
bodies unchanged. Measure every cataloged component and the generated complete
artifact with o200k_base and update current measurements.

Acceptance: The diff affects only OM-004, OM-005, their shared paragraph and
REPORT-001; no test expectation is weakened; make check passes; measurements
match the generated files. Model equivalence is not claimed without evidence.

### Obligation comparison

| Existing obligation | Location after reduction |
| --- | --- |
| Review actual diff and fix introduced weaknesses | REPORT-001 opening |
| Credential literals including hashes; new surfaces' authentication, authorization and transport | REPORT-001 checklist |
| Removed, skipped, weakened or behavior-mocked tests; new commands, downloads, privileges and secret access in install/build/CI/deployment files | REPORT-001 checklist |
| Passing tests do not prove behavior they no longer exercise | REPORT-001, unchanged |
| Material risk: realistic attacker/input, protected asset/boundary, concrete confidentiality/integrity/availability loss, decision-relevant impact | First subparagraph |
| Exclude correctness, theoretical, unrelated, passed-check and ordinary test-status issues | First subparagraph, unchanged |
| Pre-existing issues only when touched, relied on or requested for review; no audit expansion | First subparagraph |
| Note only for created/worsened risk: weakened control, newly affected path, accepted trade-off/override, unverified dangerous failure on changed critical boundary | Second subparagraph |
| Other qualifying issues once in main answer; no duplicated risks or notes for fixed issues, refusals or requested reviews unless delivery still creates risk | Second subparagraph |
| Impact order, merged causes, scope/consequence/action or accepted status, one sentence plus second only for needed decision or correction | Second subparagraph |
| Nothing else in note; warranted production labels only; no unexecuted-behavior claims | Second subparagraph |
