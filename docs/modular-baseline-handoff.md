# Modular baseline implementation handoff

This document captures the state and design reasoning on branch
`feature/modular-baseline-core` so a fresh session can review, challenge, or
continue the work without reconstructing the approach from the diff.

The branch is an implementation candidate, not a published release. Read and
follow the core, catalog and loader instructions in repository `AGENTS.md` before making
changes. The approved active change specification is
`specs/changes/modular-baseline/`, extended by the approved
`specs/changes/agent-systems/` and `specs/changes/mcp-retrieval/`.

## Current model

There is one modular baseline and an optional generated complete output:

```text
baseline/aiscb-core.md                 always-on normative core
baseline/catalog.json            verified module inventory and triggers
baseline/modules/*.md            thematic normative modules
             |
             | make build-full-baseline
             v
dist/dev/aiscb-VERSION/secure-coding-baseline.md   untracked complete artifact
```

Complete output is no longer committed. Repository instructions read the core
and catalog and use `scripts/repository_policy.py` for verified source loading.
Local projects install the bounded loader; clients without it receive complete output.
It is not a second hand-maintained baseline and
must not be edited directly. `scripts/build_baseline.py --check`, included by
`make check`, rejects stale metadata and stale existing development output;
the check then builds missing development output for tests. Release staging and
signature verification use the separate commands in `docs/releasing.md`.

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
- scoped secure design based on assets, identities, data flows, and trust boundaries;
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
| Always-on core | 7,780 | 1,558 |
| `aiscb:web-auth-crypto` | 5,189 | 1,040 |
| `aiscb:secrets-initialization` | 1,900 | 351 |
| `aiscb:deployment-environments` | 1,659 | 311 |
| `aiscb:llm-applications` | 1,252 | 247 |
| `aiscb:llm-agents` | 2,033 | 401 |
| `aiscb:supply-chain` | 1,173 | 223 |
| `aiscb:data-handling` | 1,720 | 344 |
| `aiscb:llm-retrieval-memory` | 1,666 | 325 |
| `aiscb:mcp-clients-servers` | 2,225 | 415 |
| Complete eager artifact | 26,606 | 5,215 |

The core exceeds its provisional 1,500-token target by 58 tokens; complete
output exceeds its 4,100-token target by 1,115. Further reduction
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
aiscb-core.md
overlay.md
catalog.json                    merged discovery catalog
modules/
  aiscb-web-auth-crypto.md
  aiscb-secrets-initialization.md
  acme-authentication.md
  acme-deployment.md
  ...
```

Logical IDs stay namespaced (`aiscb:web-auth-crypto`, `acme:authentication`). The
builder now rejects namespace and output-path collisions and applies the
main validator to official modules. The project installer wires the shared
catalog and a bounded Python loader directly into each tool's instructions;
generated skill adapters remain available for managed integrations. Blueprints
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
- `scripts/install.py --modular --into PROJECT` installs a verified local
  snapshot and wires Claude Code, Codex, or Copilot instructions. Organization
  packages use the same command with `--organization` and a trusted manifest
  digest. Status, update-by-reinstallation, and guarded uninstall are available.
- `scripts/policy_loader.py` accepts only catalog IDs, verifies the pinned
  package, resolves dependencies, and emits complete bodies and blueprints.
- `aiscb:llm-agents` depends on `aiscb:llm-applications`; it covers minimum
  agency, action authority, bounded execution, and agent-boundary tests.
- `aiscb:llm-retrieval-memory` depends on `aiscb:llm-applications`;
  `aiscb:mcp-clients-servers` depends on `aiscb:data-handling`, not llm-agents.
  File/SSRF mechanisms stay in data-handling and webhook replay in web-auth-crypto.
- `--complete` installs all content through the same local adapter; updates
  refresh every already-managed tool and reject drift before activation.
- `make build-full-baseline` regenerates the complete artifact and source hashes.
- The gateway example emits complete policy because it has no remote loader.

The integration contract is documented in `docs/local-policy-installation.md`.
The 2026 OWASP LLM and Agentic comparison, including remaining content gaps,
is in `docs/owasp-llm-agentic-review.md`. It adds no hidden normative rules.
Modular mode remains an explicit branch trial until actual client routing is
evaluated. Neither file installation nor loader tests prove model compliance.
The signed remote bundle still distributes complete output, with no runtime
fetching of modular helpers. Extending that signed distribution is separate
maintainer release work.

## Verification state

These checks pass on the branch:

```text
python3 scripts/build_baseline.py --check
python3 tests/selfcheck.py
python3 scripts/test_build_baseline.py
python3 scripts/test_install_policy.py
python3 examples/organization-bundle/test_bundle.py
```

The migration separates development checks from the release gate. No root
manifest or signature claims that this working tree is published. Historical
bootstrap fixtures keep the published 0.1.15 path covered. New bundles are
staged under dist/aiscb-VERSION/bundle-N and must pass `make check-release`
after maintainer signing. Actual-client and publication checks remain pending.

No paid model suite was run. New design and agent rules are explicitly recorded
as lacking model evidence in the requirements catalog. Loader and installer
tests cover dependency order, corrupt content, unknown IDs, cycles, namespace
collisions, preservation, uninstall, and organization integration; these are
not real-client routing or security-behavior evidence.

## Safe continuation order

1. Review the core/module boundary and the module triggers, with particular
   attention to false negatives caused by semantic selection.
2. Evaluate actual client routing and context budgets before making modular
   loading the default or expanding the signed remote distribution.
3. If sources change, run `make build-full-baseline`, recompute
   the `o200k_base` measurements, update README, and run deterministic checks.
4. When the version is explicitly approved, follow `docs/releasing.md`: stage,
   sign and verify exact assets, publish an immutable release, then transition
   the bootstrap and complete README Quick start. Do not commit dist files.
5. Run `make check` and the separate signed release gate. Run the model suite only
   with an explicit decision to spend that budget and record the evidence.
6. Mark the remaining change task complete and archive the change specification
   only after the release checks pass.

Do not make the release tests green by weakening signature verification,
reusing or moving an existing tag, fabricating a signature, or pointing the
Quick start at an intermediate commit.
