# Modular default and aiscb status

## Problem

The normal installation supplies every module before routing can save context.
The status question does not distinguish available modules from loaded bodies.

## Goal

Implement the user's approved request: core plus discovery initially, modules
only on demand, for Codex, Claude Code and Copilot; migrate complete installs
without losing user instructions; use `aiscb?` for context-only status.

## Non-goals

No version change, publication, release signing, or relaxation of verification.
No claim that file tests prove model routing or every Copilot surface works.

## Compatibility

Complete installation remains explicit for clients without command execution.
Published bootstrap pins remain unchanged until a separately approved release.
The user's later request for `aiscb?` replaces the earlier pending alias proposal;
this change does not implement its proposed bare `aiscb` alias.
