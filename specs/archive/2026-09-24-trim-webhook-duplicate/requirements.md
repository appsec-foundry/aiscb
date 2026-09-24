# Requirements

## TRIM-001 Webhook signature verification is stated once

Source: the user's explicit request in this conversation to remove duplicated
rule text after a review of every module, together with the verification that
`aiscb-WEBHOOK-001` states the signature check the clause repeats.

An assistant verifies inbound webhook signatures before acting, as
`aiscb-WEBHOOK-001` requires; `aiscb-MECHANISMS-001` no longer repeats it.

Acceptance: `aiscb-MECHANISMS-001` ends with the constant-time comparison of
secrets, tokens, and MACs; `aiscb-WEBHOOK-001` is unchanged and remains the
only rule requiring webhook signature verification.

Example: a webhook handler that acts on an unverified payload still violates
the module, through `aiscb-WEBHOOK-001`.
