# Requirements

## REUSE-004 Deliver the complete baseline in five bounded parts

Source: the user's explicit approval of the five-part loader adjustment in
this conversation, 2026-10-18, after the larger baseline exceeded four parts.

Increase the legacy dynamic loader to five 7,100-character parts. Keep installer,
hook output, fallback commands, and tests consistent. Recognize only exact managed
four-part installations during transition; preserve unrelated settings and reject
modified loader or hook content. Retain fail-closed capacity and output bounds.

Acceptance: All baseline bytes arrive in five bounded parts, including through
the documented fallback. Exact capacity succeeds and one extra character fails
closed. Existing managed four-part installations can be updated or migrated;
customized commands and loaders are not silently replaced.

## REUSE-003 Limit application controls to application-development tasks

Source: the user's approval of the scope proposal and explicit selection of
"Eigenständige Cloud- und Betriebsaufgaben ausnehmen" in this conversation,
2026-10-18.

Apply application-security controls to designing, implementing, testing, or
reviewing application behavior, including build and deployment configuration
within that task. Exclude standalone cloud administration, operations, and
documentation. Determine applicability from affected data flows, recipients,
and trust boundaries, not assistant file access or tool use alone. Keep the
assistant's own secret, untrusted-instruction, permission, and tool-execution
safeguards applicable throughout.

Acceptance: A standalone AWS/Terraform configuration edit does not trigger
application controls merely because the repository also has application code.
A requested application change still loads its applicable modules, including
for application build/deployment work. A documentation-only edit does not turn
into application hardening; protected assistant boundaries still apply.

## REUSE-001 Trace and reuse effective controls

Source: the user's approved OM-001 wording in this conversation, 2026-10-18;
existing baseline/aiscb-core.md, aiscb-OM-001.

Trace affected data flows through existing controls and reuse those enforcing
the required protection. Before adding a security mechanism, identify the
uncovered boundary or failure it addresses; do not duplicate effective protection
on that path.

Acceptance: A new endpoint uses existing identity resolution and effective
ownership protection. A path not covered by those controls gains the required
protection; the mere existence of a helper elsewhere does not establish coverage.

## REUSE-002 Bound resource consumption at the consuming operation

Source: the user's approved LIMITS-001 wording in this conversation, 2026-10-18;
existing baseline/modules/aiscb-data-handling.md, aiscb-LIMITS-001.

Bound resource consumption driven by untrusted input with timeouts, size limits,
or pagination at the consuming operation, reusing effective existing bounds.
Keep the requirement to avoid unbounded loops and user-supplied regular expressions.

Acceptance: Search limits bound database result retrieval rather than only
truncating a fully materialized result. Client-provided limits cannot bypass
the bound; effective bounds already on the path are reused.
