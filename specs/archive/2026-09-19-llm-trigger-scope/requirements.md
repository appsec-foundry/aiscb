# Requirements

## LLM-SCOPE-001 Distinguish application work from assistant activity

Source: the user's approval of the proposed trigger clarification and module
rename in this conversation; existing aiscb-LLM-001 and aiscb-AGENT-001.

Name the module aiscb:llm-applications, titled LLM Applications. Its catalog
trigger and module introduction apply to designing or changing LLM features in
the system being built, not merely the assistant's own prompts, tool use, or code
generation. Preserve every existing trigger topic and the security mechanisms
of aiscb-LLM-001. The assistant's own untrusted-input boundary remains in the core.

Acceptance: discovery and the module introduction agree on this scope; current
source paths and references use the new name; the security rule body is unchanged.
An application prompt change matches; ordinary code or documentation editing
does not match solely because an assistant uses prompts or tools to perform it.

## LLM-SCOPE-002 Preserve loading and measure the change

Source: the approved recommendation to update references, dependencies, and
documentation; AGENTS.md verification and context-budget requirements.

Keep agent-systems and retrieval-memory dependent on the renamed module, loaded
once before their own rules. Preserve other module triggers and the baseline
version. Show the new trigger in every modular installation's discovery text.

Acceptance: installer and loader tests cover the renamed module and dependency
closure, reject the obsolete ID, and make check passes. Recompute all artifact
sizes and o200k_base counts. Distinguish deterministic loader evidence from
model selection evidence and record any model-test gap.
