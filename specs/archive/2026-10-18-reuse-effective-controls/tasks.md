# Tasks

- [x] Add application-development scope and standalone operations coverage (REUSE-003).
- [x] Update OM-001 and LIMITS-001 for REUSE-001 and REUSE-002.
- [x] Extend the dynamic loader and exact four-part migration support (REUSE-004).
- [x] Update affected test criteria and the requirements catalog.
- [x] Regenerate the complete baseline and measure every artifact with o200k_base.
- [x] Update current measurements and budget comparisons in documentation.
- [x] Run make check and review the final diff.
- [x] Run affected model cases or record why they were not run.
- [x] Archive this specification.

The affected model matrix was checked with
`python3 tests/run.py --dry-run --cases existing-scoped-change,greenfield-untrusted-input --repeats 1`.
No paid model runs were started for this wording change: even this narrow
comparison schedules four agent runs, up to twelve judge calls, and two preflight
probes. Routing selection was also checked with
`python3 tests/routing.py --dry-run --cases standalone-ops,scope-change,multiple`:
four agent turns and two preflight calls, not executed. The new semantic criteria
remain unexecuted; deterministic validation does not establish assistant behavior.

Measured with o200k_base: core 8,891 bytes / 1,736 tokens; data-handling module
2,795 bytes / 532 tokens; complete baseline 29,307 bytes / 5,699 tokens. All other
cataloged modules were remeasured and retain their listed counts. The approximate
core context shares round to 0.9% of 200,000 and 0.17% of 1,000,000 tokens.

Initial `make check` passed assembly and structural checks, then failed three
modular setup tests because the generated baseline exceeds the legacy dynamic
loader's four-part capacity of 28,400 characters. The loader fails closed before
creating hooks. The user explicitly approved a five-part follow-up. Exact managed
four-part loader text and hook commands are recognized for update, static loading,
removal, and modular migration; modified content remains rejected. Fallback
commands now enumerate all five parts. The helper digest was added to the existing
allow-list; published bootstrap pins and the baseline version are unchanged.

`make check` passes, including 31 routing tests, 27 session-switch tests, and 38
modular-setup tests. Routing covers both applicable application changes and an
independent AWS/Terraform configuration edit, rejecting unnecessary module loads,
missing requested edits, and changes to application code. Loader checks cover
complete output, exact capacity and overflow, old-installation transitions,
preservation of unrelated hooks, and rejection of customized four-part content.
The outer sandbox initially blocked Bubblewrap's network namespace; the complete
suite passed with approved execution outside that sandbox, retaining Bubblewrap
isolation for generated-code checks. No live CLI session-hook probe was run.
