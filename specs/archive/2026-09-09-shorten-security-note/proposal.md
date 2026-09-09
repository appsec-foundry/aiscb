# Shorten the security note heading

## Problem

The risk heading reads `Security note (aiscb baseline)`. The parenthesis names
the baseline twice: `aiscb` is the baseline, so `aiscb baseline` doubles the
word without adding information. The heading appears four times in the baseline
and once in every reply that carries a risk.

## Goal

Use `Security note (aiscb)` as the single heading for the risk note in the
baseline, harness, tests, and documentation, keeping the attribution to the
baseline that the heading provides.

## Non-goals

Do not change when a note is written, what it contains, or any other rule
behavior. Do not publish a release bundle for this change.

## Compatibility

Replies carry the new heading. The harness counts notes by matching the heading
text, so it must match the new spelling. Consumers that look for the old heading
must adopt the new one. Archived change records keep the heading that described
the repository state at their time.
