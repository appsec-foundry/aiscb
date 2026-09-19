# Modular repository and generated distribution

## Approved scope

Source: the user's approval to implement modular repository loading, versioned
untracked dist output, corresponding installation/release checks, and the
specification-first project/overlay workflow. No normative security rule or
baseline version changes in this step; under specs/README.md this is a tooling
and workflow change, not a new baseline change directory.

## Requirements and acceptance

- Repository instructions reference the core and catalog; one verified loader
  resolves selected IDs and dependencies without requiring generated output.
  Claude imports repository instructions and core, never complete output.
- Complete output is generated under dist/dev/aiscb-VERSION by default; release
  staging uses dist/aiscb-VERSION/bundle-N and refuses overwrite. Neither is
  checked into Git. Names inside the bundle remain stable.
- Source checks work from a fresh checkout. Tests needing complete output build
  it first. Published-artifact verification remains a separate mandatory release
  gate, with signature and exact-byte checks, not a skipped development test.
- Future releases distribute signed assets rather than require generated files
  in a Git tree. Existing published bootstrap pins remain unchanged until an
  approved release is actually available. Old updaters may require a one-time
  current Quick start; never downgrade verification to hide incompatibility.
- Project/organization workflow templates require requirements and acceptance
  criteria, explicit approval, implementation, and verification. Small changes
  may use a short specification; changed scope requires renewed approval.

## Verification

Exercise fresh-checkout loading, unknown IDs, corrupt metadata, dependency
closure, reproducible output, immutable release staging, signed-manifest failure,
asset-download boundaries, local install formats and inherited-policy limits.
Actual client routing and production rollout remain separately recorded evidence.

## Implemented evidence

The repository loader is independent of dist output. Nine dedicated tests
cover clean-source loading, stale hashes, bounded IDs, all three repository
entry points, immutable staging, asset fallback, generated bootstrap execution,
and a real signature with a disposable test-only key. Eighteen local-policy
tests and the existing organization adapter/gateway tests remain in make check.
The version-hook subprocess test now runs from an actual temporary installation,
not by assuming a generated file in the repository root.

Official Claude, Copilot and Codex documentation was reviewed. Claude's old
"never reads AGENTS.md" claim was corrected; Copilot's obsolete full-file symlink
was replaced. The local ignored Claude full-file symlink was removed as well.
No live client, production gateway, paid model run, or published release was used.
See docs/agent-integration-verification.md for the remaining acceptance matrix.
