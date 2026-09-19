# Requirements

## MCPRET-001 MCP-specific integration

Source: user's approval of the preceding MCP assessment, informed by the
official MCP 2026-07-28 authorization and security best-practices documents.

Distinguish HTTP authorization from local stdio process trust. Bind credentials
and state to their intended resource and identity, prevent token passthrough
and proxy consent confusion, constrain discovery destinations and local starts.

Acceptance: mcp-integrations has explicit implementation/configuration triggers,
no unconditional agent dependency, and negative boundary-test instructions.

## MCPRET-002 Retrieval and memory

Source: user's approval of the assessment identifying missing retrieval
authorization, provenance, and controlled memory writes.

Apply identity/resource permissions before retrieved content reaches the model;
preserve provenance and authorize persistent writes independently of content.

Acceptance: retrieval-memory depends on llm-features, covers caches and revoked
access, and requires cross-identity and poisoning boundary tests.

## MCPRET-003 Existing-module gaps

Source: user's approval to close file/SSRF gaps in data-boundaries and webhook
gaps in web-auth rather than add broad overlapping modules.

Constrain file handling, decompression and outbound destinations; prevent
replayed webhook side effects using provider verification and deduplication.

Acceptance: mechanisms and negative tests live in existing modules, with no
duplicate normative copies in MCP or documentation.

## MCPRET-004 Integration and evidence

Source: user's explicit request to verify deployment, rollout documentation,
and installer, plus AGENTS.md generation, measurement, and release rules.

Ship new modules through catalog-driven local and organization installation
and complete output. Preserve user instructions, avoid mixed tool releases,
and distinguish local verified snapshots from signed remote distribution.

Acceptance: deterministic tests cover new module dependency/loading boundaries,
all tool entry points, organization packaging, complete output, update and
failure paths; measurements and make-check results are recorded honestly.
