# Require concrete module matches

## Problem

Broad semantic and uncertainty clauses encourage modules to load for remote
possibilities or the assistant's routine tool calls. Rechecking can also cause
full bodies to load again while they remain in context. The user's score-runtime
example motivates the change; it does not prove every reported load was wrong.

## Goal

Tie semantic selection to concrete planned changes and affected interfaces,
bound uncertainty, reuse loaded text, and distinguish loading from justification
for additional measures. Clarify the supply-chain trigger for routine commands
while keeping new external dependencies and tools subject to verification.

## Non-goals

No security-mechanism, dependency-graph, path-trigger, loader, baseline-version,
installed-policy or published-release changes. No claim that deterministic
checks establish model compliance.

## Compatibility

Required direct and indirect matches and explicit path matches remain required.
Missing required text must still load, including after context loss; unavailable
policy still stops affected work. External dependency verification and the
assistant's own execution safeguards remain applicable.
