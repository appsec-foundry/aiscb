# OWASP alignment review

Reviewed on 2026-09-19 against the feature-branch rule text. This is an
assessment of instructions, not certification, application coverage, or model
evidence. "Direct" means a concrete mechanism appears in the baseline; it does
not mean an entire OWASP category is solved. Rule IDs below omit `aiscb-`.

## Sources and editions

The current LLM edition is **2026**, not 2025. Its official repository identifies
the release as published on August 4, 2026. Use the current category numbers;
for example, excessive agency is now LLM03 and output handling is LLM10.
Sources: [official release and list](https://github.com/GenAI-Security-Project/GenAI-LLM-Top10),
[canonical entries](https://github.com/GenAI-Security-Project/GenAI-LLM-Top10/tree/main/2026/final),
and [published report](https://genai.owasp.org/download/56857/?tmstv=1785822482).

The agentic edition is **2026**, announced December 9, 2025.
Its [official release page](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/)
and OWASP's [May 2026 crosswalk](https://genai.owasp.org/download/54627/?tmstv=1779726713)
were checked, along with the agentic mappings in the current LLM report.
The original agentic PDF endpoint could not be retrieved successfully in this
session; detailed comparisons use those accessible official companion sources.
The separately published *State of Agentic AI Security and Governance 2.01*
is not a new version number for the Agentic Top 10.

## LLM risks

| 2026 category | Existing instructions | Assessment and limits |
| --- | --- | --- |
| LLM01: instruction injection | LLM-001, AGENT-001, DESIGN-001, AGENTAUTH-001 | Direct: untrusted content cannot confer authority; enforcement sits outside the model. No promise of injection-proof prompts. |
| LLM02: information disclosure | SECRETS-001, INPUT-001, ERRORS-001, LLM-001 | Direct: minimize sensitive context, restrict output and logging, isolate tenants. Broader privacy governance is outside this baseline. |
| LLM03: excessive agency | AGENCY-001, AGENTAUTH-001, AGENTBOUNDS-001 | Direct: narrow tools, reduced autonomy, scoped authorization, approvals and execution limits. |
| LLM04: supply chain | DEPS-001, INPUT-001 | Partial: software identity and integrity checks exist. Model weights, adapters, datasets and artifact promotion are not explicitly named. |
| LLM05: poisoning | LLM-001, RETRIEVAL-001, MEMORY-001 | Direct retrieval/memory mechanisms: provenance, external write authorization and removal of poisoned state. Training-pipeline controls remain outside coverage. |
| LLM06: resource consumption | LIMITS-001, AGENTBOUNDS-001 | Partial: work, time, calls, retries and depth are bounded. Token and monetary budgets for ordinary inference are not explicit. |
| LLM07: false information | LLM-001, AGENTAUTH-001, REPORT-001 | Partial: output schemas and action authorization help; factual correctness and current action preconditions need independent verification. The assistant's reporting rule is not a product-level evidence check. |
| LLM08: hidden context | SECRETS-001, DESIGN-001, AGENTAUTH-001 | Partial: secrets are minimized and authorization stays outside the model. Discoverability of hidden prompts is not explicitly stated. |
| LLM09: retrieval and vectors | RETRIEVAL-001, RETRIEVALTESTS-001 | Direct: pre-context permissions, provenance and revoked-access/cache tests. Embedding-specific inference attacks remain partial. |
| LLM10: output handling | INPUT-001, LLM-001 | Direct: strict schemas, contextual encoding, safe sinks and restricted generated-code execution. |

These are our assessments of local rules. The distinctions for
[hidden context](https://github.com/GenAI-Security-Project/GenAI-LLM-Top10/blob/main/2026/final/LLM08_HiddenContextExposure.md),
[retrieval](https://github.com/GenAI-Security-Project/GenAI-LLM-Top10/blob/main/2026/final/LLM09_VectorAndEmbeddingWeaknesses.md),
[misinformation](https://github.com/GenAI-Security-Project/GenAI-LLM-Top10/blob/main/2026/final/LLM07_Misinformation.md),
and [consumption](https://github.com/GenAI-Security-Project/GenAI-LLM-Top10/blob/main/2026/final/LLM06_UnboundedConsumption.md)
were checked against their current canonical entries.

## Agentic risks

| 2026 category | Existing instructions | Assessment and limits |
| --- | --- | --- |
| ASI01: redirected goals | AGENT-001, LLM-001, AGENTAUTH-001 | Direct: task scope and external action checks limit consequences. |
| ASI02: tool misuse | AGENCY-001, AGENTAUTH-001, LLM-001 | Direct: dedicated tools, validated proposals, authorization and sandboxing. |
| ASI03: identity abuse | ACCESS-001, AGENTAUTH-001 | Direct: initiating identity, tenant, task and resource scope; delegation cannot increase authority. |
| ASI04: dependencies | DEPS-001, MCPLOCAL-001 | Partial: executable packages and MCP startup configuration are checked; descriptors cannot grant authority. General registries and peer onboarding remain partial. |
| ASI05: code execution | INPUT-001, LLM-001, AGENCY-001 | Direct: structured sinks and constrained intentional execution. |
| ASI06: poisoned memory | MEMORY-001, RETRIEVALTESTS-001 | Direct: external write authorization, provenance, separation from policy and removal of poisoned state; no claim of semantic poison detection. |
| ASI07: agent messages | INPUT-001, ACCESS-001, AGENTAUTH-001 | Partial: generic validation and authorization; authenticated peers, message integrity and replay protection are not explicit. |
| ASI08: failure propagation | AGENTBOUNDS-001, AGENTTESTS-001 | Direct containment through limits, cancellation and safe retries; semantic fault propagation remains partial. |
| ASI09: misplaced human trust | AGENTAUTH-001 | Partial: approval binds concrete actions; trustworthy approval presentation and independent evidence are not specified. |
| ASI10: deviating agents | AGENCY-001, AGENTAUTH-001, AGENTBOUNDS-001 | Partial: authority and cancellation contain actions; detection, credential revocation and recovery are not a full incident-response design. |

## Recommended follow-up, not new normative rules

The approved split is consistent with the current lists and materially improves
least agency. The following compact additions merit a separate content decision:

1. LLM context: make hidden-prompt exposure assumptions explicit. Retrieval
   scoping, provenance and persistent-write authorization were subsequently
   approved and implemented in `llm-retrieval-memory`; they are no longer pending.
2. Agent action evidence: check current preconditions against authoritative
   state and build approval displays from the actual execution request,
   not solely from model-written descriptions.
3. Agent communication: authenticate peers, validate message scope and schema,
   protect integrity, and reject replay where messages can cause side effects.
4. Consumption and dependencies: name inference token/cost budgets and AI
   artifact/tool-registration verification explicitly when those areas change.

The user's request was to assess consideration, not copy all twenty categories.
Only the separately approved MCP/retrieval and data/web follow-up was implemented;
the other recommendations above remain non-normative. Full
training governance, hallucination elimination, legal compliance and an
enterprise incident-response program should not be implied by this compact
assistant baseline. Relevant organization specifics belong in overlays/modules.

Selecting modules remains essential: dependency and resource-limit protections
in other modules do not help a modular session unless their triggers match and
they are loaded. Assembly tests establish none of that behavioral evidence.
