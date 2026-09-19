# Tasks

- [x] Record approved scope, sources and acceptance criteria.
- [x] Change core status and initial-loading behavior.
- [x] Implement default modular setup, migration and signed distribution support.
- [x] Add targeted tests for all three adapters and failure boundaries.
- [x] Update requirements, guidance and all context measurements.
- [x] Run make check and review the diff.
- [x] Run targeted client probes or record unavailable evidence.
- [x] Archive this change and prepare the reviewed commit.

Verification: `make check` passed, including complete-mode compatibility tests.
Targeted setup tests cover the default adapters, migration, ownership and
failure boundaries. All twelve real-CLI initial-context probes passed with
Claude Code 2.1.278, Codex CLI 0.154.0 and Copilot CLI 1.0.83 (project/user,
root/subdirectory). They use a local API fixture, not a real model. No paid
semantic model cases were run: delivery and deterministic loading were tested;
model selection/status behavior and IDE surfaces remain explicitly unverified
in docs/agent-integration-verification.md. Every cataloged rule-text size was
recomputed with o200k_base; core 8,138 bytes / 1,617 tokens, complete 26,964 /
5,274, plus adapter and overlay context. No version or published pin changed.
