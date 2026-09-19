# Tasks

- [x] Rename the core and integrate secure design and agent-system rules.
- [x] Implement verified local installation, dependencies, and organization overlays.
- [x] Update the requirements catalog, README, and overlay guidance.
- [x] Add `make build-full-baseline` for the optional generated complete artifact.
- [x] Regenerate artifacts and measure o200k_base sizes: core 7,857 bytes /
  1,582 tokens; complete artifact 20,917 bytes / 4,150 tokens. README records
  the provisional budget overruns explicitly.
- [x] Compare current OWASP LLM 2026 and Agentic 2026 coverage; record partial
  coverage and proposed follow-up separately from normative rules.
- [x] Run deterministic checks: 12 local policy tests, builder mutations,
  organization packaging, and the preceding make-check suites pass. `make check`
  ends with the same five release failures: four bootstrap checks and the stale
  signature, pending the maintainer release sequence. `bundle.json` describes
  the changed files; no signature or published tag was fabricated.
- [x] Record model-test status: no paid model runs. The new loader has direct
  boundary tests, but actual client selection and the new design/agent rules
  have no model evidence. The complete suite spans all rule domains; the user
  requested feature-branch implementation and review, not a paid benchmark.
- [ ] Complete maintainer signing and release checks before archiving.
