# Tasks

- [x] Record approved requirements and compare obligations for CORE-REDUCE-001 and CORE-REDUCE-002.
- [x] Apply the approved core wording and confirm the bounded diff.
- [x] Regenerate the complete baseline and measure all cataloged components.
- [x] Update current size measurements and verify the requirements catalog remains accurate.
- [x] Run make check without weakening existing test expectations.
- [x] Run affected model cases or record why they were not run.
- [x] Review the final diff and archive the change.

Verification scope: the approved candidate matches byte-for-byte, rule IDs are
unchanged, and the security floor, verification and attribution texts are
unchanged. The existing requirements catalog still describes the same duties;
no catalog prose or test expectations needed modification for this reduction.
All eleven modules were remeasured and retain their prior byte/token counts.
Core: 7,876 bytes / 1,560 tokens; complete: 28,203 bytes / 5,509 tokens.

Affected model cases were not run: this is a conservative textual consolidation
with unchanged acceptance criteria; paid stochastic runs were deferred. The
obligation comparison and deterministic checks do not establish identical model
behavior. No new model-compliance evidence is claimed.
