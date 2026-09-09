# How the baseline changes

`secure-coding-baseline.md` in the repository root is the product: one file,
shipped to coding assistants as it is. Nothing under `specs/` is normative for
an assistant; it only records what the baseline contains and how it changes.

- `requirements.md`: a readable catalog of the current rule groups, acceptance
  criteria, model evidence, and known gaps.
- `changes/<name>/`: a change being worked on.
- `archive/<date>-<name>/`: a change that is finished.

## Where requirements come from

Three sources, and no fourth: what the user asked for, what this repository
already documents, or a commit that clearly established the behavior. Name the
source for each requirement.

If none of them settles a question, ask. Do not fill the gap with a rule, an
exception, a test obligation, or a scope extension of your own. An example may
make a sourced rule easier to see; it must not add to it.

## When a change needs its own directory

A change needs its own directory only when it changes
`secure-coding-baseline.md` in a way that could alter how an assistant behaves.
Repository tooling, configuration, workflow, documentation, harness, and
test-only changes do not get a change directory while the normative baseline
stays unchanged. Typos and rewrapping do not need one either. If you cannot tell
whether new baseline wording changes behavior, assume it does.

A change directory holds three short files (templates in `changes/README.md`,
worked examples in `archive/`, the smallest being
`2026-08-15-reference-baseline-from-agents/`):

- `proposal.md`: problem, goal, non-goals, what it breaks.
- `requirements.md`: what the baseline must do, with a source per requirement.
- `tasks.md`: the work, ticked off as it happens.

## Running a change

1. Propose the change (its requirements, their sources, and the files they land
   in) and wait for the user's answer. Nothing under `specs/` is written before
   that answer; `scripts/spec_guard.py` turns identifiable writes into a
   permission prompt.
2. Write the three files.
3. Change the baseline, test cases, and documentation as required by the change.
4. Run `make check`.
5. Run the model cases the change affects, or note in `tasks.md` why you did
   not; either way the task is done and its box gets ticked. They are evidence,
   not a gate: they cost money and vary between runs.
6. Move the directory to `archive/<date>-<short-name>/` with every box ticked.

## Requirement IDs

Every rule group in the baseline carries an ID like `aiscb-AUTH-001`. The ID
belongs to the behavior, not to the heading or the line: reword the rule and it
keeps its ID. Split a group and the new half gets a new ID. Remove a group and
its ID retires; never reuse it.

A change directory numbers its own requirements, and those IDs stay inside it:
only its `proposal.md` and `tasks.md` refer to them. Two changes may therefore
carry the same ID for different requirements, because `make check` keeps IDs
unique within a file, not across the archive. `AGENT-SDD-001` does, in
`archive/2026-08-15-load-baseline-for-agents/` and
`archive/2026-08-15-anchor-sdd-agent-instructions/`. Only baseline IDs are
unique for good.

Test cases name the IDs they exercise in their `checks.json`. A rule group
without a case is not automatically a gap, and not automatically fine. Add a
case relationship only when the case really observes that behavior.

`requirements.md` explains each group in plain language. The baseline remains
normative; catalog summaries and acceptance criteria must not add behavior. Each
entry identifies its model cases and says which parts they do not cover.

## What is enforced

`make check` runs on every push and pull request
(`.github/workflows/check.yml`), takes about a second, and never calls a model.
It fails on:

- a rule group without an ID, or an ID that is duplicated, malformed, or not
  attached to a rule group;
- an `AGENTS.md` that does not require agents to read the normative baseline,
  reintroduces a generated baseline copy, or is not paired with the required
  Claude imports;
- a case naming an ID the baseline does not define;
- a missing, duplicate, unknown, or incomplete catalog entry, or one whose name,
  section, source, evidence level, or case list no longer matches;
- a change directory with missing or incomplete proposal, requirement, or task
  content, including an invalid archive date or unfinished archived task;
- malformed case metadata, an unknown key, a pattern that does not compile, or
  a case with no observable checks;
- a fixture that no longer starts in the state its case depends on.

It also runs `examples/claude-code-gate/test_gate.py`, which keeps the example
gate honest: every rule denies its sample and allows an ordinary one, and every
rule id it cites still names a rule group in the baseline. It also runs
`examples/organization-bundle/test_bundle.py`, which builds the bundle example
against the current baseline and fails when its overlay names another aiscb
release. Neither example is normative and nothing else depends on them.

It also runs `scripts/test_spec_guard.py`, which holds the spec guard to its
contract and verifies its project registration: an identifiable write that
targets a file under `specs/` turns into a permission prompt, while recognized
read-only calls pass untouched. Conservative writer checks may still ask when
a spec is only a source. `.claude/settings.json` adds a native edit ask rule and
loads the guard when Claude Code starts from the repository root; a session
started in a subdirectory does not inherit that project hook. A command hook
that cannot start or reaches its timeout produces no decision and falls back to
the normal permission flow. The shell arm can inspect only the command and
paths Claude supplies; it cannot infer a hidden write performed by an otherwise
opaque program. Only tools with hooks can run the guard, so the approval rule
still holds on its own where the hook cannot establish the effect.

`tests/test_selfcheck.py` breaks a throwaway repository in representative ways
from every category and expects the complaint, so the main guard paths cannot
quietly disappear.

The deterministic checks enforce structure and traceability. A reviewer still
has to confirm that a summary is faithful, a source supports its requirement,
and a case really observes the behavior it names. Model runs measure whether an
assistant follows the baseline; they remain stochastic evidence, not a CI gate.
