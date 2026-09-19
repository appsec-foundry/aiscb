# LLM-Powered Features Module

`module-id: aiscb:llm-features`. Load for prompts, retrieval, memory, model
output, agents, tool calls, generated code, or model-selected resources.

## LLM-Powered Features

- **[aiscb-LLM-001] LLM-Powered Features:** Treat prompts, model and tool outputs, retrieved content, and memory as untrusted; never let them override policy, authorization, or task boundaries. Before downstream use, validate structured output deterministically against strict schemas and value allow-lists, rejecting unknown or ambiguous fields and values; encode it for context or sanitize rendered markup with a maintained allow-list sanitizer. Keep model values separate from instructions and executable text through structured or parameterized sink APIs and allow-listed operations; never pass them directly to an interpreter. Confine intended generated-code execution to a filesystem-, network-, time-, and resource-restricted sandbox. Isolate data and memory across tenants and review against the current OWASP Top 10 for LLM Applications. Load agent-systems when designing or changing model-directed actions.
