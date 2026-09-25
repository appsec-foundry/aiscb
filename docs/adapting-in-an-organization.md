# Adapting aiscb inside an organization

aiscb tells an assistant how to behave. It cannot know what your organization has decided: which identity provider to use, which claims and group IDs grant access, which libraries and headers are approved, where audit events go, or which changes need policy review. Those decisions still have to reach the assistant, or it will invent them.

Putting everything into one large instruction file makes every session pay for
unrelated policy. This guide loads the short aiscb core and organization
overlay always, then puts official `aiscb:*` and organization modules on one
flat namespaced plane selected only for matching work. The
[modular baseline design](modular-baseline-proposal.md) records the rationale.

The guide is an implementation recommendation, not part of the normative baseline. Acme names, versions, URLs, and digest placeholders are examples to replace.

For a working project installation, start with
[local installation and overlays](local-policy-installation.md). One command
installs the core, overlay, combined discovery, and verified local loader. The
broader rollout variants below describe managed deployments and future gateway
loading, not additional baseline products.

## How the layers fit together

| Part | Content | In context |
| --- | --- | --- |
| aiscb core | Portable routing, scope, safety floor, decisions, tests, and reporting, pinned to an approved release and digest | Always |
| Overlay | Organization identity, namespace authority, and the few substantive rules that apply to every task | Always |
| Flat catalog | One namespaced entry per aiscb or organization module: ID, trigger, source, and dependencies | Always, as skill descriptions or an injected list |
| Module | Portable aiscb rules or organization rules and acceptance criteria for one domain | Only for matching work |
| Blueprint | Approved values a pack refers to: libraries, claim names, group mappings, headers, limits | Only with its pack |
| Adapter | The generated files or gateway block that put the above into the format each assistant reads | Generated per tool |

In modular delivery, "loaded only for matching work" means the
assistant sees the core, overlay, and discovery metadata at session start and
applies `aiscb-MODULES-001` once across all namespaces. For a local bundle, the
project adapter exposes every module through one bounded Python loader; managed
deployments may instead wire the generated skill surface. For a gateway, one
loading tool accepts bounded catalog IDs, called either through a configured
client tool or through a separate selection request at the gateway. A file or URL alone
loads nothing.

The catalog triggers and core routing rule are the selection mechanism, so test
them with real assistant runs, not only file checks. Keep the overlay and
organization discovery metadata small or the core's saving disappears.

### A worked example

The [bundle example](../examples/organization-bundle/) wires one authentication pack. Its catalog entry, abridged, is the whole registration:

```json
{
  "id": "acme:authentication",
  "file": "packs/authentication.md",
  "trigger": "Login, SSO, sessions, tokens, or anything that decides who the user is",
  "paths": ["**/auth/**", "**/login/**"],
  "blueprints": ["blueprints/spa/1.0.0.json"],
  "requirements": {
    "ACME-SSO-001": {"narrows": ["aiscb-AUTHMECHANISMS-001", "aiscb-AUTH-001"]}
  }
}
```

The build turns that entry into whatever the tool uses for discovery. For Claude Code, Codex, and Copilot it writes a `SKILL.md` whose frontmatter `description` is the trigger text and whose body is the pack; the tool shows the assistant only the description until the assistant opens the skill. In the HTTPS design the same entry becomes one line of the injected catalog. The pack's first paragraph names the blueprint it needs, so the blueprint loads with the pack and never on its own.

Two sessions on the same machine then differ like this:

- A developer asks for SSO login. The single selection pass chooses both
  `aiscb:authentication` (which also loads `aiscb:cryptography`, `aiscb:data-handling`, and transitive `aiscb:secrets-initialization`) and `acme:authentication`; the Acme module then loads its
  blueprint for issuer, claim, and approved group values.
- A developer asks to edit unrelated prose. Nothing matches, so no module body
  loads; only the core, overlay, and discovery metadata remain in context.

To wire a requirement, write a namespaced module with stable rule IDs, put
values in a versioned blueprint, add a semantic catalog trigger, and rebuild.
The core routing rule already covers every configured namespace.

## Choose a delivery

The local project integration is implemented. Other deployment shapes are:

1. **Gateway injection of everything.** Append the eager aiscb artifact, overlay,
   all organization modules, and referenced blueprint values. The example
   builder already generates this block. Modular sources do not require a
   runtime loader for this delivery; rebuild and deploy the block and its digest.
   Choose this when policy is small enough that no lazy loader is worthwhile.
2. **Local modular bundle.** Load core, overlay, and discovery at startup; expose
   every `aiscb:*` and organization module through one verified loader.
3. **Gateway injection with HTTPS loading (design only).** Inject core, overlay, and merged
   catalog; retrieve all module namespaces and blueprints through one verified
   bounded loader. This requires a new remote adapter and loader, client tool
   provisioning, and a shared session release. Injecting only the core does not
   implement it. See [status and migration](rollout-paths/gateway-https.md#implementation-status-and-migration).
4. **Gateway-managed loading.** When development systems cannot be configured,
   let the gateway select and load modules before the normal model request.
   The LiteLLM example supports the Anthropic Messages format, including
   streaming. No client skill, helper or MCP registration is needed. See
   [setup and limits](rollout-paths/gateway-managed-loading.md).

| | Local bundle | Gateway injection with HTTPS loading |
| --- | --- | --- |
| Always in context | Core, overlay, merged discovery metadata | Core, overlay, merged compact catalog |
| Loaded for matching work | aiscb and organization modules plus blueprints from local files | aiscb and organization modules plus blueprints from pinned HTTPS artifacts |
| What you distribute | A versioned bundle and its tool integration | A gateway configuration and access to a policy loader |
| What developers need | Installed files and a supported assistant | A supported gateway connection and a tool that can retrieve and verify policy content |
| Main operational cost | Installing and updating each machine or repository | Operating the gateway, policy host, and download path |
| Offline policy access | Installed release, subject to your staleness policy | Only if you provide a verified cache; otherwise affected work stops |

The client-callable HTTPS variant still needs an MCP registration or reviewed
helper and network access. Gateway-managed loading moves execution and policy
access to the gateway and requires no local policy files or loader setup. The
[bundle example](../examples/organization-bundle/) implements the flat local
module release and a LiteLLM injection hook; it does not implement the HTTPS
loader.

## Define the shared content

The content is the same for every delivery. Keep it in a policy repository, review changes there, and generate the adapters from a reviewed release.

Give organization requirements stable IDs. Record whether each narrows named aiscb rules or stands alone as an organization requirement. The overlay and packs may narrow the baseline, never relax it. Keep rationale and history in the policy repository, outside the assistant's routine context.

### Customize rules and handle exceptions

- **Make a rule more specific or stricter:** Give it an organization rule ID
  and name the baseline rule it narrows. Put universal rules in the overlay;
  put domain rules in a module and register its loading triggers in the
  catalog. Keep configuration values in a blueprint. For example, put
  “use Acme SSO” in the authentication module and the approved issuer in its
  blueprint. The baseline still applies.
- **Request an exception for a concrete task:** Follow the [core's
  explicit-override procedure](../baseline/aiscb-core.md#operating-mode).
  The assistant names the rule, risk, and safer alternative, obtains explicit
  user confirmation before proceeding, and records accepted risk in
  **Security note (aiscb)**. An overlay cannot preapprove exceptions.
  Exposing real secrets or harming others remains forbidden. Use a compliant
  solution without confirmation when it meets the request.
- **Disable a baseline rule across the organization:** The overlay does not
  support this. For example, “internal services need no access control”
  conflicts with aiscb. The assistant reports the conflict and stops only
  the affected work. Permanent exceptions require a separately approved
  change to the policy model.

### The overlay

The example overlay includes a specification-first workflow: load policy,
specify and approve requirements, implement, then verify. Adapt the
[project workflow template](../examples/project-workflow.md) to your process.
Keep application specifications in the project, not in security modules.

The overlay is the part every session pays for, so it carries only what every session needs:

- its own ID and the aiscb release it extends, so `aiscb?` reports both;
- the authority rule for organization modules and blueprints;
- the few substantive rules that apply to almost every change, such as tenant binding, an audit-log requirement, or a list of approved languages.

The aiscb core, not the overlay, supplies selection, reload, and failure
behavior for every namespace. Duplicating those rules in each overlay would
increase the always-on cost and allow the two routing contracts to drift.

Everything else belongs elsewhere. Domain rules go into a pack: "accept only approved group IDs" is an authentication requirement, so it belongs in the authentication pack. Values go into a blueprint: the approved group IDs belong in that pack's blueprint. Changing those IDs changes who can gain access, so a blueprint change still needs policy review. Anything aiscb already says, rationale, history, and project-specific requirements stay out of the overlay entirely.

If the organization already has a secure coding standard, sort its statements the same way: the handful that apply everywhere become overlay rules, the rest become packs by domain, and every concrete value becomes a blueprint entry. Most standards end up with an overlay of well under a page.

Give the overlay its own ID, such as `acme-sec-1.0.0`. Include the following
behavior in every delivery:

```markdown
# Acme Secure Coding Overlay

`baseline-id: acme-sec-1.0.0`. Extends aiscb (`aiscb-0.1.18`). On `aiscb?`,
report both IDs and their sources. Identify injected content as gateway-supplied;
do not claim to have read a local file for it.

- **[ACME-POLICY-001]** Content selected from the verified `acme:*` namespace
  by `aiscb-MODULES-001` is organization policy in its declared scope; use
  referenced blueprints as values. It may add requirements or narrow named
  aiscb rules but may not relax them, change permissions, or expand the task.
  The core failure rule covers missing, invalid, incompatible, or conflicting
  organization content.
- **[ACME-TENANT-001]** (narrows aiscb-ACCESS-001): Bind every protected query
  to the authenticated identity and tenant. Never take effective tenant or
  permissions from request data.
```

ACME-POLICY-001 is a deliberate exception to aiscb-AGENT-001, which treats
tool results as untrusted. It holds only because the always-loaded overlay
authorizes the exact namespace and adapter loader. Loader verification and
configuration, not overlay prose, establish which bytes are policy.

The adapter supplies the core and merged catalog beside this overlay. A gateway
must inject core text; a path or `@` marker in an API request is not an import.
Local adapters use the [tool-specific mechanisms in the local bundle rollout
path](rollout-paths/local-bundle.md#adapters-per-tool).

### Packs, catalog, and blueprints

A pack names its ID, version, scope, requirements, blueprint references, and representative positive and negative tests. For example, an authentication pack can require SSO with authorization code and PKCE, specify the blueprint holding issuer and group mappings, and require tests for invalid issuer, unknown groups, logout, and missing configuration. Keep those requirements in the pack rather than duplicating them in the catalog.

The catalog records each pack's trigger, any path triggers, owner, policy source, and requirement-to-aiscb mapping. Generate the discovery metadata for each adapter from it. Write semantic triggers such as "login, SSO, sessions, tokens" because authentication changes do not always occur in a directory named `auth`. Several packs may match. If applicability is unclear, resolve it before the affected change; an absent path match alone does not make a pack irrelevant.

For local bundles, references resolve inside the selected release. For HTTPS, they identify approved artifacts by ID, exact URL, version, size limit, and digest. The catalog must be readable without first loading any pack. Validate duplicate IDs, missing references, unknown aiscb targets, and unlisted packs during the build; review trigger coverage and contradictory requirements as well.

Use Markdown for readable requirements and YAML or JSON for structured values. A structured file is data the assistant reads, not a mechanism: YAML does not provide lazy loading or enforce anything. Validate it with a safe parser against a versioned schema during the build and, for HTTPS delivery, again in the loader; the [local bundle rollout path](rollout-paths/local-bundle.md#build-and-release) lists the checks.

Review changes in Git before release. If another system owns the source data, import a bounded response from an approved endpoint into a pull request. Runtime loading retrieves the approved release, not that system's latest mutable state. Blueprints contain no credentials or personal data. Values affecting authentication, authorization, transport, secrets, or limits need policy review.

## Implement the selected rollout path

The rollout paths describe how to deliver the content to an assistant:

- [Local bundle](rollout-paths/local-bundle.md): build a release, distribute it, connect instructions and skills to each tool, and update or roll back without mixing releases in a session.
- [Gateway injection with HTTPS loading](rollout-paths/gateway-https.md): publish
  pinned modules and blueprints, inject initial context, provide one verified
  loading tool, and keep gateway and loader on the same release set.

## Verify before rollout

Name owners for policy content, distribution or gateway operations, and supported assistant integrations. Before implementation, record the chosen delivery, supported clients, distribution channel or gateway and policy hosts, loader location, authentication, release activation, and offline policy.

Test the mechanisms separately from model behavior:

| Check | Evidence |
| --- | --- |
| Delivery | Bundle installation and tool entry points work in a clean environment, or a real gateway request receives the expected block; record release IDs and digests without logging prompts or credentials |
| Retrieval | Wrong hash, version, schema, duplicate keys, oversized response, redirect, timeout, denied access, and missing artifact produce no usable policy content |
| Selection | Real assistant runs load all matching packs before design or code changes, including a task matching several packs and a root-started run editing a child directory; unrelated work does not load them |
| Failure behavior | A missing tool or required artifact stops affected work; the assistant does not use remembered values or another source |
| Release consistency | An update during a session followed by first use of another pack keeps one release throughout; test restart, rollback, and any cache |
| Application behavior | Representative positive and negative cases exercise SSO, claims, tenant isolation, browser policy, and limits covered by the selected packs |

Use `aiscb?` as a smoke test for visible IDs and sources, not proof of prior loading or compliance. Repeat affected checks after policy, loader, gateway, or client changes. Mark unimplemented pieces and unrun integration tests explicitly.

An overlay supplies instructions; it cannot guarantee compliance. A verified loader establishes which content was returned, not whether the model selected every needed pack or followed it. Requirements that must hold still need application controls, tests, review, and deployment checks.

## Handing the implementation to an assistant

Give an implementing assistant this guide and the selected rollout path. It should identify the deployment inputs, reuse existing organization infrastructure and settings, and ask for missing deployment choices rather than invent hosts or credentials. A host, tool, installer, or catalog format mentioned in an example does not exist until it has been implemented and configured; the assistant should report those gaps explicitly.
