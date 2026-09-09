# Move deployment detail out of the baseline

## Problem

The TLS bullet of `aiscb-DEFAULTS-001` and the bootstrap bullet of
`aiscb-SECRETS-001` describe how a deployment is wired: redirect-only
plain-HTTP listeners, proxy trust, cookie and HSTS settings per bind, and
container stdout as a log channel. `AGENTS.md` says the baseline governs how
an assistant behaves and is not a security specification for the application
being built. The organization guide already has the place for such detail: a
requirement pack loaded only for matching work.

## Goal

Keep the assistant-behavior core in the baseline: TLS for everything that
leaves the machine, loopback by default, TLS configuration required for a
wider bind with startup failing without it, and a first admin credential from
configuration or a one-time operator-only disclosure. Move the deployment
detail into a deployment pack in the organization bundle example.

## Non-goals

No ID moves or retires. The browser and CORS bullets stay as they are. The
organization guide under `docs/` is not edited in this change because another
session is editing it; the pack is linked from the example README only.

## Compatibility

An assistant no longer reads proxy trust, redirect-only listeners, or the
container-stdout sentence in the baseline. Organizations that need them take
the example pack. Model cases that grade TLS and first-credential behavior
grade the retained core; they were not rerun.
