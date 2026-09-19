# Requirements

## MODULE-NAMES-001 Name the work each module covers

Source: the user's approved consolidated naming list and correction retaining
supply-chain, followed by explicit approval of these specification files.

Use these IDs and titles:

| ID | Title |
| --- | --- |
| aiscb:web-auth-crypto | Web, Authentication and Cryptography |
| aiscb:data-handling | Data Handling |
| aiscb:secrets-initialization | Secrets and Initialization |
| aiscb:supply-chain | Software Supply Chain |
| aiscb:deployment-environments | Deployment and Environments |
| aiscb:llm-applications | LLM Applications |
| aiscb:llm-agents | LLM Agents |
| aiscb:llm-retrieval-memory | LLM Retrieval and Memory |
| aiscb:mcp-clients-servers | MCP Clients and Servers |

Acceptance: sources, catalog, dependencies, installed discovery, generated
skills, current documentation and requirement source links use these names.
Loaders reject the obsolete IDs. Security rule bodies and IDs remain unchanged
except for references to renamed modules.

## MODULE-NAMES-002 Select modules from concrete tasks

Source: the approved trigger recommendations in this conversation; existing
aiscb-MODULES-001 and the affected modules' rules.

Keep the catalog trigger and module introduction aligned. Explicitly name
cryptography tasks for web-auth-crypto. Scope LLM retrieval and memory to the
system being built, including document selection, context caches and persistent
memory writes; exclude ordinary SQL queries and the assistant's own context.
For deployment-environments, relate mocks and fixtures to activation, exposure
and separation from production. Keep CI component integrity in supply-chain
and CI permissions in deployment-environments; load both when both match.

Acceptance: concrete positive and negative routing scenarios cover those
boundaries. Every installed adapter exposes the descriptions; dependency
closure loads shared prerequisites once. Do not present deterministic delivery
tests as evidence of model selection.

## MODULE-NAMES-003 Preserve delivery and account for context

Source: AGENTS.md build, verification and context-budget requirements, and the
user's request to keep installer, overlays and releases correctly connected.

Generate the complete baseline from the renamed sources. Preserve release
signing and bootstrap verification, organization namespaces and rule mappings.
Retain the baseline version and published assets.

Acceptance: make check passes, including installation and release tests.
Recompute bytes and o200k_base counts for every artifact, update current budget
tables, and record executed tests and any remaining real-client evidence gap.
