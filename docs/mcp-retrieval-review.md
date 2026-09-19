# MCP and retrieval integration review

Reviewed 2026-09-19. This records scope and evidence, not additional rules.

## Boundaries and sources

MCP-specific rules distinguish HTTP resource authorization from local process
execution. Credential audiences and resource binding follow
[MCP authorization](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization).
Proxy consent, discovery destinations, owner-bound handles and local server
configuration were checked against the official
[security guidance](https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/security_best_practices).
HTTP Origin handling was checked against
[Streamable HTTP](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http).
Implementations must follow their supported protocol revision; this module is
not a complete protocol-conformance checklist. It does not require HTTP OAuth
for stdio or agent autonomy for every MCP connection.

General file and outbound-request mechanisms remain in data-handling, informed
by the [OWASP file-upload guidance](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html)
and [SSRF guidance](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html).
Webhook replay stays with web authentication rather than MCP. The
[OWASP alignment review](owasp-llm-agentic-review.md) records the retrieval and
memory gaps closed, along with remaining non-goals.

## Integration decision

The catalog drives complete assembly, local snapshots, organization skills,
and the gateway's complete block. There is no separate module copy list in the
installer. MCP requires data-handling; llm-retrieval-memory requires llm-applications.
Other semantic matches still apply. Package delivery is not model selection.

The installer now offers explicit `--complete` as well as `--modular`; omitting
the latter was ambiguous for official-only installations. Updating any managed
tool also refreshes the others, preventing an installation record that describes
one release while another tool still loads the previous one. Existing drift
refuses the update before writing entry points.

See [local installation](local-policy-installation.md) for commands, selection
scenarios, rollback and absolute-path limitations. The managed-machine skill
rollout is an alternative integration, not an extra required layer. A new MCP
coding module does not implement the future HTTPS/MCP policy-loader service.

## Evidence limits

Deterministic tests exercise module inclusion, dependency order, all generated
tool adapters, gateway complete content, CLI formats, corruption/refusal, update
and removal. They do not establish application controls or real model behavior.
At the time of this module review, the signed distribution was complete-only.
Subsequent 0.1.17 packaging embeds modular sources and helpers in the signed
installer and defaults to modular installation; see
[release packaging](releasing.md) and [current client evidence](agent-integration-verification.md#current-branch-evidence-2026-09-19).
Changed bundle bytes still require maintainer signing and bootstrap refresh. Full
`make check` results are recorded in `specs/changes/mcp-retrieval/tasks.md`.

No real-client routing, production gateway, cross-platform rollout, or paid
model evaluation was performed for this change. These remain rollout acceptance
work. The later modular installation default does not establish semantic
selection or model compliance. The gateway example still injects complete
content; [client-callable remote loading](rollout-paths/gateway-https.md) remains
a design. The later [gateway-managed example](rollout-paths/gateway-managed-loading.md)
selects and loads modules before each request; it does not use MCP.
