# Changelog

Changes to aiscb's rules, installation, and organization setup. Each release
shows its publication date. Later installer updates are listed separately.

## [0.1.18](https://github.com/appsec-foundry/aiscb/releases/tag/aiscb-0.1.18) (2026-09-25)

- Split the web, login and cryptography rules into three modules, so a task
  loads only what it needs. Login rules bring cryptography and data handling
  with them.
- Shortened the core and removed rules that were stated twice.
- A confirmed decision stays confirmed: the assistant asks again only when the
  action, exposure or scope changes. Routine secure work no longer mentions aiscb.
- Added rules for data-only deserialization, explicit response fields, log
  injection, header values, and outbound URL paths.
- Loading modules takes less context.
- Added Kiro to the installer.
- appsec-advisor can now update existing aiscb installations through the
  signed installer.
- Added an upgrade command for organization rules. It prepares a separate
  draft and keeps custom rules. Organization packages may now consist of
  always-on rules only.
- Updates now take their files from the signed release, not from the repository.

**Updating:** Run the [Quick start](README.md#quick-start) once. Installations
from 0.1.17 and earlier cannot install this release through `--update`.

## [0.1.17](https://github.com/appsec-foundry/aiscb/releases/tag/aiscb-0.1.17) (2026-09-19)

- Installations for Claude Code, Codex and Copilot now load modules as needed
  by default. The installer contains everything required for this.
- Added migration of existing complete installations. Other instructions in
  the same files are kept.
- Replaced the status question with `aiscb?`. It shows the installation mode
  and which modules are available and loaded.
- Clarified what the core covers and when a Security note is required.

**Updating:** Close agent sessions, then run the Quick start. Guided setup
offers to migrate complete installations. Restart the clients and ask `aiscb?`.

## [0.1.16](https://github.com/appsec-foundry/aiscb/releases/tag/aiscb-0.1.16) (2026-09-19)

- Split the baseline into an always-loaded core and nine modules. Local
  installations can load modules as needed; the Quick start still installs
  all rules together.
- Added design rules for identifying what needs protection, checking access,
  and limiting permissions.
- Added rules for LLM agents, retrieval and memory, and MCP clients and servers:
  which actions are allowed, which tools may run, and who may access stored data.
- Expanded rules for handling untrusted files, restricting outbound requests,
  and preventing duplicate webhook actions.
- Added a local installer for modules and organization rules in Claude Code,
  Codex, and Copilot. It preserves existing project instructions.
- Clarified module names, when to load them, and how to add organization rules
  or request an exception for a specific task.

**Updating:** Run the current [Quick start](README.md#quick-start) once when
moving from 0.1.15 or an older installation. Older updaters cannot install this
release through `--update`.

**Loading modules as needed:** Install from a reviewed checkout. The assistant
must be able to run the supplied loader with Python 3.10+. Before rollout,
check that it loads the modules required by the task.

## [0.1.15](https://github.com/appsec-foundry/aiscb/releases/tag/aiscb-0.1.15) (2026-09-12)

- Made confirmation of riskier designs explicit: explain the safer option and
  the risk, then wait for the user's choice. Silence and default selections
  do not count as consent.
- Required the assistant to explain aiscb's role alongside the affected
  decision or question. The closing Security note covers risks the work
  creates or worsens.
- Clarified which directory setup changes and what its optional session-start
  notices do.

### Installer update (2026-09-14)

- Added user-level installation for Copilot Chat and agent mode in VS Code,
  alongside Copilot CLI.
- Fixed installation and status reporting when tools use custom configuration
  directories or existing instruction files.

## [0.1.14](https://github.com/appsec-foundry/aiscb/releases/tag/aiscb-0.1.14) (2026-09-09)

- Added signed updates. The installer verifies the release's signature and
  checks its files before running them.
- Specified safer login flows, token storage, and browser settings. Tightened
  rules for accepting request data and limiting CI and container permissions.
- Shortened risk reporting and adopted the heading **Security note (aiscb)**.
- Added an example and setup guide for distributing aiscb with organization rules.

**Updating from an earlier version:** Run the [Quick start](README.md#quick-start)
once to enable signed updates.

### Installer updates (2026-09-10 to 2026-09-12)

- Simplified setup choices and showed the installed version separately for
  each tool.
- Added an optional switch to start a new Claude Code or Codex session without
  the user-installed baseline. Project installations remain active.
- Added installation into local directories without Git and fixed selection
  of a different target directory.
- Fixed handling of existing Claude instructions and made incomplete
  installations visible in setup status.

## [0.1.12](https://github.com/appsec-foundry/aiscb/releases/tag/aiscb-0.1.12) (2026-09-04)

- Shortened the rules without changing their requirements or exceptions.

## [0.1.11](https://github.com/appsec-foundry/aiscb/releases/tag/aiscb-0.1.11) (2026-09-02)

- Clarified which risks belong in the Security note and which belong in the
  main answer. Removed passed checks from risk summaries.
- Made clear that development settings do not permit weaker security controls.
- Clarified that verification codes and links must not be exposed in the
  response, interface, or URLs returned to the requester.
- Required the assistant to explain aiscb's role when it first affects the work.
- Changed rule IDs to use lowercase `aiscb`.

## [0.1.10](https://github.com/appsec-foundry/aiscb/releases/tag/aiscb-0.1.10) (2026-08-30)

- Renamed the baseline from `aisec` to `aiscb` and added its source and licence
  to the baseline text. Guided setup offers to migrate older installations.
- Required the assistant to explain when aiscb leads to a security measure,
  safer approach, refusal, or confirmation request.
- Required a risk explanation and confirmation before retaining HTTP Basic
  authentication for interactive browser login.
- Added guided removal and an optional notice when a newer release is available.

### Installer update (2026-08-30)

- Made remote setup check downloaded files before running them. Updates use
  the verified Quick start.

## [0.1.9](https://github.com/appsec-foundry/aiscb/releases/tag/v0.1.9) (2026-08-29)

- First published release, using the baseline name `aisec-0.1.9`.
- Included secure-coding instructions for Claude Code, Codex, and Copilot,
  with separate handling of new applications and changes to existing ones.
- Added guided installation for a user account or project.
