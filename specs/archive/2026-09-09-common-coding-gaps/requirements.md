# Requirements

## GAP-BIND-001 Bind and expose only allow-listed fields

Source: the user's request in this conversation to build the three gaps the
spec review identified into the baseline.

Under `aiscb-INPUT-001`, an assistant binds request data only to fields it has
explicitly allow-listed and returns only the fields the caller needs, instead
of mapping a request onto every writable model field or returning whole
records.

Acceptance: a request carrying a field the caller may not write, such as a
role or owner, cannot set it, and a response contains no field the caller does
not need.

## GAP-COMPARE-001 Constant-time comparison and signed callbacks

Source: the user's request in this conversation.

Under `aiscb-MECHANISMS-001`, an assistant compares secrets, tokens, and MACs
in constant time and verifies the signature of an inbound webhook or callback
before acting on it.

Acceptance: a secret comparison uses the platform's constant-time primitive,
and an unsigned or mis-signed callback is rejected before any side effect.

## GAP-PRIV-001 CI and container least privilege

Source: the user's request in this conversation; `aiscb-DEFAULTS-001` already
requires least privilege and a separate identity for privileged operations.

Under `aiscb-DEFAULTS-001`, an assistant gives CI jobs read-only tokens by
default, never runs untrusted pull-request code in a workflow that holds write
access or secrets, and runs containers as a non-root user.

Acceptance: a generated workflow declares read-only permissions unless a step
needs more, no workflow checks out and runs pull-request code with write access
or secrets, and a generated container image sets a non-root user.
