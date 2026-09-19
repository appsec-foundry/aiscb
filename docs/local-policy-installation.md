# Install the modular baseline and an organization overlay

Use the same local installer for official policy and an organization package.
The core and official modules share one aiscb release. An organization overlay
has its own release and pins the exact aiscb content it extends.

Modular installation is the default for reviewed checkouts and signed releases
from 0.1.17 onward, at project or user scope.
Python 3.10 or newer is required. Modular mode requires the assistant to execute
the supplied Python loader; it does not grant command-execution permission. If that tool is absent
or denied, affected work must stop. Use complete output for such clients.

The generated loader command uses POSIX shell quoting and Python 3.10+.
Automated execution was checked on Linux, not native Windows/PowerShell or
every IDE execution environment. For Windows modular use, validate a compatible
environment such as WSL; do not assume the native PowerShell command works.
Complete mode avoids that runtime command but still needs client loading tests.

## Install

```bash
python3 scripts/install.py claude codex copilot --into /path/to/project
python3 scripts/install.py claude codex copilot --user
```

Supported entry points are `AGENTS.md` for Codex, `CLAUDE.md` for Claude Code,
and `.github/copilot-instructions.md` for Copilot. Specify one or several of
`codex claude copilot`. The installer embeds core, optional overlay, discovery,
and a named loader command directly into a managed block. Existing unrelated
instructions are preserved; existing baseline integrations and changed managed
blocks cause a refusal rather than a second baseline or an overwrite.

Project setup also checks known user and ancestor instruction locations for
inherited complete policy and refuses the conflict before writing. Close sessions
and migrate the user installation first with `--user --migrate`, then any old
project with `--into /path/to/project --migrate`. Only unchanged, recorded managed
content (or the exact bundled complete source) is eligible. Other instructions
are preserved; unowned imports, modified policy and unexpected symlinks are refused.
For a managed dynamic installation, migration also removes its exact complete-text
injection hooks while preserving unrelated hooks. A modified injection hook is
refused; it cannot silently continue loading all modules after migration.
Custom managed policies, additional configured instruction directories and IDE profile
settings still need inspection; status verifies files, not the whole client context.

User entries are `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md` and
`~/.copilot/instructions/secure-coding.instructions.md` with `applyTo: "**"`.
The existing tool configuration-home overrides are respected; Copilot also gets
the default VS Code personal instruction file when its CLI home differs.
User snapshots and their record live under `~/.aiscb/`. Use `--status --user` or
`--uninstall --user` for this scope. The installed updater is `~/.aiscb/install.py`.

Start a fresh session from the project root. Confirm `aiscb?`, then exercise
a task requiring modules. Selecting `aiscb:llm-agents` must return both
`aiscb:llm-applications` and `aiscb:llm-agents` before affected work. The loader
verifies the pinned snapshot, rejects unknown IDs and invalid dependencies,
and emits nothing on failure. It cannot establish that the assistant invokes
it or follows the rules: test actual clients before organizational rollout.

Official instruction references:
[Codex](https://developers.openai.com/codex/guides/agents-md/),
[Claude Code](https://code.claude.com/docs/en/memory), and
[Copilot](https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions).
The direct loader avoids relying on differing skill-discovery behavior.

For Claude, keep the explicit CLAUDE.md entry even though recent releases can
conditionally read AGENTS.md. For Copilot, select the exact CLI/IDE/cloud-agent
surface and confirm it can run the loader; Chat, code review and inline
completion are not interchangeable. Complete mode also requires the entire
block to fit the surface's instruction limits. See the
[client compatibility evidence](agent-integration-verification.md#current-branch-evidence-2026-09-19).

Adopt the [specification-first workflow](../examples/project-workflow.md) in
project instructions when required. The example organization overlay includes
it already; the official security core does not mandate an organization's
project-management process. The installer preserves project workflow text.

## Add organization policy

Keep a short always-on `overlay.md` with organization identity, the exact
aiscb release, namespace authority, and only universally applicable rules.
Put thematic rules in cataloged organization modules. Blueprints provide
values for those rules and load with their referring modules. Neither can
relax aiscb, widen the user's task, or grant tools additional permissions.

Adapt `examples/organization-bundle/`, then build a package:

```bash
python3 examples/organization-bundle/build.py \
  --aiscb baseline --source /path/to/organization-source \
  --out /path/to/new-bundle --install-root /path/to/managed-root
```

The builder prints the manifest digest. The organization's release process
must authenticate both that digest and the distribution of this installer.
Consumers receive the digest separately through that trusted channel:

```bash
python3 scripts/install.py codex --modular --into /path/to/project \
  --organization /path/to/new-bundle \
  --organization-sha256 TRUSTED_MANIFEST_DIGEST
```

The installer verifies the entire organization manifest and files, validates
the official rule set and routing, and installs one merged snapshot. It
replaces the example's build-machine references with package-local references;
the loader returns blueprints with modules. No model-supplied URL is fetched.
The example's separate managed-machine installer still requires its configured
install root; the project installer above relocates verified content itself.

Select `--complete` when the client cannot execute a loader. Then the
entry contains the core, overlay, every configured module, and all referenced
blueprint values. This is generated from the same package, not separate policy.
Fresh official complete installs retain the legacy installer and session-switch
compatibility. A managed modular installation can switch to complete and back by
rerunning setup; returning from a legacy complete installation requires `--migrate`.
The example gateway also receives complete output until a remote loader exists.

## Update, verify, remove

Rerun the same installation command with the reviewed checkout or new trusted
organization package. Snapshots are stored by full manifest digest under
`.aiscb/releases/`; old ones remain for existing sessions. Do not update tool
entry points while sessions are running: clients may reread instructions.
Close affected sessions before activation and restart afterward.

Updating any tool also updates all previously managed tool entry points to the
same release and format; drift in any of them refuses the update. Roll back by
rerunning the installer from the previous reviewed checkout or with the previous
authenticated organization package, using the desired format. Retained snapshots
alone are not an automatic rollback command. Do not edit the installation record.

The loader command contains an absolute project path. Do not commit a generated
entry point as a portable installation for other checkout locations: rerun setup
at each target location. Repository-wide portable adapters remain rollout work.

### New-module acceptance scenarios

| Work | Required selection beyond core |
| --- | --- |
| Configure a local stdio MCP server | `mcp-clients-servers` and its `data-handling` dependency; `supply-chain` when executing/installing its package |
| Build protected HTTP MCP | `mcp-clients-servers`, `data-handling`, `web-auth-crypto`; other matching modules still apply |
| Build RAG without agent actions | `llm-retrieval-memory` and its `llm-applications` dependency; no automatic agent module |
| Build an agent with persistent memory and MCP actions | All three domain modules plus their dependencies and other semantic matches |
| Use an existing MCP tool during unrelated editing | No MCP implementation trigger from tool use alone |
| Change the system prompt of an application's LLM summarizer | `llm-applications`; other task-specific matches still apply |
| Fix ordinary code or a documentation typo using the assistant's tools | No `llm-applications` trigger from the assistant's prompts, tool use, or code generation alone |
| Change a login flow in an application without LLM features | `web-auth-crypto` and other task-specific matches; no `llm-applications` trigger from assistant activity alone |
| Change archive extraction in an application without LLM features | `data-handling` and other task-specific matches; no `llm-applications` trigger from assistant activity alone |
| Add file encryption or signature verification without a web endpoint | `web-auth-crypto`; the cryptography trigger does not require web work |
| Select internal documents for a chatbot's answers | `llm-retrieval-memory` and `llm-applications`, even if the request never says RAG |
| Store, replace or delete an application's persistent agent memories | `llm-retrieval-memory` and `llm-applications`; `llm-agents` when model-directed actions also change |
| Optimize an ordinary SQL query or add a database index | No `llm-retrieval-memory` trigger without an LLM retrieval or memory feature; `data-handling` still applies |
| Change a CI action version or container base image | `supply-chain`; also `deployment-environments` when container configuration or runtime controls are affected |
| Change CI job permissions or isolate untrusted PR code | `deployment-environments`; also `supply-chain` when external components change |
| Make a debug route, development server or mock service reachable | `deployment-environments` and other matching modules |
| Change only an isolated unit-test fixture's expected value | No `deployment-environments` trigger from test data alone; reassess if activation, exposure or production separation changes |

Run these scenarios with actual supported clients, including unavailable-loader
and corrupt-artifact cases. Unit tests prove dependency resolution and installed
content, not semantic selection. All discovery descriptions cost initial context;
selected module bodies and dependencies add context, and complete mode loads all.

The module names changed during this unpublished branch trial. Reinstall from
the reviewed checkout and start a fresh session to use the current names.
Old IDs are rejected by the new loader; retained snapshots keep their own IDs.

```bash
python3 scripts/install.py --status --offline --into /path/to/project
python3 scripts/install.py --uninstall --into /path/to/project
```

Status verifies stored content and managed blocks. Uninstall removes only
unchanged managed blocks and their installation record; user text and snapshots
remain. Snapshot cleanup is a separate explicit operation after sessions end.
Modified managed blocks are not silently deleted. An interrupted installation
can leave a snapshot without activation; inspect status and entry points before
retrying. The installer does not promise a transaction across several tools.

Protect policy files and entry points with the same organization-managed write
permissions. Hashes detect drift relative to the pinned instructions; they
cannot defend against an actor allowed to replace both instructions and loader.
Project-local policy is not a substitute for managed organizational enforcement.

The signed remote updater verifies the release before running its guided setup.
From 0.1.17 onward, the signed installer embeds modular sources and helpers; it
installs verified snapshots without fetching replacement code. User installations
keep the updater at `~/.aiscb/install.py`. Organization packages still need an
explicit approved package and digest.
