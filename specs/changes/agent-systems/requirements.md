# Requirements

## AGSYS-001 Secure design

Source: the user's request to integrate sufficient secure design principles,
following the proposed trust-boundary, identity, and data-flow design step.

Before security-relevant design or code changes, identify affected assets,
identities, data flows, and trust boundaries; place authorization and validation
at the enforcing boundary and reduce privilege and exposed operations.

Acceptance: an always-on mechanism-level rule covers the affected scope without
requiring an unrelated audit.

## AGSYS-002 Agent systems

Source: the user's approval of the preceding llm-agents proposal and explicit
confirmation that agentic systems must be an additional module.

Provide minimum agency, independently authorized actions, bound approvals,
limited delegation and execution, cancellation, safe retries, and boundary tests.

Acceptance: aiscb:llm-agents declares aiscb:llm-applications as a dependency;
the LLM module retains output handling, sandboxing, and data isolation.

## AGSYS-003 Modular integration

Source: the user's request to implement installation, README, overlay workflow,
and specifications, following the single-package integration proposal.

Use aiscb-core.md and one release-bound namespaced catalog. Install a bounded
loader with complete dependency resolution, or generated complete content.
Organization overlays remain always loaded and may narrow but never relax aiscb.

Acceptance: local installation connects tool entry points, preserves unrelated
instructions, rejects conflicting IDs and invalid releases, verifies content
before returning it, and supports an authenticated organization package.

## AGSYS-004 Evidence and release

Source: repository AGENTS.md, the approved proposal, and the user's instruction
to perform this work on the current feature branch.

Keep aiscb-0.1.16, regenerate outputs and measured sizes, document practical
installation and evidence limits, and prepare bundled changes for signing.

Acceptance: deterministic tests exercise loading and failure boundaries;
make check results and omitted model tests are recorded without bypassing the
maintainer-key release boundary.

## AGSYS-005 Current OWASP review

Source: the user's follow-up request to compare both modules against current
OWASP LLM and Agentic Top 10 lists without requiring one-to-one reproduction.

Document current editions, direct and partial mechanism coverage, and remaining
gaps, distinguishing assistant behavior from controls in systems being built.

Acceptance: `docs/owasp-llm-agentic-review.md` maps all twenty categories to
existing rules with sources and does not introduce unsourced normative rules.
