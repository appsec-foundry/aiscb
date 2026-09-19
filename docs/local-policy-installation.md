# Install the modular baseline and an organization overlay

Use the same local installer for official policy and an organization package.
The core and official modules share one aiscb release. An organization overlay
has its own release and pins the exact aiscb content it extends.

This is a feature-branch integration, not yet a signed remote release. Use a
reviewed checkout and an existing project directory. Python 3.10 or newer is
required. Modular mode requires the assistant to execute the supplied Python
loader; it does not grant command-execution permission. If that tool is absent
or denied, affected work must stop. Use complete output for such clients.

The generated loader command uses POSIX shell quoting and Python 3.10+.
Automated execution was checked on Linux, not native Windows/PowerShell or
every IDE execution environment. For Windows modular use, validate a compatible
environment such as WSL; do not assume the native PowerShell command works.
Complete mode avoids that runtime command but still needs client loading tests.

## Install

```bash
python3 scripts/install.py codex --modular --into /path/to/project
```

Supported entry points are `AGENTS.md` for Codex, `CLAUDE.md` for Claude Code,
and `.github/copilot-instructions.md` for Copilot. Specify one or several of
`codex claude copilot`. The installer embeds core, optional overlay, discovery,
and a named loader command directly into a managed block. Existing unrelated
instructions are preserved; existing baseline integrations and changed managed
blocks cause a refusal rather than a second baseline or an overwrite.

This conflict check covers the targeted project entry points, not every inherited
user-level or managed policy. Inspect those separately before rollout; do not
combine old eager imports and new modular installation unintentionally. Status
checks installed files, not the complete instruction context a client actually
loads. Installation does not remove inherited policy.

Start a fresh session from the project root. Confirm `baseline?`, then exercise
a task requiring modules. Selecting `aiscb:agent-systems` must return both
`aiscb:llm-features` and `aiscb:agent-systems` before affected work. The loader
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

Replace `--modular` with `--complete` when the client cannot execute a loader. Then the managed
block contains the core, overlay, every configured module, and all referenced
blueprint values. This is generated from the same package, not separate policy.
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
| Configure a local stdio MCP server | `mcp-integrations` and its `data-boundaries` dependency; `supply-chain` when executing/installing its package |
| Build protected HTTP MCP | `mcp-integrations`, `data-boundaries`, `web-auth`; other matching modules still apply |
| Build RAG without agent actions | `retrieval-memory` and its `llm-features` dependency; no automatic agent module |
| Build an agent with persistent memory and MCP actions | All three domain modules plus their dependencies and other semantic matches |
| Use an existing MCP tool during unrelated editing | No MCP implementation trigger from tool use alone |

Run these scenarios with actual supported clients, including unavailable-loader
and corrupt-artifact cases. Unit tests prove dependency resolution and installed
content, not semantic selection. All discovery descriptions cost initial context;
selected module bodies and dependencies add context, and complete mode loads all.

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

The signed remote updater still handles the published complete bundle. It does
not update these local snapshots or fetch unpinned modular helpers. A modular
remote release needs a maintainer-approved signed distribution extension.
