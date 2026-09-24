# Requirements

## TRIM-001 The routing paragraph states only what the initial context holds

Source: the user's explicit request in this conversation to shorten the core
where it repeats itself, after a review that found the paragraph under
`Module Routing` restating `aiscb-MODULES-001` and the adapter text that
`scripts/install_policy.py` appends; the recorded requirement for
`aiscb-MODULES-001` in `specs/requirements.md` already carries the initial
context and the explicit complete loading.

An assistant starts with this core, the adapter's discovery and loader
instructions, and supplied always-on organization overlays in context, and
loads module bodies only before affected work.

Acceptance: the paragraph under `Module Routing` is one sentence naming the
initial context and the on-demand loading of module bodies, and repeats nothing
from `aiscb-MODULES-001` or the adapter text. In a fresh modular session,
`aiscb?` reports no loaded modules.

Example: a fresh session in a project with a modular installation reports the
core, the catalog entries, and no loaded module bodies; the assistant loads
`aiscb:web-auth-crypto` when it is about to implement a login, not at session
start.
