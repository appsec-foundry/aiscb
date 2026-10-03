# Requirements

## ATTR-WORDS-001 Name the baseline in words

Source: specs/archive/2026-09-29-concrete-security-attribution, ATTR-CONCRETE-002,
approved by the user on 2026-09-29; `names_baseline` in
tests/design_confirmation.py from commit 5daf4ff; the user's approval of this
change on 2026-10-03.

Wherever aiscb-ATTR-001 requires attribution, the text names the aiscb baseline
in words. A rule ID alone does not count.

Acceptance: The `basic-silence`, `basic-accepted` and `persistent-secrets`
dialog cases and `design-accepted-risk-note` pass their attribution checks.

Example: A confirmation question reads "The aiscb baseline flags HTTP Basic's
reusable credentials; which approach do you want?" rather than citing only
`aiscb-AUTH-001`.
