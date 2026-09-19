# Requirements

## MODULAR-DEFAULT-001 Load module bodies only when needed

Source: user's approved request in this conversation, including all three clients.

Supported installations start with core, catalog discovery and a loader command.
Module bodies enter context only for matching work, including dependencies.

Acceptance: default project and user entries for Codex, Claude Code and Copilot
contain no module rule bodies; executing their loader returns only the selected
dependency closure. Complete mode is explicit. Missing or invalid content fails.

## MODULAR-DEFAULT-002 Preserve instructions during migration

Source: approved migration proposal in this conversation and AGENTS.md's
installation integrity and preservation requirements.

Recognize conflicting complete installations and migrate verified managed
content explicitly, retaining unrelated instructions and refusing altered data.

Acceptance: tests cover inherited complete policy, all three tool entry points,
modified content, and preservation. Published distribution pins remain intact.

## MODULAR-DEFAULT-003 Report context through aiscb?

Source: user's request to replace `baseline?` with `aiscb?` and the approved
proposal distinguishing available and loaded modules.

Answer `aiscb?` from existing context with identity, source, mode, available
modules, loaded modules and overlays; disclose unknown state without reading.

Acceptance: the core and current guidance use `aiscb?`; adapter discovery states
its mode and available inventory without claiming that modules are loaded.
