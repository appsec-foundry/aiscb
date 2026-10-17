# Scope module selection to affected work

## Problem

The routing rule does not explicitly distinguish affected interfaces from
technologies merely present elsewhere in an application. Its unqualified
uncertainty clause can encourage unrelated module loads. The reported process
change is a motivating example, not proof of an incorrect selection.

## Goal

Clarify that semantic matching covers the task and affected interfaces,
including indirect effects, and scope uncertainty to that applicability.
Exercise an isolated process change in a project that also contains HTTP code.

## Non-goals

No module trigger, dependency, path matching, security mechanism, version,
installed policy, or release change. No claim that deterministic tests prove
model selection behavior.

## Compatibility

Existing affected matches remain required, including indirect effects. Explicit
path matches still add modules and dependencies still load through the loader.
