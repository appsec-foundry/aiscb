# Requirements

## MOD-001 Always-on core

Source: the user's request to create the proposed short always-on baseline.

Provide a compact normative core that carries release identity, module routing,
scope behavior, the universal security floor, decision behavior, and completion
review needed even when no module is selected.

Acceptance: `baseline/core.md` is independently readable, declares
`aiscb-0.1.16`, names the module-selection mechanism, and its measured token
count is lower than the complete eager artifact.

## MOD-002 Flat module plane

Source: the user's clarification that the overlay and aiscb modules should work
on one level.

Represent aiscb and organization modules in one logical flat, namespaced
catalog selected in one pass; namespaces identify provenance without creating
separate routing hierarchies.

Acceptance: the catalog uses fully qualified `aiscb:*` IDs, the core requires
one selection pass across every configured namespace, and documentation shows
an aiscb and organization module selected together.

## MOD-003 Thematic modules

Source: the user's request to create the modules described by the proposal in
`docs/modular-baseline-proposal.md`.

Place detailed portable requirements in official modules for web and
authentication, data boundaries, secrets and bootstrap, supply chain,
deployment and runtime, and LLM-powered features.

Acceptance: every module is a complete cataloged artifact with semantic
triggers, and every current normative rule is present in the core or exactly
one module.

## MOD-004 Organization overlay compatibility

Source: the user's request that an organization overlay continue to work with
the modular baseline.

Keep the overlay always loaded but outside the module plane. Let it register a
verified organization namespace whose modules are selected with aiscb modules;
organization rules may add or narrow requirements but never relax aiscb.

Acceptance: the organization guidance and example describe one merged catalog,
one loader contract, namespaced modules, pinned compatible releases, and
blueprints as module dependencies rather than independently selected policy.

## MOD-005 Eager compatibility artifact

Source: the compatibility path in the user-approved modular baseline proposal.

Generate `secure-coding-baseline.md` deterministically from the core and every
official module for existing clients and any client without reliable on-demand
loading.

Acceptance: a deterministic check proves the eager artifact is current, has one
baseline ID, and contains every normative rule ID exactly once.

## MOD-006 Verified modular release

Source: the repository's existing verified distribution requirements and the
user-approved modular architecture.

Pin the core, catalog, and every official module by size and SHA-256 in a
machine-readable manifest or catalog, reject malformed or inconsistent module
metadata, and keep one compatible release throughout a session.

Acceptance: local checks reject missing, altered, duplicated, unknown,
cross-release, or unlisted modular artifacts and reject a generated eager file
that differs from its normative sources.

## MOD-007 Exact release identity

Source: the user's explicit approval of `aiscb-0.1.16` after requesting that
the change remain in the `0.1.x` series.

The core, eager artifact, README, examples, and release metadata must identify
this baseline as `aiscb-0.1.16`.

Acceptance: repository checks find exactly the approved ID everywhere the
current release must be named and no stale `aiscb-0.1.15` compatibility claim.

## MOD-008 Measured and tested delivery

Source: the repository's existing size, testing, and release requirements.

Measure the core and eager artifacts, test deterministic assembly and routing
metadata, run `make check`, and record which paid model cases were or were not
run. Prepare changed bundled files for maintainer signing without fabricating a
signature or publishing a release.

Acceptance: README measurements match the files, deterministic checks pass,
the task record names model-test evidence, and release work stops at the
maintainer-key boundary.
