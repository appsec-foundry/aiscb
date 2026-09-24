# Data Handling Module

`module-id: aiscb:data-handling`. Load for request parsing, database access, files, archives, templates, process execution, deserialization, search, pagination, uploads, error responses, logging, or external destinations. Reading or editing source or documentation alone does not trigger this module; changes to their parsing or processing do. Handling untrusted files, executing processes, and contacting external destinations remain in scope.

## Data Handling

- **[aiscb-ERRORS-001] Errors & Logging:** Return no stack traces, internal paths, or raw exceptions. Log security-relevant events with enough context to investigate, but no sensitive data.
- **[aiscb-LIMITS-001] Resource Limits:** Bound input-driven work with timeouts and size or pagination caps; avoid unbounded loops and user-supplied regular expressions.
- **[aiscb-FILES-001] Untrusted Files:** Allow only required file types and validate content rather than trusting names or MIME headers. Use server-generated storage names outside executable/public paths and authorize downloads; serve untrusted active content as attachments or from an isolated origin. Confine parsing and extraction, reject escaping paths and links, and cap expanded bytes, entry counts, nesting, and processing time. Test traversal, misleading types, unauthorized downloads, and decompression exhaustion.
- **[aiscb-EGRESS-001] Outbound Requests:** For input-influenced destinations, allow only required schemes, hosts, ports, and network ranges. Validate resolved addresses at connection time, including IPv6; block metadata and unintended internal/loopback access. Disable redirects or revalidate every hop and never forward credentials to a different origin. Use a maintained URL parser and connection-bound checks or an enforcing egress proxy, not a DNS check separated from use. Test redirects, alternate address encodings, and DNS changes against the enforced boundary.
