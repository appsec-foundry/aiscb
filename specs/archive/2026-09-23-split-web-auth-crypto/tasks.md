# Tasks

- [x] Split modules and update catalog/dependencies.
- [x] Update requirement IDs, tests and documentation.
- [x] Regenerate complete output and measure every source.
- [x] Run make check and review the diff.
- [x] Run four focused module-routing tasks and record limitations.
- [x] Archive the completed specification.

User approved the concrete specification paths and requirements, then confirmed
implementation. No baseline version or published bootstrap pins changed.

`make check` passed. Packaging and adapter checks were updated without removing
refusal checks. Clause reconstruction preserves the original five rule bodies;
authentication resolves cryptography once and the old module ID fails closed.

Measurements (bytes / o200k_base): core 8,357 / 1,656; web 1,766 / 381;
authentication 2,688 / 529; cryptography 1,111 / 234; data 1,943 / 383;
secrets 1,900 / 351; supply chain 1,173 / 223; deployment 1,659 / 311;
LLM applications 1,252 / 247; agents 2,033 / 401; retrieval 1,666 / 325;
MCP 2,236 / 414; complete 27,795 / 5,455. README and the handoff table
include the recomputed values and budget comparison. Discovery and loader
payloads are separately measured in docs/web-auth-crypto-split.md.

Focused model evidence: tests/results/split-20260923/, Sonnet 4.6, four
planning tasks and one preflight; no judges, retries or application execution.
All four plans were written. All new thematic modules were selected correctly,
but full routing passed only Web. Authentication and cryptography omitted
secrets-initialization; mixed omitted secrets-initialization and data-handling.
The unchanged module triggers remain required: these failures were retained,
not waived or repaired through post-hoc expectations. This is not evidence of
reliable full routing or of a regression: no matched pre-split control was run.
Model outcomes are evidence, not a release gate under specs/README.md.

No wide comparison or application-generation campaign was run. Existing
immutable installations remain untouched; this is a development source change,
not a published baseline release.


Follow-up fix requested by the user: cryptography now requires secrets-initialization;
authentication requires cryptography and data-handling. The three recorded failed
module sets were replayed through the real verified loader: all now deliver the
previously missing rules exactly once. Missing secrets content still fails closed.
The four deterministic split checks pass. The original model failures remain
recorded; no new model calls were made for this dependency-only correction.
A final isolated check of the staged commit follows the same make check gate.
