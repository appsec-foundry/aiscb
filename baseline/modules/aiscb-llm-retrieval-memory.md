# LLM Retrieval and Memory Module

`module-id: aiscb:llm-retrieval-memory`. Load for: Designing or changing retrieval or
persistent memory in an LLM application: selecting documents for model answers, RAG,
vector stores, context caches, or creating, replacing and deleting model/agent memories;
not ordinary database queries or the coding assistant's own context.
Requires `aiscb:llm-applications`.

## LLM Retrieval and Memory

- **[aiscb-RETRIEVAL-001] Authorized Retrieval:** Enforce current identity, tenant, and source-resource permissions in retrieval filters before content reaches the model or caller; a namespace or similarity score is not authorization. Apply the same permissions to cached context and derived chunks, and invalidate or recheck them after access revocation. Retain source identity and provenance through ingestion and retrieval; retrieved text must not define its own permissions or trust level.
- **[aiscb-MEMORY-001] Controlled Memory Writes:** Authorize persistent memory creation, replacement, and deletion outside the model against the acting identity and memory scope. Separate untrusted retrieved/user content from policy and trusted configuration; never promote it through summarization or persistence. Record write provenance and support removal of poisoned entries and affected derived caches.
- **[aiscb-RETRIEVALTESTS-001] Retrieval Boundary Tests:** Test same-tenant unauthorized documents, cross-tenant retrieval and cache reuse, revoked access, forged provenance or permissions, and content-induced unauthorized memory writes. Verify denied content never enters the model context, not merely that the final answer hides it.
