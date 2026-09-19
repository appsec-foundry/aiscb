# Agent Systems Module

`module-id: aiscb:agent-systems`. Load when designing or changing model-directed
tool execution, autonomous workflows, action permissions or approvals,
delegation, or multi-agent orchestration. Requires `aiscb:llm-applications`.
The trigger concerns the system being built, not the coding assistant's own tools.

## Agent Systems

- **[aiscb-AGENCY-001] Minimum Agency:** When building agentic systems, use deterministic execution where model-selected actions are unnecessary. Expose only task-required tools with narrow operations and resource scopes; separate read, write, and destructive capabilities. Prefer dedicated operations over unrestricted shell, code, database, or network tools. Review against the current OWASP Top 10 for Agentic Applications.
- **[aiscb-AGENTAUTH-001] Action Authority:** Treat model-selected actions and arguments as untrusted proposals. Validate them and authorize each execution outside the model against the initiating identity, tenant, task, and target resource with least privilege. Require human approval for consequential or irreversible actions; bind approval to the concrete action, target, and parameters, and renew it if these change. Delegated agents receive only the authority their subtask needs, never more than the parent holds.
- **[aiscb-AGENTBOUNDS-001] Bounded Execution:** Enforce finite limits on execution time, tool calls, retries, and delegation depth outside the model. Stop affected execution on exhausted limits or missing authorization. Provide cancellation and recheck authorization before further side effects. Never blindly retry a side-effecting action with an unknown outcome; reconcile its state or use an idempotency mechanism.
- **[aiscb-AGENTTESTS-001] Agent Boundary Tests:** Test rejection of unauthorized tools, resources, cross-tenant actions, altered approved parameters, and delegated privilege escalation. Verify that untrusted content cannot authorize actions and that limits, cancellation, and retries prevent unauthorized or duplicate side effects.
