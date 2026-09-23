# Reduce unnecessary baseline interaction

## Problem

The core does not distinguish consent to the same decision from unrelated prior
consent. Routine compliant work requires attribution. The data-handling trigger
can be mistaken for every source or documentation edit.

## Goal

Implement the user's approved recommendations after rechecking their sources:
scope confirmation, reserve attribution for refusals, blockers and confirmations,
and clarify ordinary file editing without excluding actual data-handling work.

## Non-goals

No weaker security controls, report-rule rewrite, supply-chain exclusion,
version change, release, or claim that a shorter core improves model behavior.
The full/modular model comparison remains an evidence gap, not a proven benefit.

## Compatibility

Keep rule IDs and aiscb-0.1.18. Update behavioral checks that required routine
attribution; retain their security checks. Historical model results describe the
previous wording and do not validate this revision.
