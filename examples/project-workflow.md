# Specification-first project workflow

Adopt this block in the project's AGENTS.md, CLAUDE.md or Copilot instructions,
or as an organization overlay rule. Keep the installed policy block unchanged.

Before implementation, clarify the requested outcome and load applicable core,
overlay and modules. Write a specification containing scope, sourced
requirements, affected trust boundaries, decisions and observable acceptance
criteria. Obtain explicit approval before implementation. For small changes,
a short specification in the conversation is sufficient. Implement only the
approved scope, test against its acceptance criteria, and report unverified
requirements. Material requirement or scope changes need renewed approval.

Project specifications contain project decisions; do not copy the baseline into
them. Refer to applicable rule IDs. These instructions guide the assistant;
review and CI gates are still needed to enforce the workflow.
