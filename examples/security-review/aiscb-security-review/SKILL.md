---
name: aiscb-security-review
description: Arrange a requested independent security review of an implementation change in a fresh context using the same AISCB policy. Return findings to the implementer. Not for ordinary implementation or a repository-wide audit.
---

# Independent AISCB security review

You are the implementer and prepare the review. One reviewer in a fresh context
reports findings. You make corrections and stay responsible for tests and final
review. This workflow adds no application security requirements.

| Status | Meaning |
| --- | --- |
| **prepared** | Handoff is ready; the user must start the reviewer |
| **incomplete** | Review was interrupted or required coverage is missing |
| **completed** | Reviewer covered the handoff scope; this is no security guarantee |

## 1. Prepare the handoff

- [ ] Fill [handoff.md](references/handoff.md) from the authorized task and
      repository evidence.
- [ ] Reuse established requirements and decisions. Do not invent acceptance
      criteria.
- [ ] Ask the user only if missing information prevents the review.
- [ ] Keep the code stable: use a snapshot or pause edits.
- [ ] Use your existing policy source.
- [ ] Do not create commits, install policy or change user settings for the review.

## 2. Start one reviewer

| Situation | Action |
| --- | --- |
| The user asked you to start the review, and the host can start an agent without this conversation | Start one separate agent |
| Otherwise | Give the user the handoff and [reviewer.md](references/reviewer.md) for a new session with the same code and policy. Status: **prepared**. Continue with step 3 when the result returns |

For either path:

- [ ] Give the reviewer the full reviewer instructions and completed handoff.
- [ ] Withhold this conversation and this workflow.
- [ ] Allow scoped read access, the handoff's policy loader command and the
      isolated checks named in the handoff.
- [ ] Deny all other write, shell, network, credential and delegation access.
- [ ] Enforce access through the host. If it cannot, continue and record
      **not enforced** in the handoff. Instructions alone enforce nothing.
- [ ] Run one pass: no nested agents, automatic retries or repair loops.
- [ ] Apply available host time/turn limits and cancellation. Interrupted means
      **incomplete**.

Self-review is not an independent review. Claim a fresh context, enforced
permissions or successful policy loading only when verified.

## 3. Handle the result

- [ ] Show the user the status, unresolved findings, open checks and limitations.
- [ ] Never present **incomplete** as "no findings" or an empty finding list as a
      security guarantee.
- [ ] Keep corrections within the original authorization and approval requirements.
- [ ] Re-review only on request: use the new snapshot, fill **Previous review** in
      the handoff and repeat step 2.
- [ ] Apply AISCB's reporting rules to the final delivery.
