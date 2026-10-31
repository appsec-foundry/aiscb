# AISCB implementation and independent security review

## Executive summary and decision

Option B keeps the existing AISCB core and relevant modules in the implementation
context and adds a separate security reviewer using the same requirements in a
fresh context. Its purpose is independent verification, not reducing the
implementer's AISCB context. Total tokens and latency initially increase.

The user selected Option B after the architecture discussion and explicitly
requested this analysis file and continuation with the recommended approach.
The first increment is an optional, findings-only
[skill example](../examples/security-review/aiscb-security-review/SKILL.md) with
a portable handoff and manual fresh-session fallback. It changes neither
normative rules nor the baseline version. See the [usage guide](security-review.md).
Automated client launchers, installation, a multi-arm harness and paid model
experiments remain subsequent work; no model-test budget was approved.

Analysis source snapshot: repository commit
`99c467a60bfdc8a96d8afe5a3e217934c7ffac7c`, baseline `aiscb-0.1.21`.
The initial conversation also contained an older installed development policy;
the product analysis uses the checked-out normative sources, not that installation.
The discussion was inspired by the user's account of Matt Pocock's
[Fixing the PR Bottleneck](https://www.youtube.com/watch?v=LlgiOCmFG_w).
The video was not independently retrieved, so no additional claims about the
speaker's recommendations are made here.

## Assessment of the initial hypothesis

A fresh reviewer can concentrate on counterexamples, incorrect assumptions and
missing evidence. Whether this improves AISCB results is a hypothesis. A second
agent can repeat the first agent's errors, overlook existing controls, or demand
unnecessary hardening. A different model also does not guarantee independence
of errors. More findings are not necessarily better security.

Security requirements often constrain decisions before implementation or
execution: identity propagation, authorization boundaries, credential handling,
cryptographic mechanisms, network destinations and package verification. Review
cannot undo disclosed secrets or execution of an unchecked package. Delaying
these requirements can require architectural rework rather than a small patch.
Some general quality rules also require early decisions; the useful distinction
is timing and reversibility, not whether a rule is called a security guideline.

The proposed split of responsibilities is useful: implementation establishes
controls, independent review checks them. Splitting requirements is much less
promising. In particular, the test rules require the assistant to create or
exercise tests, not merely inspect test coverage later. Functional correctness
of a protected operation includes rejecting unauthorized callers.

## Current architecture and evidence

The [core](../baseline/aiscb-core.md), [catalog](../baseline/catalog.json) and
cataloged [modules](../baseline/modules/) are normative. The complete artifact
is generated. [repository_policy.py](../scripts/repository_policy.py) validates
source/catalog consistency; [policy_loader.py](../scripts/policy_loader.py)
checks a pinned installed package and returns dependency-closed module bodies.
Neither loader determines semantic task applicability. That remains the
assistant's responsibility under `aiscb-MODULES-001`.

[Why the core stays loaded](why-the-core-stays-loaded.md) explains why selection
cannot safely precede every basic safeguard: apparently ordinary tasks can
involve secrets, untrusted instructions, dependency execution or pressure to
disable a control. Hooks can arrive after design decisions or fail to run.
The [modular proposal](modular-baseline-proposal.md) places the universal floor,
scoping, decisions and completion behavior in the core. The
[handoff](modular-baseline-handoff.md) explicitly retains the reporting contract
even when no thematic module matches. These are existing design rationales,
not proof of optimal context size.

The README records 2,010 `o200k_base` tokens for the core and 6,004 for the
complete baseline. Modules range from 226 to 532 tokens. Discovery, loader text,
overlays, dependencies and the rest of the conversation add context. Policy text
size, peak context occupancy, repeated input including cache reads and billed
cost are different measurements. The existing architecture already avoids
loading unrelated domain details; Option B addresses independent verification.

[Integration evidence](agent-integration-verification.md) records initial policy
delivery for concrete Claude Code, Codex CLI and Copilot CLI versions, including
release 0.1.21. It does not establish semantic routing, compliance or all IDE
surfaces. The core rationale cites successful routing tests, while the
[context comparison](context-comparison.md) records an incomplete, unbalanced
pilot and one scope-change trace missing required modules. Kiro observations
include three of seven login runs omitting web. These are different experiments;
together they do not justify a general routing-reliability claim.

The [requirements catalog](../specs/requirements.md) distinguishes partial,
unexecuted and absent model evidence. In particular, several authentication,
agent, retrieval and MCP obligations lack direct model cases. Successful loader
checks cannot substitute for behavioral evidence.

## Rule responsibilities

Classification concerns responsibilities, not replacement loading profiles.
Implementation means a requirement must influence design or action before or
during implementation. Review means it primarily evaluates an existing result.
Shared means the implementer must establish the property and the reviewer must
know the same requirement to verify it. At current rule-group granularity all
groups are shared; some have a strong implementation or review emphasis. This
does not imply loading every module for every task.

All IDs below have the `aiscb-` prefix. Summaries are analytical descriptions,
not replacement normative text. The linked source files contain the actual rules.

### Core

Source: [aiscb-core.md](../baseline/aiscb-core.md).

| Rule ID | Current responsibility | Context | Reason | Risk if deferred to review |
| --- | --- | --- | --- | --- |
| SCOPE-001 | Determine application scope and continuing agent safeguards | Shared | Both roles need task boundaries | Overreach or missing safeguards |
| MODULES-001 | Select before affected work and recheck | Shared | Review must reconsider actual affected interfaces | Shared routing blind spot |
| OM-006 | Require a material reason for interventions | Shared | Constrains changes and findings | Unnecessary hardening and warnings |
| OM-001 | Reuse controls and limit existing-app changes | Shared | Both must trace effective controls | Duplicate protection and scope expansion |
| OM-002 | Build greenfield controls and tests from the start | Shared | Defines design and acceptance | Architectural rework |
| OM-003 | Complete legitimate parts of mixed requests | Shared | Also applies to reviewer actions | Over-refusal or forbidden action |
| OM-004 | Handle knowingly requested weakening before acting | Shared, implementation first | Reviewer verifies prior authorization | Action precedes required decision |
| OM-005 | Decide materially riskier designs before implementation | Shared, implementation first | Later checks cannot supply prior consent | Retrospective risk acceptance |
| ATTR-001 | Explain baseline-caused interventions | Shared | Either role can cause an intervention | Unclear or duplicated explanations |
| DESIGN-001 | Identify assets, identities, flows and boundaries | Shared, implementation emphasis | Architecture and review model | Incorrect security architecture |
| ACCESS-001 | Authorize protected server actions | Shared | Implement and verify resource binding | Unauthorized access |
| INPUT-001 | Validate and use safe boundary mechanisms | Shared | Safe APIs are selected early | Unsafe processing before review |
| SECRETS-001 | Prevent disclosure and unsafe credentials | Shared | Applies throughout execution | Disclosure cannot be undone |
| PRESERVE-001 | Preserve effective controls | Shared | Prevent and detect regressions | Controls removed to make work pass |
| AGENT-001 | Separate untrusted content from authority | Shared | Both roles consume untrusted artifacts | Prompt injection or authority escalation |
| DEFAULTS-001 | Choose least privilege and fail closed | Shared | Determines ordinary and failure paths | Unsafe defaults become dependencies |
| TESTS-001 | Add positive and negative security tests | Shared | Creation and independent assessment | Missing or late test coverage |
| REPORT-001 | Review diff, fix introduced weaknesses, report risks | Shared, review emphasis | Mixes inspection, repair and delivery | Lost self-review and reporting contract |

### Web, authentication and cryptography

Sources: [web](../baseline/modules/aiscb-web.md),
[authentication](../baseline/modules/aiscb-authentication.md),
[cryptography](../baseline/modules/aiscb-cryptography.md).

| Rule ID | Current responsibility | Context | Reason | Risk if deferred to review |
| --- | --- | --- | --- | --- |
| WEB-001 | Secure transport, headers, cookies, CSP, CSRF and CORS | Shared | Affects clients and startup | Exposure or late browser redesign |
| WEBTESTS-001 | Exercise browser boundaries and forged requests | Shared | Tests must be created | Missing protection remains hidden |
| AUTH-001 | Abuse resistance, separate channels and session lifecycle | Shared | Determines storage and flows | Unsafe authentication architecture |
| AUTHMECHANISMS-001 | OAuth/OIDC, token storage and password limits | Shared | Protocol and mechanism selection | Flow or token-storage replacement |
| AUTHTESTS-001 | Test authentication lifecycle and byte limits | Shared | Must exercise real state boundaries | Misleading local-only tests |
| MECHANISMS-001 | Use established crypto and safe primitives | Shared | Library/algorithm selection is early | Unsafe mechanisms already used |
| WEBHOOK-001 | Verify signatures and prevent replay atomically; test | Shared | Persistence and processing order matter | Repeated side effects |

### Data handling

Source: [data-handling](../baseline/modules/aiscb-data-handling.md).

| Rule ID | Current responsibility | Context | Reason | Risk if deferred to review |
| --- | --- | --- | --- | --- |
| ERRORS-001 | Bound errors and encode/redact logs | Shared | Outputs occur during execution | Disclosure or forged log records |
| DESERIALIZE-001 | Parse data without execution; test | Shared | Parser must be safe before use | Code execution |
| RESPONSES-001 | Select fields explicitly; test exclusions | Shared | Defines public data contract | Credential disclosure |
| LIMITS-001 | Bound consumption at the consuming operation | Shared | Output truncation is insufficient | Resource exhaustion |
| FILES-001 | Validate, isolate, bound and authorize files | Shared | Storage and serving design | Traversal or unauthorized delivery |
| EGRESS-001 | Constrain destinations at connection time | Shared | Needs actual enforcement boundary | SSRF or credential forwarding |

### Secrets, supply chain and deployment

Sources: [secrets](../baseline/modules/aiscb-secrets-initialization.md),
[supply-chain](../baseline/modules/aiscb-supply-chain.md),
[deployment](../baseline/modules/aiscb-deployment-environments.md).

| Rule ID | Current responsibility | Context | Reason | Risk if deferred to review |
| --- | --- | --- | --- | --- |
| BOOTSTRAP-001 | Initialize without known credentials; keep persistent keys | Shared | Defines setup and operation | Unsafe first start or unstable keys |
| SECRETTESTS-001 | Test initialization and missing configuration | Shared | Setup must have verifiable failures | Privileged account or unsafe startup |
| DEPS-001 | Verify dependencies before execution; pin artifacts | Shared, implementation first | Explicit pre-execution obligation | Unchecked code has already run |
| DEPLOYMENT-001 | Minimize CI/runtime rights; require configuration | Shared | Executable deployment design | Overprivileged execution |
| ENV-001 | Separate development and production safely | Shared | Controls startup paths and switches | Reachable bypass or debug behavior |
| DEPLOYTESTS-001 | Exercise the production-safe start path | Shared | Development tests are insufficient | Unverified production behavior |

### LLM, agents, retrieval and MCP

Sources: [LLM](../baseline/modules/aiscb-llm-applications.md),
[agents](../baseline/modules/aiscb-llm-agents.md),
[retrieval/memory](../baseline/modules/aiscb-llm-retrieval-memory.md),
[MCP](../baseline/modules/aiscb-mcp-clients-servers.md).

| Rule ID | Current responsibility | Context | Reason | Risk if deferred to review |
| --- | --- | --- | --- | --- |
| LLM-001 | Validate outputs, isolate execution and use safe sinks | Shared | Enforcement sits outside the model | Output becomes code or authority |
| AGENCY-001 | Minimize autonomy and tool surface | Shared, implementation emphasis | Architectural capability choice | Excessive action authority |
| AGENTAUTH-001 | Authorize actions externally and bind approvals | Shared | Must precede side effects | Unauthorized execution |
| AGENTBOUNDS-001 | Bound loops, retries, cancellation and delegation | Shared | Runtime control structure | Repeated or unbounded effects |
| AGENTTESTS-001 | Exercise authority and execution boundaries | Shared | Requires executable test cases | Model promises mistaken for enforcement |
| RETRIEVAL-001 | Authorize before context exposure | Shared | Answer filtering is too late | Unauthorized data reaches model |
| MEMORY-001 | Authorize persistence and preserve provenance | Shared | Writes can persist poisoned trust | Unauthorized or poisoned memory |
| RETRIEVALTESTS-001 | Test context exclusion, revocation and writes | Shared | Observe exposure, not only answers | Hidden context disclosure |
| MCPAUTH-001 | Bind tokens, consent, handles, discovery and Origins | Shared | Defines identity/transport boundaries | Token or resource misuse |
| MCPLOCAL-001 | Verify and approve local execution before start | Shared, implementation first | Cannot approve retrospectively | Unchecked process receives access |
| MCPTESTS-001 | Test actual configured transport and process boundary | Shared | Stdio does not prove HTTP behavior | Wrong-transport evidence |

Potential future separation is at responsibility level: REPORT-001 mixes
inspection, repair, materiality and reporting; WEBHOOK, FILES, EGRESS,
DESERIALIZE and RESPONSES combine controls and tests; LLM and AGENCY combine
mechanisms and review references; AUTH combines controls and design decisions.
An adapter can turn these into review questions without maintaining a second
rule set. No normative split is approved by this decision.

## Architecture alternatives

| Criterion | A: existing AISCB | B: AISCB plus reviewer | C: divide policy by role | D: targeted design step |
| --- | --- | --- | --- | --- |
| Security | Prevention and self-review | Possible additional detection | Depends on complete, timely handoff | Possible better early boundaries |
| Reliability | One agent performs all work | Second opportunity, correlated errors remain | New routing and responsibility gaps | Plan may still be implemented incorrectly |
| Context/cost | Existing selective modules | Same implementer load; added review cost | Smaller implementer, uncertain total | Additional planning context |
| Latency | Least added overhead | Review and corrections | Review necessarily on completion path | Early delay, possible later savings |
| Unnecessary measures | Core limits intervention | Can reduce or create false positives | Roles may disagree about requirements | Can over-plan small work |
| Over-refusal | Existing model risk | Additional source of mistaken blockers | Missing context can worsen decisions | Risk inflation possible |
| Rework | Own mistakes can remain hidden | Detected defects require correction | Greatest late-design rework risk | May avoid architectural rework |
| Maintenance | Existing implementation | Handoff and optional adapter | Profiles, coverage and version coordination | Small scoped planning workflow |
| Compatibility | Existing integrations | Needs fresh agent/session | Depends strongly on orchestration | Manual planning works across clients |
| Traceability | Existing traces and checks | Findings tied to exact revisions | Must track ownership of every requirement | Explicit decisions |
| Testability | Existing harnesses | Pipeline extension needed | Also needs omitted-policy/failure tests | Compare plan with actual behavior |

Option B is selected for exploration, while A remains the normal installation.
Option D can complement changes to fundamental identity, tenant, credential,
deployment or agent authority models. It does not replace implementation review.
Option C is deferred until a concrete safe reduction and evidence justify it.

## Reviewer design and trust boundaries

The first workflow is explicitly invoked for one coherent change before final
delivery, not after every edit. A fresh context receives requirements, scope,
acceptance criteria, exact diff/snapshot, relevant project sources, test evidence,
approved decisions, and the same policy snapshot with overlays. It does not
receive the entire implementation conversation. Missing facts must not become
invented requirements. The reviewer reselects modules from the actual change,
then uses the existing loader for integrity and dependencies.

Protected assets are the reviewed code, requirement/policy identity, credentials
and integrity of the review result. Diff text, comments, test output and the
implementer's claims are untrusted evidence. They cannot authorize commands or
change review scope. Existing AISCB mechanisms remain the requirements; this
workflow's narrow read access limits the reviewer's ability to alter its own
evidence. Host permissions, not a prompt, enforce access. Test execution needs
an isolated boundary because a test command may execute changed code.

The reviewer returns location, rule ID, concrete misuse path and consequence,
existing controls examined, evidence, minimal correction and focused test.
Unverified behavior is reported separately from demonstrated vulnerabilities.
A changed snapshot or missing policy produces incomplete coverage, not a pass.
The implementer fixes findings under the existing authorization, and a new
requested review checks the changed snapshot. There is no automatic repair loop.
Existing decision requirements govern human approval; a finding alone adds no
approval gate. OM-001, OM-006 and REPORT-001 constrain unnecessary hardening.

Controls remain normative AISCB text. Review heuristics are ways to gather
evidence, not extra application requirements. Reporting describes results and
limitations without converting uncertainty or every successful check into a
Security note. Same version labels are insufficient for development snapshots;
use the trusted package digest or reviewed sources with catalog identity.

## Empirical validation

[tests/run.py](../tests/run.py) supplies control/baseline comparisons, fixtures,
scope checks, verification and semantic judges. Its baseline arm uses complete
policy, so it is not automatically a modular comparison.
[tests/context_comparison.py](../tests/context_comparison.py) supplies control,
complete and modular arms, actual loader traces, independent executable checks,
CLI token categories and timing. [routing.py](../tests/routing.py) exercises
selection and reload behavior. Judges score results; they are not reviewers
that return findings for correction. Existing oracles cover selected behaviors,
not every requirement, and some aggregate functional and security outcomes.

New infrastructure is needed for fresh-reviewer orchestration, immutable phase
snapshots, finding adjudication, correction/re-review accounting and distinct
security outcomes before and after review. Usage must sum implementation,
review, corrections and verification; cached tokens and unknown usage remain
explicit. Cost requires the selected model's pricing rather than treating all
tokens equally. Detection/false-positive rates need adjudicated flaws and clean
controls, not just a count of findings.

Proposed first pilot: three scenarios, three predetermined repeats, three arms
(no AISCB, modular AISCB, modular AISCB plus reviewer): 27 workflows, with extra
review calls in the last arm and at most one correction round per workflow.
Use an owner-bound endpoint change, a small refactor preserving an existing
control, and a documentation/label change without relevant security impact.
Reuse fixtures where their visible contracts and independent oracles suffice.
Greenfield authentication and dependency/deployment changes follow if the small
pilot is informative. Dependency tests use controlled artifacts, not dangerous
external packages. A fourth reduced-policy arm needs an exact, separately
approved experimental reduction; it must not masquerade as unchanged AISCB.

Fix model versions, tools, policy digests, task contracts and budgets; randomize
order; isolate profiles; retain incomplete runs in denominators. Measure final
security and functional outcomes, introduced flaws, detected/missed defects,
unnecessary interventions, scope drift, correction rounds, tokens, cost and
latency. Keep independent checks outside agent-writable fixtures. Human review
settles disputed findings. Three repeats are exploratory, not statistical proof.

The first comparison tests workflow packages. A later equal-effort self-review
arm is needed to distinguish fresh-context benefit from simply spending more
compute. If implementations contain no flaws, reviewer sensitivity remains
unknown; a separate known-defect/clean-diff test can probe it without pooling
those results into the implementation comparison.

## Delivery requirements and acceptance

Sources: the user's analysis request, subsequent explanations of Option B and
explicit instruction to proceed; existing core/module rules; repository
workflow in AGENTS.md and specs/README.md. The authorized first increment is
analysis plus a reusable findings-only workflow. Baseline/version changes,
global installation, publication and paid experiments are outside this increment.

Observable acceptance for the initial example:

- Analysis records alternatives, rule responsibilities, evidence limits and pilot.
- Skill preserves implementer policy and references the existing loader.
- Handoff identifies requirements, exact code, policy and permitted checks.
- Fresh-context launch and manual fallback are distinguished from self-review.
- Reviewer returns findings without patches and identifies incomplete coverage.
- No automatic retries, nested agents, model tests or installation are introduced.
- Skill metadata, relative links, rule inventory and repository checks validate;
  baseline byte/token budgets are recomputed without changing normative text.

These static checks establish artifact consistency, not runtime enforcement or
review quality. A client acceptance run must separately demonstrate fresh
context, matching policy, module loading and permission behavior. A paid pilot
must demonstrate any claimed security benefit.

## Next decisions

Select the first actual client and model, review invocation point, supported
isolated verification tools, finite execution budget and acceptable additional
cost/latency. Agree success criteria and false-positive tolerance before a paid
pilot. After evidence, decide whether to automate invocation or explore specific
policy reductions. The initial skill can also be used manually in a new session.

Repository-only workflow/harness work needs agreed requirements and verification,
but no normative change specification while baseline text stays unchanged.
Any later core/module behavior change requires the approved specification
process; writes under specs and an exact version change require their respective
explicit approvals. This analysis is explanatory documentation, not policy.
