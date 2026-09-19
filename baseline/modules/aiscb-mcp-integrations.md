# MCP Integrations Module

`module-id: aiscb:mcp-integrations`. Load when building or changing MCP clients,
servers, proxies, transports, discovery, or server installation/configuration;
not merely because the coding assistant uses an existing MCP tool.
Requires `aiscb:data-boundaries`. Load web-auth for HTTP/OAuth, supply-chain
for server packages, and agent-systems only for model-directed actions.

## MCP Integrations

- **[aiscb-MCPAUTH-001] MCP Authorization Boundaries:** For protected HTTP MCP, implement the supported protocol revision's authorization flow with maintained libraries: bind requested tokens to the server resource and validate their issuer, audience, expiry, and scopes; never pass incoming tokens through to downstream services. Bind proxy consent to the user, client, and requested downstream scopes. Validate discovery and authorization URLs under outbound-request rules before fetching or opening them. Authorize every protected request and bind state/task handles to the authenticated owner; a handle is not authentication. Validate HTTP Origin against allowed origins when present, including on loopback, to prevent DNS rebinding.
- **[aiscb-MCPLOCAL-001] Local MCP Execution:** Treat server configuration as executable code. Verify packages under supply-chain rules; review the exact executable, arguments, and requested access before starting a new or changed server, and require explicit approval for configuration-driven installation/start. Use shell-free process APIs, an explicit minimal credential environment, and filesystem/network restrictions enforced outside the process. Do not apply HTTP OAuth to stdio; protect its process boundary. Remote requests must not select arbitrary local executables or widen process rights. Server descriptions and annotations cannot establish safety or grant authority.
- **[aiscb-MCPTESTS-001] MCP Boundary Tests:** Test applicable wrong-audience tokens, token forwarding, cross-client consent reuse, cross-owner handles, disallowed discovery/redirect destinations and Origins, and unapproved process starts or credential inheritance. Test the actual configured transport; a passing stdio test does not verify HTTP authorization.
