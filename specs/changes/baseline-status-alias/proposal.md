# Baseline status aliases

## Problem

The current baseline defines `baseline?` as its status question. Users also
want to ask `aiscb?` in Codex or another assistant to see whether aiscb is loaded.

## Goal

Prepare `aiscb` and `aiscb?` as additional triggers for the existing status
answer. The user asked to collect this with other possible changes before
implementing or releasing the next version.

## Non-goals

No core, module, installer, or released-bundle changes yet. No new version
number, release, tool-specific command, or automatic loading. This status
answer does not prove that the assistant follows every rule.

## Compatibility

Keep `baseline?` and its existing response unchanged. Published 0.1.16 assets
stay immutable. The next version and implementation scope require approval
once the pending changes have been reviewed together.
