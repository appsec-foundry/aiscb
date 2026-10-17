# Tasks

- [x] Clarify aiscb-MODULES-001 (SCOPE-001).
- [x] Add and verify the process-only routing scenario (SCOPE-002).
- [x] Update the requirements catalog and routing documentation.
- [x] Rebuild and measure the core, every module, and complete artifact.
- [x] Run make check and review the diff.
- [x] Record affected model evidence or the reason no model cases ran.
- [x] Archive the completed change.

## Verification

The 29 deterministic routing tests pass, including the new negative cases for
unnecessary web loading, omitted or late data-handling loads, wrong signal or
return behavior, exited children, and unrelated HTTP edits. Existing HTTP and
dependency cases still pass. The scoped dry run selects process-only and
multiple as two model turns plus two preflight calls without executing them.

make check passes. The initial wording crossed the legacy session loader's
28,400-character capacity; equivalent shorter wording preserves ordinary and
derived-baseline loading without changing the loader or its limits.
The final complete artifact is 28,387 bytes / 5,547 o200k_base tokens; core is
8,060 bytes / 1,598 tokens. Every cataloged module was remeasured and retains its
previous counts. README and other current measurements were updated.

No paid model runs were made for this wording change: verification was limited
to deterministic assembly, loader integration, and failure-sensitive scoring.
Actual model selection for the new scenario remains unverified; these checks
are not evidence that a model reliably avoids unrelated modules.
