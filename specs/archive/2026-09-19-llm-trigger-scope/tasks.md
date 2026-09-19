# Tasks

- [x] Rename the module and clarify its trigger for LLM-SCOPE-001. Compared the
  aiscb-LLM-001 rule body with the previous source: unchanged.
- [x] Update dependencies, current references, and the requirements catalog.
  Other trigger strings, rule IDs, and versions remain unchanged. Agent and
  retrieval modules already distinguish application work; supply-chain still
  covers dependency execution by the assistant.
- [x] Verify discovery, loading, dependency order, and obsolete-ID rejection
  through the installed adapter for every supported tool and the source loader.
- [x] Rebuild the complete artifact and remeasure every module with o200k_base.
  Core: 7,780 bytes / 1,558 tokens; LLM Applications: 1,255 / 246;
  agent-systems: 2,054 / 398; retrieval-memory: 1,551 / 301;
  complete: 26,257 / 5,138. Other module counts are unchanged and verified.
- [x] Run make check and review the final diff. Passed, including the new
  installed discovery and rename test; git diff --check passed.
- [x] Record model-routing evidence or why model cases were not run. No paid
  model cases were run: the current main harness installs the complete baseline,
  and its organization experiment tests a synthetic pack rather than this
  catalog's module selection. Neither proves the changed routing behavior.
  Added concrete positive and negative scenarios to docs/local-policy-installation.md;
  actual-client module selection remains an explicit evidence gap.
- [x] Archive this change directory under 2026-09-19-llm-trigger-scope.
