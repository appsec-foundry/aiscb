# Tasks

- [x] Add two modules and focused data/web rules; update catalog and summaries.
- [x] Verify and correct installer and organization/gateway integration:
  explicit --complete, all-managed-tool updates, installation-record validation,
  and 18 local-policy tests including generated-command execution and rollback.
- [x] Update rollout instructions, README, and coverage limitations; document
  absolute paths, inherited-policy checks, no multi-file transaction, and the
  distinction between coding modules and a not-yet-implemented remote loader.
- [x] Regenerate full baseline, measurements, and unsigned bundle manifest.
  o200k_base: core 7,897 bytes / 1,593 tokens; complete 26,234 / 5,150.
  README contains fresh measurements for every module and budget overruns.
- [x] Run make check: sandbox prevented the HTTP test server, so rerun with
  permission outside the sandbox. All suites preceding release checks passed;
  five existing release checks fail (four bootstrap checks and the committed
  signature) until maintainer signing and bootstrap refresh. No gate weakened.
- [x] Record model evidence: no paid model or actual-client runs. Deterministic
  tests establish delivery and dependency boundaries, not semantic selection,
  application security, production gateway compatibility or cross-platform rollout.
- [ ] Complete maintainer release signing before archiving.
