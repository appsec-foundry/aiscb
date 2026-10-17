# Requirements

## SCOPE-001 Match affected work

Source: user's approval of the reviewed routing wording in this conversation;
baseline/aiscb-core.md, aiscb-MODULES-001 and aiscb-OM-001;
specs/requirements.md's existing unrelated-modules acceptance criterion.

Select semantic matches for the task and affected interfaces, including indirect
effects. Technology presence elsewhere in the application alone is not a match.
Uncertainty within the affected scope still requires loading; path matches and
dependency loading retain their existing behavior.

Acceptance: an isolated process change does not load web solely because HTTP
code exists elsewhere; an affected HTTP interface still requires web. Required
modules load before edits. Preserve the existing missing-policy behavior.

## SCOPE-002 Verify selection evidence and context cost

Source: user's approval of the scoped routing regression test and documentation
updates; AGENTS.md's verification and measurement requirements.

Add a process-only routing scenario with actual loader evidence and application
behavior checks. Its scoring must reject unnecessary web loading, omitted or
late required loading, and incorrect process behavior. Preserve existing
positive HTTP and dependency scenarios. Regenerate the complete artifact,
measure every component using o200k_base, and run make check.

Acceptance: deterministic tests accept the intended selection and reject those
failure cases; documentation distinguishes harness verification from actual
model evidence and records any missing model run.
