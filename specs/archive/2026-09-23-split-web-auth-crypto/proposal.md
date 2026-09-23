# Split web, authentication and cryptography

## Problem

The combined module loads unrelated rules for narrowly scoped tasks.

## Goal

Implement the user-approved three-module candidate, preserve security clauses,
and verify module delivery and discovery overhead with focused checks.

## Non-goals

No new security requirements, core change, version bump, release or broad model matrix.

## Compatibility

Replace aiscb:web-auth-crypto with aiscb:web, aiscb:authentication and
aiscb:cryptography. Authentication requires cryptography and data-handling; cryptography requires
secrets-initialization, following the user-requested fix for observed omissions. Existing immutable
installed snapshots remain intact; new catalogs reject the retired module ID.
Split MECHANISMS and WEBTESTS into separately tracked groups; update references.
