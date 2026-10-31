---
name: aiscb-security-review
description: Arrange an independent AISCB security review of a specified implementation change in a fresh context, using the existing baseline and loader. Return actionable findings for the implementer. Use for a requested independent security review, not ordinary implementation or a repository-wide audit.
---

# Independent AISCB security review

Keep AISCB active for the implementer. This optional workflow adds a reviewer;
it neither replaces the implementer's tests and final review nor defines new
application security requirements. The reviewer reports findings and does not
patch the implementation.

## Prepare the handoff

Read [handoff.md](references/handoff.md) and fill its fields from the authorized
task and repository evidence. Reuse established requirements and decisions;
ask only for missing information that prevents a meaningful scoped review.
Do not invent acceptance criteria or treat an implementer's summary as proof.

Identify both the code snapshot and policy snapshot. Include base/head revisions
for committed changes. For uncommitted work, identify the base, staged and
unstaged changes, relevant untracked files and their content digests; arrange
a stable snapshot or pause edits during review. Do not create commits, install
policy, or change user settings just to arrange the review.

Use the implementer's existing policy source: installed release digest and
loader, or reviewed repository revision and catalog plus repository loader.
Include organization overlays and their identities. A version label alone
does not identify a development snapshot. Do not silently substitute a newer
release or a reviewer machine's user-level baseline. Resolve conflicting active
policy before claiming that the same requirements were used.

## Start one reviewer

Read [reviewer.md](references/reviewer.md). Give its complete contents and the
completed handoff to one fresh reviewer context, without the implementation
conversation or this coordinator workflow. The reviewer must load the trusted
project instructions and pinned AISCB core, discovery and relevant modules;
a fresh conversation is not a policy-free conversation.

Use a separate-agent facility only when available, authorized, and able to start
without inherited conversation. Request read access to the scoped snapshot and
policy loader. Use host-enforced read-only access where supported. This skill
is an instruction, not a filesystem sandbox. Do not grant general write, shell,
network, credential, or delegation access merely to make a review work.

If that facility is unavailable, return the completed handoff and reviewer
instructions for a new user-started session with access to the same snapshots.
Label this as prepared, not completed. Reading the review instructions in the
implementation conversation is self-review, not independent review. Do not
claim a new context, enforcement, or successful policy loading without evidence.

One invocation starts at most one reviewer pass, with no nested delegation,
automatic repair loop, or automatic retries. Apply the host's finite turn/time
budget and cancellation where available; record interruption as incomplete.
Do not expand this into an unattended model campaign.

## Return the result

Return the review's snapshot identity, findings, relevant verification gaps and
completion status. Keep quoted code and test output minimal and free of secrets.
An empty finding list is not a security guarantee. Preserve unresolved findings
and distinguish incomplete review from completed review with no material finding.

The implementer handles corrections within the original authorization. Findings
do not authorize a broader audit or override existing approval requirements.
After corrections, a requested re-review identifies the new snapshot and checks
the affected findings and regressions. A changed snapshot is not covered by an
earlier result. Apply the baseline's reporting contract to the final delivery;
do not manufacture a Security note merely because a review took place.
