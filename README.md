# AI Secure Coding Baseline

[![GitHub Release](https://img.shields.io/github/v/release/appsec-foundry/aiscb)](https://github.com/appsec-foundry/aiscb/releases/latest)
[![check](https://github.com/appsec-foundry/aiscb/actions/workflows/check.yml/badge.svg)](https://github.com/appsec-foundry/aiscb/actions/workflows/check.yml)
[![codecov](https://codecov.io/gh/appsec-foundry/aiscb/graph/badge.svg)](https://codecov.io/gh/appsec-foundry/aiscb)
[![License: CC BY 4.0](https://img.shields.io/badge/License-CC%20BY%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-compatible-D97757?logo=anthropic&logoColor=white)](https://code.claude.com/)
[![GitHub Copilot](https://img.shields.io/badge/GitHub%20Copilot-compatible-000000?logo=githubcopilot&logoColor=white)](https://github.com/features/copilot)
[![OpenAI Codex](https://img.shields.io/badge/OpenAI%20Codex-compatible-412991?logo=openai&logoColor=white)](https://developers.openai.com/codex/)

aiscb gives AI coding assistants a shared secure-coding baseline: an always-on
core and task-specific modules, extended by an optional organization overlay.
Install it once instead of repeating security expectations in every prompt.

Current baseline: `aiscb-0.1.16`.

The 0.1.16 release is being prepared. Until it is signed and published, the
Quick start installs 0.1.15. Use a [reviewed checkout](#from-a-repository-clone)
for 0.1.16.

> **Scope and limits**
>
> aiscb guides how assistants design, write, test, and review code. Assistants
> can miss or ignore instructions. Keep code review, security tests, scanners,
> and CI checks in place. Enforce mandatory controls through permissions and
> other checks outside the model. Broader data-protection policies are out of scope.

## Quick start

Use the guided installer to install or update aiscb. The complete command verifies a pinned setup script and bundle before running them, and keeps existing instruction files:

```bash
curl --proto '=https' \
  --fail --silent --show-error \
  --output aiscb-setup.sh \
  https://raw.githubusercontent.com/appsec-foundry/aiscb/6deb1bd83c627a54c31570899a4dd1dc40f690c1/setup.sh &&
echo '7aa593cc0b69dd4c2f9d21dd9a7782bbf23e5f4922c772033ff070ac1956f3ac  aiscb-setup.sh' |
  sha256sum --check &&
bash aiscb-setup.sh
```

Choose your user account or a project directory, then the tools. The installer
preserves existing instructions and installs the complete baseline, with all
modules loaded together. Restart the assistant after installation.

Requires Bash, `curl`, `sha256sum`, and Python 3.10+. For modules loaded as
needed, use [Modular installation](#modular-installation). Claude Code users
can also use the [appsec-advisor](https://github.com/appsec-foundry/appsec-advisor)
plugin.

## Update

If enabled, the optional session notice links here when a newer release is available. Update a user-level installation from a terminal, outside the agent session:

```bash
python3 ~/.local/share/aiscb/install.py --update
```

The command verifies the signed release, then opens guided setup for the user installation and the current project. The new baseline applies to new sessions. If the command is unavailable or refuses the update, run the current [Quick start](#quick-start).

## Why this exists

AI coding assistants know many security practices but apply them inconsistently, especially when tests fail or deadlines press. aiscb gives different tools and sessions the same concrete rules.

Each rule names a mechanism: "Authorize on the server" is actionable; "be security-aware" is not. aiscb is neither a security standard nor a compliance checklist.

## See the difference

The same prompt, with and without aiscb. These are illustrative examples from individual sessions, not a benchmark or a guarantee. Click any screenshot to view it at full size.

### A small login app, with security choices made explicit

> Create a very small Flask real web application with a user login function

<table>
  <thead>
    <tr>
      <th width="50%">Without aiscb</th>
      <th width="50%">With aiscb</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td valign="top"><a href="docs/images/example_create_flask_without_aiscb.png"><img src="docs/images/example_create_flask_without_aiscb.png" width="100%" alt="Flask login app without aiscb: reports password hashing, a protected dashboard, and login tests; warns that the default secret key must be replaced before deployment."></a></td>
      <td valign="top"><a href="docs/images/example_create_flask_with_aiscb.png"><img src="docs/images/example_create_flask_with_aiscb_highlighted.png" width="100%" alt="Flask login app with aiscb: highlighted paragraphs describe CSRF protection, login rate limits, session protections, a required external secret key, and a Security note on TLS and rate-limit storage. Click for the original screenshot."></a></td>
    </tr>
    <tr>
      <td valign="top">Reports password hashing, protected routes, and login tests. Leaves a default secret key with advice to replace it before deployment.</td>
      <td valign="top">Also reports CSRF protection, login limits, session protections, and a required external secret key. A <strong>Security note (aiscb)</strong> identifies remaining deployment risks. Highlights added for comparison; click for the original screenshot.</td>
    </tr>
  </tbody>
</table>

### Security enters the design

> describe a UI implementation for a customer dashboard with 5 short bullet points

<table>
  <thead>
    <tr>
      <th width="50%">Without aiscb</th>
      <th width="50%">With aiscb</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td valign="top"><a href="docs/images/example_create_ui_without_aiscb.png"><img src="docs/images/example_create_ui_without_aiscb.png" width="100%" alt="Dashboard design without aiscb: five bullets covering layout, metric cards, data tables, charts, and UI states."></a></td>
      <td valign="top"><a href="docs/images/example_create_ui_with_aiscb.png"><img src="docs/images/example_create_ui_with_aiscb_highlighted.png" width="100%" alt="Dashboard design with aiscb: the highlighted fifth bullet requires server-side authorization on every fetch, scoped to the logged-in customer. Click for the original screenshot."></a></td>
    </tr>
    <tr>
      <td valign="top">Covers layout, components, and UI states.</td>
      <td valign="top">Also specifies server-side authorization scoped to the logged-in customer. Highlight added for comparison; click for the original screenshot.</td>
    </tr>
  </tbody>
</table>

### The agent pauses before writing custom crypto

> Create a simple encryption method in Python using a custom algorithm.

<table>
  <thead>
    <tr>
      <th width="50%">Without aiscb</th>
      <th width="50%">With aiscb</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td valign="top"><a href="docs/images/example_create_crypto_without_aiscb.png"><img src="docs/images/example_create_crypto_without_aiscb.png" width="100%" alt="Without aiscb, the agent writes a custom cipher to simple_cipher.py and warns that it is not cryptographically secure."></a></td>
      <td valign="top"><a href="docs/images/example_create_crypto_with_aiscb.png"><img src="docs/images/example_create_crypto_with_aiscb.png" width="100%" alt="With aiscb, the agent asks whether the custom encryption is a learning exercise or intended to protect real data, and offers Fernet as an established alternative."></a></td>
    </tr>
    <tr>
      <td valign="top">Writes a custom cipher, with warnings that it is not secure.</td>
      <td valign="top">Clarifies the intended use before writing code and offers an established library for real data.</td>
    </tr>
  </tbody>
</table>

The crypto example shows Claude Code with `aiscb-0.1.14` in the baseline session.

## Structure and context budget

The assistant always reads the [core](baseline/aiscb-core.md): how to scope
changes, protect secrets, handle security decisions, and review its work.
It loads modules as the task requires—for example, `web-auth-crypto` for a login.
The [catalog](baseline/catalog.json) lists when each module applies.
An organization can add rules through an overlay, but cannot relax the baseline.

| Component | Covers | Bytes | Tokens (`o200k_base`) |
| --- | --- | ---: | ---: |
| Core (always loaded) | Keep work within scope, load relevant modules, protect secrets, and review changes | 7,780 | 1,558 |
| `aiscb:web-auth-crypto` | Protect web content, authentication, webhooks, and cryptography | 5,189 | 1,040 |
| `aiscb:secrets-initialization` | Set up credentials and keys without shipping working defaults | 1,900 | 351 |
| `aiscb:deployment-environments` | Restrict CI and container privileges; separate development from production | 1,659 | 311 |
| `aiscb:llm-applications` | Validate model output and contain generated-code execution | 1,252 | 247 |
| `aiscb:llm-agents` | Check permissions for agent actions; limit tools, delegation, and retries | 2,033 | 401 |
| `aiscb:supply-chain` | Verify packages and downloads before use; pin external build tools | 1,173 | 223 |
| `aiscb:data-handling` | Handle untrusted files, restrict outbound requests, and limit resource use | 1,720 | 344 |
| `aiscb:llm-retrieval-memory` | Check access before retrieval and control what enters persistent memory | 1,666 | 325 |
| `aiscb:mcp-clients-servers` | Authorize MCP requests and control local server starts and credentials | 2,225 | 415 |
| Complete baseline | The core and every module in one file | 26,606 | 5,215 |

Counts cover rule text only; the catalog, loading instructions, and overlays
add context. `llm-agents` and `llm-retrieval-memory` also load `llm-applications`;
`mcp-clients-servers` also loads `data-handling`. Shared dependencies load once.

## What changes in practice

The assistant is instructed to:

- Apply security rules to the changed code and affected interfaces in an existing
  application; include applicable controls from the start in a new one.
- Check access on the server, protect secrets, and use established security libraries.
- Explain the risk and safer alternative before asking to weaken a control or
  adopt a materially riskier design.
- Treat retrieved content and tool results as data that cannot grant permissions.
- Test affected controls, including failure and abuse cases, and review the diff.
- Report concrete remaining risks; use **Security note (aiscb)** for risks the
  delivered work creates or worsens.

Read the [core](baseline/aiscb-core.md) and [modules](baseline/modules/) for the
rules, or the [requirements catalog](specs/requirements.md) for applicability
and test coverage.

## Using it

### From a repository clone

From a reviewed checkout, install its version with:

```bash
make setup ARGS=--offline
```

Choose a user installation or a project. Inside Git, the project is the nearest
repository root; otherwise it is the current directory. Existing instructions
are preserved. Replacing an edited baseline requires confirmation and creates
a backup. Restart the assistant after installation.

Other commands:

```bash
make status ARGS=--offline    # show installation status
make uninstall               # preview and remove the project installation
make help                    # list available commands
```

Omit `--offline` in setup to check for a newer published release. The optional
update notice checks at most daily and never installs automatically.

See the [integration guide](docs/agent-integration-verification.md) for client
setup, including Visual Studio personal instructions.

### Modular installation

To load only the modules a task needs, run this from a reviewed checkout:

```bash
python3 scripts/install.py codex --modular --into /path/to/project
```

Replace `codex` with `claude` or `copilot`, or name several tools. The assistant
must be allowed to run the supplied Python 3.10+ loader. The installer preserves
unrelated instructions. Restart the assistant after installation.

Modular loading needs verification in the clients you use before rollout;
installer tests do not establish that a model selects the right modules.
If command execution is unavailable, use `--complete`, provided the client's
instruction limit can hold the entire baseline. Remote and user installations
use the complete baseline.

For an organization overlay, package verification, updates, and removal, see
[local installation and overlays](docs/local-policy-installation.md).

### Temporarily disable the baseline

Claude Code and Codex user installations support an optional session switch.
Enable **dynamic loading** in guided setup, then start a new session:

```bash
AISCB_DISABLE=1 claude
AISCB_DISABLE=1 codex
```

Start normally to restore the baseline. The switch does not disable project
installations, separate overlays, or other permissions and instructions.
See [setup and troubleshooting](docs/session-switch.md).

### Coding-agent compatibility

| Client | Project instruction file |
| --- | --- |
| Claude Code | `CLAUDE.md` |
| Codex | `AGENTS.md` |
| GitHub Copilot | `.github/copilot-instructions.md` |

Support varies between CLI, IDE, cloud agent, review, and completion features.
Check the [integration guide](docs/agent-integration-verification.md) for the
surface you use, instruction limits, and loading checks.

### Verify it loaded

Start a fresh session after installing 0.1.16. Ask `baseline?`; the
answer should include `aiscb-0.1.16`,
its source, loaded modules, and any overlays. Until the new release is published,
the remote Quick start installs 0.1.15, so that is the expected answer there.

The answer reports what the assistant sees in context; it does not prove that
all rules are followed. Check the client's loaded instructions too, as described
in the [verification guide](docs/agent-integration-verification.md).

## Adapting it

For organization rules, keep the official baseline and add a separately
versioned overlay, such as `acme-sec-1.0.0`. An overlay may add or narrow rules;
it cannot disable baseline controls. See the
[organization guide](docs/adapting-in-an-organization.md) for setup, examples,
and how explicit exceptions for an individual task work.

If you change the baseline itself, retain attribution and existing rule-group
IDs, and give the derived baseline its own versioned identity. Application
requirements belong in tests, CI, review gates, and runtime controls.

## Evidence and related guidance

Research suggests that explicit, concrete, persistent security instructions improve AI-assisted coding, but do not replace enforcement ([Yan et al., 2025](https://arxiv.org/abs/2506.23034), [Gloaguen et al., 2026](https://arxiv.org/abs/2602.11988), [Kharma et al., 2026](https://arxiv.org/abs/2605.24298), [Chen et al., 2026](https://arxiv.org/abs/2604.20200), [Sharma, 2026](https://arxiv.org/abs/2603.00822)).

- The [OWASP Top 10:2025](https://owasp.org/Top10/2025/), [LLM Top 10](https://genai.owasp.org/llm-top-10/), and [Agentic Top 10](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/) describe relevant risks.
- The OWASP [Secure Coding with AI Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secure_Coding_with_AI_Cheat_Sheet.html) and OpenSSF [instruction guide](https://best.openssf.org/Security-Focused-Guide-for-AI-Code-Assistant-Instructions) offer further guidance.
- The optional [Claude Code gate](examples/claude-code-gate/) blocks some unsafe patterns; contextual issues still require review or CI.

These resources neither certify aiscb nor define its coverage. Check time-sensitive advice against current sources.

The [LLM and agentic alignment review](docs/owasp-llm-agentic-review.md) compares
the current 2026 OWASP lists with the modules, including partial coverage and
remaining gaps. It is not a compliance claim or model-test evidence.

## Development

Normative rule text lives in `baseline/aiscb-core.md` and the cataloged files under
`baseline/modules/`; the complete file under `dist/dev/aiscb-0.1.16/` is
generated from those sources with `make build-full-baseline`. See
[Structure and context budget](#structure-and-context-budget) for current
token measurements.

The provisional budgets are roughly 1,500 tokens for the core and 4,100 for
the complete baseline. The expanded rules currently
exceed them by 58 and 1,115 tokens respectively; these are visible design targets,
not a reason to silently drop controls. Adapter discovery and overlay text add
to the actual session context.

[`specs/requirements.md`](specs/requirements.md) maps rule groups to tests. Behavior changes follow the workflow in [`specs/README.md`](specs/README.md); editorial and repository-only changes need no change specification.

Run `make check` after changing the baseline, specifications, test metadata, or harness. For model tests, start with `make test-smoke`, then run affected rules with `make test-rule RULE=<rule group>`. See [tests/README.md](tests/README.md).

[docs/releasing.md](docs/releasing.md) describes how a release is published, from signing the bundle to updating the Quick start block.

## License

[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). You may use, share, and adapt the material with attribution. See [LICENSE](LICENSE).
