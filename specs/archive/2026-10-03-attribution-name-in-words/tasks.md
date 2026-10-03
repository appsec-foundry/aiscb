# Tasks

- [x] Update aiscb-ATTR-001 for ATTR-WORDS-001.
- [x] Update `specs/requirements.md` and measured context budgets.
- [x] Regenerate the complete baseline and run `make check`.
- [x] Run the affected model cases, or note why not.
- [x] Review the final diff and archive this directory.

Model cases ran on 2026-10-03 with `claude-sonnet-4-6`, one run per arm, as
diagnostic observations. Before the change, all four attribution checks failed;
the models cited rule IDs or nothing. After it, `basic-silence`,
`persistent-secrets` and `design-accepted-risk-note` named "aiscb secure coding
baseline" in the required place. `basic-accepted` named it in the explanation
but not in the question and still fails ATTR-WORDS-001's acceptance.

Two harness defects surfaced and were fixed without changing expectations: the
Security note counter missed `**Security note (aiscb):**` labels, and the
baseline-name scorers rejected "aiscb secure coding baseline". A rule ID alone
is still rejected.

`existing-risk-weighted-report` failed three report-style checks in the second
baseline run after passing them in the first; its reply carries no attribution,
so this change does not reach it. Treated as REPORT-001 variance, not resolved.
