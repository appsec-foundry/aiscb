# Modular baseline implementation handoff

This document captures the state and design reasoning on branch
`feature/modular-baseline-core` so a fresh session can review, challenge, or
continue the work without reconstructing the approach from the diff.

The branch is an implementation candidate, not a published release. Read and
follow `secure-coding-baseline.md` and the repository `AGENTS.md` before making
changes. The approved active change specification is
`specs/changes/modular-baseline/`.

## Current model

There are two delivery profiles built from one normative source set:

```text
baseline/core.md                 always-on normative core
baseline/catalog.json            verified module inventory and triggers
baseline/modules/*.md            thematic normative modules
             |
             | scripts/build_baseline.py --write
             v
secure-coding-baseline.md        tracked eager artifact: core + every module
```

The root `secure-coding-baseline.md` is deliberately still committed. Existing
installers and clients have no reliable generic module loader, so they continue
to receive one complete file. It is not a second hand-maintained baseline and
must not be edited directly. `scripts/build_baseline.py --check`, included by
`make check`, rejects any difference between it and the modular sources.

The modular profile always loads the core and exposes the catalog's semantic
triggers at startup. Before affected design or code, `aiscb-MODULES-001`
selects every matching module. A file on disk or a catalog entry alone is not a
loading mechanism: the adapter must expose a bounded loader and must make the
discovery metadata visible before selection is needed. If that cannot be
proved, the eager artifact is the safe profile.

## Why the core has this content

The core contains only behavior needed before a topic can be classified or at
the completion of any task:

- release identity and module routing;
- existing, greenfield, mixed-request, override, and design-decision behavior;
- attribution;
- the universal floor for authorization, untrusted input, secrets, preserving
  controls, agentic input, and secure defaults;
- generic security-test behavior;
- review and reporting.

The detailed `Security note (aiscb)` mechanism remains in the core by design.
It is security-critical and cross-cutting: an assistant must know when to emit
a note even when no thematic module matched. Its material-risk threshold,
qualifying situations, exclusions, ordering, and concise output format were not
moved into an optional module. Core size was reduced around that mechanism,
not by weakening it.

Current `o200k_base` measurements are:

| Artifact | Bytes | Tokens |
| --- | ---: | ---: |
| Always-on core | 7,432 | 1,500 |
| `aiscb:web-auth` | 4,647 | 944 |
| `aiscb:secrets-bootstrap` | 1,885 | 349 |
| `aiscb:deployment-runtime` | 1,562 | 294 |
| `aiscb:llm-features` | 1,212 | 236 |
| `aiscb:supply-chain` | 1,155 | 221 |
| `aiscb:data-boundaries` | 631 | 139 |
| Complete eager artifact | 18,530 | 3,683 |

The core is exactly at its provisional 1,500-token budget. Further reduction
should be evaluated against lost always-on behavior, not treated as an
automatic goal. In particular, do not shorten the Security-note contract merely
to improve the headline number.

## Organization overlay integration

The overlay remains always loaded next to the core, but it is not a second
module router. It establishes organization identity and grants authority to a
verified organization namespace. The core performs one selection pass across
all configured namespaces and supplies common reload and failure behavior.

The source trees may remain separated for ownership, but a built organization
release presents one logical and physical module plane:

```text
core.md
overlay.md
catalog.json                    merged discovery catalog
modules/
  aiscb-web-auth.md
  aiscb-secrets-bootstrap.md
  acme-authentication.md
  acme-deployment.md
  ...
```

Logical IDs stay namespaced (`aiscb:web-auth`, `acme:authentication`) so
provenance and collision handling remain explicit. The organization-bundle
example generates the same combined skill surface for Claude Code, Codex, and
Copilot and tests that official and organization modules share it. Blueprints
are dependencies of organization modules, not independently selected policy.

Organization modules may add requirements or narrow named aiscb rules. They
may not relax aiscb, expand the user's task, or change permissions. Missing,
invalid, incompatible, or conflicting required content stops only the affected
work.

## What is integrated today

- The modular normative source tree, catalog, validation, deterministic eager
  builder, mutation tests, requirement catalog, and case mappings exist.
- The organization-bundle example consumes the modular source tree, verifies
  core and module hashes, merges the catalogs, creates a flat release, and
  generates tool adapters and skills.
- The standard repository installer still distributes the eager artifact. It
  does not yet offer a generic modular installation mode.
- There is no dedicated `make build-baseline` convenience target. The current
  write command is `python3 scripts/build_baseline.py --write`; `make check`
  validates without rewriting.

The last two items are deliberate open product decisions, not hidden behavior.
A generic modular installer has to define supported client discovery and
loading mechanisms; merely copying `core.md` and module files would create a
false assurance that modules are active.

## Verification state

These checks pass on the branch:

```text
python3 scripts/build_baseline.py --check
python3 tests/selfcheck.py
python3 scripts/test_build_baseline.py
python3 examples/organization-bundle/test_bundle.py
```

`make check` reaches the install/release tests after all preceding checks pass.
Five release tests then fail for one expected reason: `bundle.json` describes
the changed 0.1.16 bundled files, while `bundle.json.sig`, `setup.sh`, and the
README Quick start still authenticate the published 0.1.15 bundle. The private
release key must never enter the repository, CI, or an assistant's context, so
the branch intentionally stops here.

No paid model suite was run. This refactor touches all rule domains, making the
honest affected set the full suite (currently 162 agent turns plus judge calls).
Case metadata was updated and deterministic checks pass, but that is not model
evidence.

## Safe continuation order

1. Review the core/module boundary and the module triggers, with particular
   attention to false negatives caused by semantic selection.
2. Decide whether 1,500 always-on tokens is the intended budget and whether the
   standard installer should remain eager-only or gain an explicit modular
   mode for named supported clients.
3. If sources change, run `python3 scripts/build_baseline.py --write`, recompute
   the `o200k_base` measurements, update README, and run deterministic checks.
4. When the content is approved, a maintainer follows `docs/releasing.md` with
   the private key: sign the bundle, commit and verify it, create a new immutable
   bundle tag, then update `setup.sh` hashes and the complete README Quick start
   in the documented two-commit sequence.
5. Run `make check` after signing/bootstrap updates. Run the model suite only
   with an explicit decision to spend that budget and record the evidence.
6. Mark the remaining change task complete and archive the change specification
   only after the release checks pass.

Do not make the release tests green by weakening signature verification,
reusing or moving an existing tag, fabricating a signature, or pointing the
Quick start at an intermediate commit.
