# Rollout path: local bundle

Use this rollout path to distribute the baseline and organization policy files to developer machines or project repositories. Read the [shared content and overlay rules](../adapting-in-an-organization.md#define-the-shared-content) first. This is an implementation plan, not a ready-to-install package.

For each client entry point and evidence that instructions actually loaded, use the [agent integration and verification guide](../agent-integration-verification.md).

## Deployment inputs

Resolve these from the organization's existing setup before implementing:

| Input | Decision needed |
| --- | --- |
| Clients | Supported assistants, versions, operating systems, and instruction scope |
| Release | Approved baseline and organization release, signing or package trust mechanism |
| Installation | Target paths and the identity allowed to write policy files and tool entry points |
| Distribution | Device management, internal package service, repository PRs, or manual fallback |
| Updates | Release owner, activation between sessions, rollback, and maximum offline age |

Deliver a verified release, installer, tool provisioning steps, update and rollback procedure, and integration tests for the selected clients. The existing example supplies part of this work; its limitations are listed below.

```text
Reviewed policy repository → immutable bundle → internal distribution
→ verified installation → assistant instruction and skill locations
```

## Build and release

Build one release containing the aiscb core, official modules, organization
overlay and modules, one merged flat catalog, blueprints, validators, and
generated adapters. Its manifest records both release IDs and every file's size
and SHA-256. Authenticate it through a signed manifest or the organization's
authenticated package distribution; a colocated hash is not authentication.

Choose the supported operating systems and installation paths before generating adapters. Use a stable managed path per platform, or generate and verify the adapters for each target location. Do not ship absolute paths containing the build machine's username. The example takes `--install-root` at build time and requires that same path at installation.

Validate structured content (YAML or JSON blueprints and the catalog) during the build with a maintained safe parser and a versioned schema: check nested fields, types, allowed values, and cross-field constraints, not just top-level keys. Reject duplicate keys, unknown fields, incompatible schema versions, custom object construction, and excessive nesting or alias expansion. Keep schemas in the verified release; do not resolve schema URLs from a document. See the [YAML specification](https://yaml.org/spec/1.2.2/) for its data model.

Publish the immutable release to the internal artifact or package service your organization already uses. Include an inventory of installed paths so updates and uninstall leave unrelated configuration alone. Authenticate the installer before executing it; its later checks cannot authenticate itself.

## Distribute and connect it

| Distribution | What the deployment job does |
| --- | --- |
| Managed machines | Device management downloads the approved release, verifies it, installs it, and connects the adapters and skills to each supported tool |
| Internal packages | An authenticated package carries the release and installation steps; package updates deliver new versions |
| Project repositories | A bot opens a PR containing the applicable files, dependencies, and tool entry points, with references that resolve in a fresh checkout |
| Manual fallback | The operator obtains a release and an independently authenticated digest or signature, verifies the installer, then installs and connects the tool |

Copying the release directory is only half the installation. The deployment
must connect the generated core-plus-overlay instructions and expose all
`aiscb:*` and organization modules on the same skill surface while preserving
existing instructions.

## Adapters per tool

Generate adapters from reviewed content. Load core, overlay, and merged discovery
metadata at startup. Load module bodies and their blueprints only for matching
work. Set an initial-context budget and fail rather than truncate policy.

| Tool | Initial instructions | Packs in a project | Path-specific option |
| --- | --- | --- | --- |
| Claude Code | `CLAUDE.md` with the verified core import plus overlay and discovery | `.claude/skills/<publisher>-<module>/SKILL.md` | `.claude/rules/*.md` with `paths` |
| Codex | Combined core, overlay, and discovery in `AGENTS.md` | `.agents/skills/<publisher>-<module>/SKILL.md` | Nested `AGENTS.md` on the startup directory chain |
| Copilot | Combined `.github/copilot-instructions.md` | `.github/skills/<publisher>-<module>/SKILL.md` on supported surfaces | `.github/instructions/*.instructions.md` with `applyTo` |

Claude Code expands local `@` imports at startup; import the core, not every
module. Its managed-policy and managed-skills locations differ by operating
system. Confirm whether an external project import prompts on every supported
version, because declining it drops the policy.

Codex builds its project instruction chain from repository root to working
directory at startup. Make every module discoverable from the root and use the
core routing rule. Generate combined core and overlay text rather than assuming
an `@` import.

Copilot support differs between chat, code review, IDEs, and agents. Verify the selected surface against its [instruction support matrix](https://docs.github.com/en/copilot/reference/custom-instructions-support), [skill documentation](https://docs.github.com/en/copilot/concepts/agents/about-agent-skills), and [Visual Studio skill documentation](https://learn.microsoft.com/en-us/visualstudio/ide/copilot-agent-skills?view=visualstudio) (Visual Studio 2026 18.5 or later, agent mode). Where on-demand loading is unavailable, include the applicable packs in the initial adapter and account for their size.

## Update and roll back

Install releases side by side, verify the new one, and switch entry points before new sessions start. Keep previous releases for rollback. References inside an adapter must resolve to one versioned directory rather than a moving `current` path.

Keep running sessions on their selected release, including skill discovery. Claude Code and Codex can detect skill changes during a session; use isolated discovery locations, or wait for sessions to end and prevent new starts while shared entry points switch. An atomic filesystem rename alone does not update every tool's loaded context. See [Claude Code live change detection](https://code.claude.com/docs/en/skills#live-change-detection) and [Codex skills](https://developers.openai.com/codex/skills/).

Track rollout through device, package, or repository inventory. Set a maximum acceptable age for an offline release and record update attempts separately from successful updates. Test install, interruption, update, rollback, and uninstall on each supported operating system.

## Use the repository example

Start with [examples/organization-bundle](../../examples/organization-bundle/). Its build creates local adapters and a manifest; its installer verifies files, switches releases, detects drift, and uninstalls recorded files. The standalone tests run against temporary directories.

The example does not authenticate its own delivery, configure the assistant's entry points, implement session-aware activation, or validate the full nested blueprint schema. Its blueprint format is JSON only. Add those pieces for the selected deployment; do not describe copying its output as a completed rollout.

For repository distribution, include the flat module directory, blueprints,
catalog, core, overlay, and adapters. The example's absolute paths are tied to
an installation root, so repository output needs relative-path adapters.

## Acceptance checks

Run the common [verification cases](../adapting-in-an-organization.md#verify-before-rollout), plus clean installation, interrupted installation, tampered manifest and files, unresolved paths, entry-point imports that resolve outside the working directory, missing skill discovery, preservation of existing instructions, update during a session, rollback, drift, and uninstall. Test each supported operating system and client. Package verification and real assistant loading are separate checks.
