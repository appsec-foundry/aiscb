# Tasks

- [x] Clarify core routing and the supply-chain trigger (ROUTE-001 to ROUTE-005).
- [x] Extend routing scenarios and failure-sensitive scoring (ROUTE-001, ROUTE-002, ROUTE-004).
- [x] Update specs/requirements.md and affected documentation (ROUTE-006).
- [x] Rebuild and measure every component with o200k_base (ROUTE-006).
- [x] Run make check and review the final diff (ROUTE-006).
- [x] Run affected model cases or record why none ran (ROUTE-006).
- [x] Archive the completed change (ROUTE-006).

## Verification

make check passes with the final normative wording. The routing suite has 35
deterministic tests, covering unnecessary agent and supply-chain loading,
routine source/check activity, continued-session reuse, redundant loads, reuse
without prior delivery, and required reloading after fresh-session context loss.
Existing positive HTTP/dependency scenarios, missing-policy refusal and
isolated application-behavior checks still pass. The test sandbox was preserved;
local sockets and Bubblewrap required running the suite outside the outer
command sandbox.

The complete artifact was regenerated. Final o200k_base measurements:

| Component | Bytes | Tokens |
| --- | ---: | ---: |
| Core | 10,467 | 2,010 |
| Supply-chain | 1,356 | 253 |
| Complete baseline | 31,066 | 6,004 |

Every other cataloged module was remeasured and retains its previous counts.
Both current measurement tables and affected budget comparisons agree. Rule
text grows by 100 tokens overall; discovery, loader instructions and overlays
remain additional context. Baseline version, dependency graph, security rule
bodies outside module selection, installations and published pins are unchanged.

No paid model runs were requested or made; verification for this wording change
was limited to deterministic assembly, loader integration and failure-sensitive
scoring. A focused dry run selects routine-tools, same-context, process-only,
context-loss and multiple as seven agent turns plus two preflight calls without
executing them. Actual model selection, native compaction and intervention
behavior remain unverified by these checks.
