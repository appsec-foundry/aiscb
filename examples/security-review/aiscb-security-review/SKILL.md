---
name: aiscb-security-review
description: Arrange a requested independent security review of an implementation change in a fresh context using the same AISCB policy. Return findings to the implementer. Not for ordinary implementation or a repository-wide audit.
---

# Independent AISCB security review

Keep AISCB active during implementation. The reviewer reports problems;
the implementer makes corrections and remains responsible for tests and final
review. This workflow adds no application security requirements.

## 1. Prepare the handoff

Fill [handoff.md](references/handoff.md) from the authorized task and repository
evidence. Reuse established requirements and decisions; ask only when missing
information prevents the review. Do not invent acceptance criteria.

Use a stable code snapshot and the implementer's existing policy source.
Pause edits if needed. Do not create commits, install policy or change user
settings to prepare the review.

## 2. Start one reviewer

Give the complete [reviewer instructions](references/reviewer.md) and completed
handoff to one fresh context. Exclude the implementation conversation and this
coordinator workflow.

- Use a separate agent only when authorized and able to start without inherited
  conversation. Otherwise return the handoff and instructions for a new
  user-started session with access to the same code and policy. Mark it **prepared**.
- Request only scoped read access and the policy loader. Use host-enforced
  read-only access where available; instructions alone do not enforce it.
  Do not grant general write, shell, network, credential or delegation access.
- Start at most one pass. No nested agents, automatic retries or repair loops.
  Apply available host time/turn limits and cancellation. Mark interruption
  **incomplete**.

Self-review is not an independent review. Claim a fresh context, enforced
permissions or successful policy loading only when verified.

## 3. Return the result

Return the reviewer's concise report, preserving unresolved findings and
relevant limitations. An incomplete review is not a completed review with no
findings; an empty finding list is not a security guarantee.

Corrections stay within the original authorization and approval requirements.
A requested re-review covers the new snapshot, previous findings and affected
regressions. Apply AISCB's reporting rules to the final delivery.
