# Split aiscb into an always-on core and flat modules

## Problem

Every session currently loads the complete baseline, including detailed web,
authentication, deployment, dependency, and LLM rules that many tasks do not
need. An organization overlay adds its own lazy-loaded packs, but aiscb itself
still consumes roughly four thousand tokens before those packs are considered.

## Goal

Publish a short always-on aiscb core and official thematic modules selected
with organization modules in one flat, namespaced catalog and one routing pass.
Keep a complete eager artifact for clients that cannot load modules reliably.
Use the exact user-approved release ID `aiscb-0.1.16`.

## Non-goals

Do not weaken or remove the current security requirements. Do not make model
selection an enforcement boundary, invent organization-specific values, or
silently omit modules on clients without a verified loading mechanism. Do not
publish, tag, or sign the release without the maintainer's release key.

## Compatibility

`secure-coding-baseline.md` remains the complete file consumed by existing
installations and model tests. Modular clients load the core, overlay, and one
merged discovery catalog, then select fully qualified `aiscb:*` and
organization modules together. The repository's normative source layout,
validation, documentation, bundle metadata, and release process change; the
existing rule IDs remain stable where their behavior remains intact.
