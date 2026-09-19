# Data Boundaries Module

`module-id: aiscb:data-boundaries`. Load for request parsing, database access,
files, archives, templates, process execution, deserialization, search,
pagination, uploads, error responses, logging, or external destinations.

## Data Boundaries

- **[aiscb-ERRORS-001] Errors & Logging:** Return no stack traces, internal paths, or raw exceptions. Log security-relevant events with enough context to investigate, but no sensitive data.
- **[aiscb-LIMITS-001] Resource Limits:** Bound input-driven work with timeouts and size or pagination caps; avoid unbounded loops and user-supplied regular expressions.
