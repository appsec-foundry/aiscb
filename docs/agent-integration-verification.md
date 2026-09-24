# Build and verify organization baseline integrations

Use this guide when another coding agent builds an installer or repository adapter for an organization-specific baseline. The result must deliver the reviewed baseline, overlay, and always-needed catalog to each selected client, preserve existing instructions, and report separately whether the client is installed, configured, and observed loading the release. See [the organization design](adapting-in-an-organization.md) and [the local bundle rollout](rollout-paths/local-bundle.md) for release and policy-pack design.

## Define the target before writing files

Record the exact client surfaces: Claude Code CLI, Claude Code VS Code extension, Codex CLI, Codex IDE extension, Copilot CLI, Copilot Chat/agent in VS Code, Copilot Chat in Visual Studio, Copilot on GitHub.com, and any code-review surface. “VS Code” can also mean running a CLI in its integrated terminal; that is still the CLI surface. Visual Studio is a separate Windows IDE, not VS Code. Do not infer one surface from another. Record supported versions, operating systems, VS Code profiles, local versus SSH/WSL/container windows, project versus user versus managed scope, and the approved release ID and digest.

Build the adapters from one verified release. Put the baseline and short organization overlay in the initial instruction entry point. Put task-specific packs in skills or path-specific files only when the selected surface supports their discovery. A skill selected by the model is not a reliable substitute for the rules that must be present at the start of every applicable request. If the initial content can exceed a client’s instruction limit, fail the build instead of shipping a truncated policy.

## Connect the initial instructions

| Client and scope | Entry point to generate | What to check |
| --- | --- | --- |
| Claude Code, project | `CLAUDE.md` or `.claude/CLAUDE.md` containing combined text, or a local `@path` import | Current versions conditionally load AGENTS.md too; keep explicit imports for older/restricted sessions. External imports can require approval. |
| Claude Code, user or managed | `~/.claude/CLAUDE.md` or a [managed-policy `CLAUDE.md`](https://code.claude.com/docs/en/memory#deploy-organization-wide-claudemd) | Resolve the actual Claude configuration directory. Managed locations differ on macOS, Linux/WSL, and Windows. |
| Codex, project | Combined text in root `AGENTS.md`; use a nested `AGENTS.md` only for work started in its directory chain | `AGENTS.override.md` can replace `AGENTS.md` in the same directory. Codex has no portable `@` file import. |
| Codex, user | Combined text in `$CODEX_HOME/AGENTS.md` (default `~/.codex/AGENTS.md`) | `AGENTS.override.md` at that level replaces the normal file. Codex CLI and the IDE extension share configuration layers; verify the actual home and trusted project. |
| Copilot, project | Combined text in `.github/copilot-instructions.md` | This is the broadest repository entry point across Copilot surfaces. A Markdown link to a policy file is a reference, not an automatic import. |
| Copilot CLI, user | `~/.copilot/copilot-instructions.md` or `~/.copilot/instructions/*.instructions.md` | Resolve `COPILOT_HOME` where supported. Test the CLI itself; an IDE extension does not prove the CLI is installed. |
| Copilot Chat/agent in VS Code, user | `~/.copilot/instructions/*.instructions.md` with YAML frontmatter such as `applyTo: "**"`, or organization instructions enabled in VS Code | `applyTo` matches working files. Test both a request with a matching file and a plain chat request. For every-request policy in a repository, prefer `.github/copilot-instructions.md` or verified organization instructions. |
| Copilot Chat in Visual Studio, project | `.github/copilot-instructions.md`; `.github/instructions/*.instructions.md` can add path-specific rules | Do not assume that Visual Studio Chat reads `AGENTS.md`: the [GitHub support matrix](https://docs.github.com/en/copilot/reference/custom-instructions-support) does not list it for this surface. |
| Copilot Chat in Visual Studio 2026, user or organization | Personal `%USERPROFILE%\copilot-instructions.md`; organization custom instructions for organization repositories in Visual Studio 18.8 or later | This is a Windows IDE entry point, separate from VS Code’s `~/.copilot/instructions`. Check the selected Visual Studio version and the organization-instructions option. |
| Copilot Chat on GitHub.com | Repository or organization custom instructions, according to the selected feature | Personal and organization instructions have different support by feature; check the [current matrix](https://docs.github.com/en/copilot/reference/custom-instructions-support). |
| Kiro, project | Combined text in root `AGENTS.md`, the same block the Codex adapter writes | [Kiro steering](https://kiro.dev/docs/steering/) always includes `AGENTS.md` and does not apply inclusion modes to it. A `.kiro/steering/` file with the same policy loads in addition to `AGENTS.md`; the installer refuses a complete copy there. The modular loader needs shell execution approved in Kiro. |
| Kiro, user | Combined text in `~/.kiro/steering/AGENTS.md` | Kiro reads user steering from `~/.kiro/steering/`, not from `~/.codex/AGENTS.md`. Global steering applies to the IDE and CLI, not to Kiro on the web. |

For Claude, use a real import only where Claude Code supports it. For Codex and Copilot, generate the actual combined instruction text at their entry points; do not assume `@`, a Markdown link, or a path string loads another file. If an entry point already exists, merge the new block without deleting unrelated instructions and maintain one identifiable managed block. Refuse ambiguous ownership, symlink targets outside the intended root, invalid encoding, and content drift; back up any file the installer is authorized to replace. Make install, update, and uninstall operate only on owned blocks or files.

The build order is: verify the release; render the initial text and each adapter; check size, frontmatter, and imports; stage all files; inspect existing entry points and ownership; install without following unexpected links; re-read the installed bytes and verify their digest; record owned paths and blocks. A VS Code personal instruction file must contain the rendered policy after its frontmatter, for example:

```markdown
---
applyTo: "**"
---

<rendered baseline and organization overlay>
```

The angle-bracket line is a build placeholder, not an instruction to ship. Test whether this adapter reaches plain chat as well as file-related requests on the supported VS Code version.

These entry points guide an agent; they do not enforce a security policy. Keep deterministic controls such as permissions and CI checks outside the prompt. For a managed machine, authenticate the release before executing its installer and protect both the release and entry points against unauthorized edits.

## Detect the client in the environment that will run it

Represent state as **not found**, **installed but inactive**, **configured but unverified**, **verified loaded**, or **unsupported on this surface**. Do not report “active” from a file on disk, an installed extension, or a command on `PATH` alone. An unknown profile, disabled extension, remote extension host, or unavailable client must remain unverified.

For CLIs, resolve `claude`, `codex`, or `copilot` on the `PATH` of the process that will launch the client. Then inspect the actual configuration home and instruction entry point. A CLI in the VS Code integrated terminal uses the terminal’s environment; test it as a CLI. The [Claude Code VS Code extension](https://code.claude.com/docs/en/vs-code#run-cli-in-vs-code) bundles its own runtime and does not install `claude` on shell `PATH`.

For VS Code extensions, inspect the **current window and profile**, not only `~/.vscode/extensions`. The official extension IDs are `anthropic.claude-code`, `openai.chatgpt`, and `GitHub.copilot-chat` for their respective chat surfaces. `code --list-extensions --show-versions --profile <name>` can inventory a known local profile; it lists installed extensions, including ones disabled for the workspace. VS Code does not sync extensions into SSH, WSL, or dev-container windows. In such windows check the Extensions view’s local/remote location and whether the extension is enabled and its panel starts. If `code` is absent from shell `PATH`, the GUI extension may still be installed. If an extension folder exists, the current profile may still not use it. Use the [VS Code extension and CLI documentation](https://code.visualstudio.com/docs/configure/extensions/extension-marketplace) for these distinctions.

For Visual Studio, check the actual IDE and Copilot Chat panel, signed-in entitlement, and supported version. Do not treat a VS Code extension, `code` command, or Copilot CLI binary as evidence for Visual Studio. Organization instructions require a GitHub organization repository and can be turned off under **Tools → Options → GitHub → Copilot → Copilot Chat**. Personal instructions use the Windows user profile path above; inventory it without overwriting an existing preferences file.

Check instruction-file location from the client’s point of view. A local user-home path may not be the user home of a remote agent. VS Code’s Agent Host reads personal instruction files from supported folders such as `~/.copilot/instructions`, rather than arbitrary VS Code profile data; `chat.instructionsFilesLocations` is deprecated for that host. Check settings that can disable instruction discovery, including `chat.useAgentsMdFile`, `chat.includeApplyingInstructions`, and `github.copilot.chat.organizationInstructions.enabled` when those routes are used. VS Code combines applicable files, so detect duplicate or conflicting baseline copies.

## Prove that the release actually loaded

Perform these checks in a fresh session opened from the intended repository and directory, using the intended profile or remote window. A self-reported ID is a smoke test; corroborate it with the client’s source view. Record the client version, surface, scope, release ID, expected source path, observed source path, and result without recording prompts or secrets.

| Surface | Loading evidence |
| --- | --- |
| Claude Code CLI or its own VS Code panel | Run `/context` and inspect **Memory files**. `/memory` shows available locations, including files that may not exist; it is not proof of loading. Check imported paths and any external-import approval. |
| Codex CLI | Start from the target directory and ask which instruction files are active; verify the reported sources against the global and root-to-working-directory chain. Restart after changing files. For a stronger audit, use the official [AGENTS.md verification guidance](https://learn.chatgpt.com/docs/agent-configuration/agents-md#verify-your-setup). |
| Codex IDE extension | Open the Codex sidebar in the intended VS Code window, start a new local chat, and perform the same source question. Verify the selected workspace and the shared `config.toml` layers; do not count a Copilot Chat response as Codex evidence. |
| Copilot Chat/agent in VS Code | Open Chat **Diagnostics** and inspect loaded instruction files and errors. Inspect the response’s **References** list or the actual model-request instructions for the expected file; a plain-chat and a matching-file test are both required for `*.instructions.md`. Do not count inline code completions: VS Code custom instructions do not apply to them. |
| Copilot Chat in Visual Studio | Start a new chat for the intended solution and inspect the **References** list for the repository, personal, or organization instruction source. Confirm organization instructions are enabled when that route is used. Test the intended Chat or review feature separately. |
| Kiro CLI | From the project root, run `kiro-cli chat --no-interactive --trust-tools= "aiscb?"`. With no tools trusted, the answer can only come from the loaded context. |
| Copilot CLI or GitHub.com | Start a fresh interaction on that surface and inspect its available instruction references or diagnostics. Test the exact feature being rolled out: Chat, cloud agent, and code review do not share one support matrix row. |

Use a harmless probe that asks for organization baseline IDs and their already-loaded source files **from the current instruction context, without opening files**. Keep the expected ID out of the question. Compare the answer with the approved release, then inspect the source view above. A correct answer alone can be guessed or learned from repository search; a visible source alone does not prove the model follows the rule. For a behavior test, run one representative, reversible task in an isolated fixture and inspect the resulting diff.

## Acceptance cases for the installer

### Complete release 0.1.16 (2026-09-19)

The published bundle was downloaded over HTTPS and its maintainer signature,
file sizes and hashes verified. A changed installer was rejected. Fresh project
installations with Claude Code 2.1.278 and Codex CLI 0.154.0 sent the complete,
unchanged baseline in their API requests to a local test server. The test used
isolated homes and no real credentials or model calls.

This verifies loading of the complete release on those two CLI versions. It
does not verify model compliance, modular selection, or Copilot/IDE loading.

### Current branch evidence (2026-09-19)

Default project and user installations now use core plus discovery and a loader.
`scripts/test_modular_setup.py` exercises all three adapters, dependency output,
complete-to-modular migration, inherited and additional complete instructions,
modified sources/hooks/updaters, configuration-home overrides, symlinks,
interactive setup, and standalone staged/installed installers. The existing
complete-mode compatibility and loader integrity tests still run in `make check`.

`python3 scripts/probe_modular_clients.py` was run with Claude Code 2.1.278,
Codex CLI 0.154.0 and Copilot CLI 1.0.83. All twelve combinations passed:
three clients, project/user scope, and launch from project root/subdirectory.
Captured API requests contained the exact core and the available-module catalog,
and no module rule bodies. The probe uses isolated homes, a loopback API fixture
and artificial test credentials; it makes no real model calls or external writes.

This verifies initial instruction loading on those CLI versions. Loader tests
execute each generated command and verify the selected dependency closure and
failure behavior. Neither proves semantic module selection, the model's status
answer, or IDE loading. Copilot in VS Code Agent Mode still needs a fresh-window
test of References/Diagnostics and an allowed loader execution; other Copilot
surfaces remain separately unverified. No paid model cases were run for this
delivery change; do not treat a fixture response as evidence of model compliance.

The repository's Copilot entry is a short read-and-load instruction, not an
automatic import. A surface unable to read files or execute the loader cannot
use this adapter. Complete mode is an alternative only where the full block fits
and is actually loaded. There is no automatic IDE/feature capability detection.
Do not claim inline-completion or every Copilot code-review surface support.

Claude's documented default loads CLAUDE.md instead of AGENTS.md when both
exist. An explicit `@AGENTS.md` import remains supported and is deduplicated when
AGENTS is also discovered. In installed projects that independently embed the
same policy in both files, a non-default setting loading both may duplicate
context; inspect `/context` and select one integration. Source:
[Claude memory and AGENTS behavior](https://code.claude.com/docs/en/memory#agentsmd).

Before release, supplement the recorded startup checks with actual model tasks:
MCP-only and RAG tasks, multi-module selection, missing
loader, corrupted source, new session after update, and preserved user policy.
Record exact client versions, execution permissions and instruction-size limits.

### Kiro project installation (2026-09-24)

Tested with Kiro CLI 2.24.0 on Linux and no global Kiro steering. A project
installation (`install.py kiro --into`, which writes the same `AGENTS.md` block
as `codex`) answered `aiscb?` with `aiscb-0.1.18`, modular mode, all eleven
modules available, none loaded, and no overlays; no tools were trusted for this
question. Asked for a Flask login endpoint, Kiro ran the loader for
`authentication`, `data-handling`, and `cryptography` before writing code.

A user installation (`install.py kiro --user`) into an isolated home wrote
`~/.kiro/steering/AGENTS.md`. Kiro CLI started with that home in a project
without its own `AGENTS.md` answered `aiscb?` correctly and ran the loader for
the same login task.

This shows that Kiro CLI loads the baseline and runs the loader. It does not
show that Kiro selects the right modules: in three of seven login runs it did
not load `aiscb:web`. The Kiro IDE was not tested, nor a Windows IDE opening a
WSL project.

### Remaining real-client acceptance cases

- Fresh checkout, existing unrelated instructions, edited managed block, foreign symlink, unreadable or invalid entry point, and uninstall after a manual edit.
- No CLI but the VS Code extension is active; CLI on `PATH` but no extension; extension installed but disabled; another VS Code profile; SSH/WSL/container window; Visual Studio installed without Copilot Chat; missing login or organization entitlement.
- Codex global and project `AGENTS.override.md`; Claude external import declined; Copilot `applyTo` with matching file and with no file; organization instructions disabled in VS Code.
- Correct release, stale release, duplicated release, missing pack, failed import, and content over the initial instruction budget. In each case assert the reported state and what a new session actually loads.

Do not claim rollout success until at least one real session per selected client and environment shows the expected instruction source and the behavior probe passes. Re-run the loading check after a client update or release switch. See the [common verification cases](adapting-in-an-organization.md#verify-before-rollout) for release and policy-loading checks.

## Primary product references

- [Claude Code memory, imports, and managed instructions](https://code.claude.com/docs/en/memory); [Claude Code in VS Code](https://code.claude.com/docs/en/vs-code).
- [Official OpenAI documentation: Codex `AGENTS.md`](https://learn.chatgpt.com/docs/agent-configuration/agents-md); [Codex IDE extension](https://learn.chatgpt.com/docs/codex/ide); [Codex configuration layers](https://learn.chatgpt.com/docs/config-file/config-basic).
- [GitHub Copilot instruction support matrix](https://docs.github.com/en/copilot/reference/custom-instructions-support); [VS Code custom instructions and diagnostics](https://code.visualstudio.com/docs/agent-customization/custom-instructions); [VS Code extension management](https://code.visualstudio.com/docs/configure/extensions/extension-marketplace); [Visual Studio personal instructions](https://learn.microsoft.com/en-us/visualstudio/ide/copilot-context-overview?view=visualstudio) and [organization instructions](https://learn.microsoft.com/en-us/visualstudio/releases/2026/release-notes). Official extension listings: [Claude Code](https://marketplace.visualstudio.com/items?itemName=anthropic.claude-code), [Codex](https://marketplace.visualstudio.com/items?itemName=openai.chatgpt), [Copilot Chat](https://marketplace.visualstudio.com/items?itemName=GitHub.copilot-chat).
