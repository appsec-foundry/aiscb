# Remove the webhook clause that WEBHOOK-001 already states

## Problem

`aiscb-MECHANISMS-001` in `baseline/modules/aiscb-cryptography.md` ends with
"and verify inbound webhook signatures before acting". `aiscb-WEBHOOK-001`,
the next rule in the same module, opens with "Verify the provider's signature
over its prescribed bytes before processing" and goes on to freshness and
replay. The two rules always load together, so the clause states a duty twice.

## Goal

State the duty once, in `aiscb-WEBHOOK-001`, and end `aiscb-MECHANISMS-001`
with the constant-time comparison.

## Non-goals

No change to what either rule requires. No change to the module trigger, which
keeps "webhooks" so the module loads for webhook work. No new version or
baseline ID.

## Compatibility

Consumers that quoted the removed clause find its content, stated more
precisely, in `aiscb-WEBHOOK-001`. The catalog summary for `aiscb:cryptography`
in the README still says "verify signed webhooks", which remains true.
