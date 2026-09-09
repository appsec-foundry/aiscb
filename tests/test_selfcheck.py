#!/usr/bin/env python3
"""Check that selfcheck.py still fails when something is actually wrong.

selfcheck.py is the only thing standing between a broken suite and a paid model
run, and a guard nobody tests is a guard that can quietly stop guarding. Each
case below breaks a tiny throwaway repository in one realistic way and expects
the message that should come out.
"""

import contextlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent

BASELINE = """\
# Demo baseline

`baseline-id: aiscb-0.1.0`

## Non-negotiable

- **[aiscb-DEMO-001] First rule:** Do the safe thing.
- **[aiscb-DEMO-002] Second rule:** Do it again.
"""

CATALOG = """\
# Secure coding requirements catalog

## aiscb-DEMO-001 — First rule

**Section:** Non-negotiable
**Normative source:** `secure-coding-baseline.md`, rule group `aiscb-DEMO-001`.
**Applies when:** The demo runs.
**Requirement:** Do the safe thing.
**Observable acceptance:** The result is safe.
**Model cases:** `demo-case`
**Evidence and gaps:** Partial. One demo case covers it.

## aiscb-DEMO-002 — Second rule

**Section:** Non-negotiable
**Normative source:** `secure-coding-baseline.md`, rule group `aiscb-DEMO-002`.
**Applies when:** The demo runs again.
**Requirement:** Repeat the safe action.
**Observable acceptance:** The result is safe again.
**Model cases:** None.
**Evidence and gaps:** None. No model case declares it.
"""

CHECKS = """\
{
  "mode": "greenfield",
  "why": "A minimal valid case for guard tests.",
  "requirements": ["aiscb-DEMO-001"],
  "reply_required_regex": [{"id": "says-something", "pattern": "safe"}]
}
"""

CONVERSATION = """\
[
  {
    "turn": 1,
    "reaction": "Answer the request without adding a Security note.",
    "security_note_count": 0,
    "required_regex": [],
    "forbidden_regex": [],
    "judge": [{"id": "turn-1-reaction", "q": "The reply does not answer safely."}]
  }
]
"""

PROPOSAL = """\
# Demo change

## Problem
The old behavior is unclear.

## Goal
Make it clear.

## Non-goals
Do not change unrelated behavior.

## Compatibility
Existing callers remain supported.
"""

CHANGE_REQUIREMENTS = """\
# Requirements

## DEMO-001 Clear behavior

Source: the explicit demo request.

The system must make the behavior clear.

Acceptance: the resulting behavior is unambiguous.
"""

AGENTS = """\
# Repository instructions

Before doing any repository work, read and follow
[`secure-coding-baseline.md`](secure-coding-baseline.md); it is normative.
"""

README = """\
# Demo baseline

Ask the tool `baseline?`. The answer should include `aiscb-0.1.0`.

- `aiscb-0.1.0`: this baseline.
"""


def build(root: Path) -> None:
    """A miniature of this repository: baseline, catalog, one case, the guard."""
    (root / "specs").mkdir()
    (root / "tests" / "cases" / "demo-case").mkdir(parents=True)
    (root / "secure-coding-baseline.md").write_text(BASELINE)
    (root / "README.md").write_text(README)
    (root / "AGENTS.md").write_text(AGENTS)
    (root / "CLAUDE.md").write_text("@AGENTS.md\n@secure-coding-baseline.md\n")
    (root / "specs" / "requirements.md").write_text(CATALOG)
    (root / "tests" / "cases" / "demo-case" / "prompt.md").write_text("do the thing\n")
    (root / "tests" / "cases" / "demo-case" / "checks.json").write_text(CHECKS)
    # selfcheck compiles run.py; the real one is irrelevant to these guards.
    (root / "tests" / "run.py").write_text("# stub\n")
    shutil.copy(HERE / "selfcheck.py", root / "tests" / "selfcheck.py")


def edit(path: Path, old: str, new: str) -> None:
    path.write_text(path.read_text().replace(old, new))


def make_change(directory: Path, *, completed: bool = True) -> None:
    directory.mkdir(parents=True)
    (directory / "proposal.md").write_text(PROPOSAL)
    (directory / "requirements.md").write_text(CHANGE_REQUIREMENTS)
    mark = "x" if completed else " "
    (directory / "tasks.md").write_text(f"# Tasks\n\n- [{mark}] Finish the change.\n")


def add_failing_precondition(root: Path) -> None:
    case = root / "tests" / "cases" / "demo-case"
    (case / "fixture").mkdir()
    edit(case / "checks.json", '\n}',
         ',\n  "fixture_precondition": {"cmd": "true", "expect_exit": 1}\n}')


def add_conversation(root: Path) -> None:
    checks = root / "tests" / "cases" / "demo-case" / "checks.json"
    edit(checks, "\n}", f',\n  "conversation": {CONVERSATION}\n}}')


# Each case gets the throwaway repository and breaks it. The second value is
# what selfcheck must say; None means it must stay silent and pass.
CASES = [
    ("intact repository", lambda r: None, None),
    ("valid conversation contract", add_conversation, None),
    ("conversation contract points at the wrong turn",
     lambda r: (add_conversation(r),
                edit(r / "tests" / "cases" / "demo-case" / "checks.json",
                     '"turn": 1', '"turn": 2')),
     "conversation must cover every turn exactly once"),
    ("conversation contract has no note count",
     lambda r: (add_conversation(r),
                edit(r / "tests" / "cases" / "demo-case" / "checks.json",
                     '"security_note_count": 0', '"security_note_count_missing": 0')),
     "needs a non-negative integer security_note_count"),
    ("conversation judge has no stable id",
     lambda r: (add_conversation(r),
                edit(r / "tests" / "cases" / "demo-case" / "checks.json",
                     '"id": "turn-1-reaction"', '"name": "turn-1-reaction"')),
     "judge item 0 has no id"),
    ("baseline id is not SemVer",
     lambda r: edit(r / "secure-coding-baseline.md", "aiscb-0.1.0", "aiscb-0.1"),
     "does not use Semantic Versioning"),
    ("README current baseline id is stale",
     lambda r: edit(r / "README.md", "- `aiscb-0.1.0`: this baseline.",
                    "- `aiscb-0.1.1`: this baseline."),
     "README current baseline id 'aiscb-0.1.1' does not match"),
    ("agent baseline reference is missing",
     lambda r: (r / "AGENTS.md").write_text("# Repository instructions\n"),
     "AGENTS.md must require agents to read and follow"),
    ("generated agent baseline block is reintroduced",
     lambda r: edit(r / "AGENTS.md", "# Repository instructions",
                    "# Repository instructions\n\n"
                    "<!-- BEGIN GENERATED SECURE CODING BASELINE -->"),
     "AGENTS.md must reference secure-coding-baseline.md instead of embedding"),
    ("Claude baseline import is missing",
     lambda r: edit(r / "CLAUDE.md", "@secure-coding-baseline.md\n", ""),
     "CLAUDE.md must import secure-coding-baseline.md exactly once"),
    ("rule group renamed in the baseline",
     lambda r: edit(r / "secure-coding-baseline.md", "First rule", "Renamed rule"),
     "catalog calls aiscb-DEMO-001"),
    ("rule group added without a catalog entry",
     lambda r: edit(r / "secure-coding-baseline.md", "\n## Non",
                    "\n- **[aiscb-DEMO-003] Third rule:** New.\n\n## Non"),
     "catalog does not list 'aiscb-DEMO-003'"),
    ("case coverage the catalog does not show",
     lambda r: edit(r / "tests" / "cases" / "demo-case" / "checks.json",
                    '["aiscb-DEMO-001"]', '["aiscb-DEMO-001", "aiscb-DEMO-002"]'),
     "catalog cases for aiscb-DEMO-002"),
    ("case pointing at an id that does not exist",
     lambda r: edit(r / "tests" / "cases" / "demo-case" / "checks.json",
                    "aiscb-DEMO-001", "aiscb-GONE-001"),
     "unknown requirement id"),
    ("duplicate id in the baseline",
     lambda r: edit(r / "secure-coding-baseline.md", "aiscb-DEMO-002", "aiscb-DEMO-001"),
     "duplicate requirement id"),
    ("malformed id in the baseline",
     lambda r: edit(r / "secure-coding-baseline.md", "aiscb-DEMO-002", "aiscb-demo-002"),
     "malformed requirement id"),
    ("rule group without an id",
     lambda r: edit(r / "secure-coding-baseline.md",
                    "- **[aiscb-DEMO-002] Second rule:**",
                    "- **Second rule:**"),
     "has no valid requirement id"),
    ("catalog entry missing its requirement text",
     lambda r: edit(r / "specs" / "requirements.md",
                    "**Requirement:** Do the safe thing.",
                    "**Summary:** Do the safe thing."),
     "is missing 'Requirement'"),
    ("misspelled key in checks.json",
     lambda r: edit(r / "tests" / "cases" / "demo-case" / "checks.json",
                    '"mode"', '"moed"'),
     "unknown key"),
    ("check pattern that does not compile",
     lambda r: edit(r / "tests" / "cases" / "demo-case" / "checks.json",
                    '"safe"', '"safe("'),
     "does not compile"),
    ("case with no observable checks",
     lambda r: edit(r / "tests" / "cases" / "demo-case" / "checks.json",
                    '[{"id": "says-something", "pattern": "safe"}]', '[]'),
     "no checks at all"),
    ("fixture no longer has its required starting state",
     add_failing_precondition,
     "fixture_precondition 'true' exited 0, expected 1"),
    ("change directory missing a file",
     lambda r: (r / "specs" / "changes" / "half-done").mkdir(parents=True),
     "half-done is missing proposal.md"),
    ("change proposal missing meaningful content",
     lambda r: (make_change(r / "specs" / "changes" / "empty-goal"),
                edit(r / "specs" / "changes" / "empty-goal" / "proposal.md",
                     "## Goal\nMake it clear.", "## Goal")),
     "missing a non-empty 'Goal' section"),
    ("change requirement missing its source",
     lambda r: (make_change(r / "specs" / "changes" / "no-source"),
                edit(r / "specs" / "changes" / "no-source" / "requirements.md",
                     "Source:", "Origin:")),
     "requirement DEMO-001 has no source"),
    ("change requirement missing acceptance",
     lambda r: (make_change(r / "specs" / "changes" / "no-acceptance"),
                edit(r / "specs" / "changes" / "no-acceptance" / "requirements.md",
                     "Acceptance:", "Result:")),
     "requirement DEMO-001 has no acceptance criterion"),
    ("change requirement id repeated",
     lambda r: (make_change(r / "specs" / "changes" / "duplicate-requirement"),
                edit(r / "specs" / "changes" / "duplicate-requirement" /
                     "requirements.md", "## DEMO-001 Clear behavior",
                     "## DEMO-001 Clear behavior\n\nSource: the explicit demo request.\n\n"
                     "The first copy must be clear.\n\nAcceptance: the first copy is clear.\n\n"
                     "## DEMO-001 Clear behavior")),
     "repeats 'DEMO-001'"),
    ("archived change has unfinished work",
     lambda r: make_change(r / "specs" / "archive" / "2026-08-15-unfinished",
                           completed=False),
     "has unfinished tasks in the archive"),
    ("archived change without a valid date in its name",
     lambda r: make_change(r / "specs" / "archive" / "no-date"),
     "no-date should start with a valid date"),
]


# The cases above run the guard as its own process against a copy of it, which
# is the honest end-to-end shape but leaves the shipped selfcheck.py unmeasured
# and every per-case rejection below untested. check_case() only depends on the
# directory it is handed, so the schema rules are checked by calling it.

sys.path.insert(0, str(HERE))
import selfcheck  # noqa: E402

DEMO_IDS = {"aiscb-DEMO-001", "aiscb-DEMO-002"}
VALID_CHECKS = {
    "mode": "greenfield",
    "why": "A minimal valid case for guard tests.",
    "requirements": ["aiscb-DEMO-001"],
    "reply_required_regex": [{"id": "says-something", "pattern": "safe"}],
}
VALID_TURN = {
    "turn": 1,
    "reaction": "Answer without a Security note.",
    "security_note_count": 0,
    "judge": [{"id": "turn-1-reaction", "q": "Does the reply answer safely?"}],
}


def with_checks(**overrides) -> dict:
    return {**VALID_CHECKS, **overrides}


def with_turn(**overrides) -> dict:
    return with_checks(conversation=[{**VALID_TURN, **overrides}])


def inspect_case(checks: object, extra: dict[str, str] | None = None,
                 prompt: str = "do the thing\n") -> tuple[list[str], list[str]]:
    """Run check_case over a throwaway case directory and collect its verdict."""
    with tempfile.TemporaryDirectory() as tmp:
        case = Path(tmp) / "demo-case"
        case.mkdir()
        if prompt is not None:
            (case / "prompt.md").write_text(prompt)
        if checks is not None:
            (case / "checks.json").write_text(
                checks if isinstance(checks, str) else json.dumps(checks)
            )
        for name, content in (extra or {}).items():
            target = case / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        selfcheck.problems.clear()
        selfcheck.notes.clear()
        selfcheck.coverage.clear()
        selfcheck.check_case(case, set(DEMO_IDS))
        return list(selfcheck.problems), list(selfcheck.notes)


# Every entry breaks the minimal valid case in one way and names the complaint.
SCHEMA_CASES = [
    ("a checks.json that does not parse", "{not json", "does not parse"),
    ("a checks.json that is not an object", [], "must contain an object"),
    ("an unknown key", with_checks(moed="greenfield"), "unknown key"),
    ("an unknown mode", with_checks(mode="brownfield"), "mode must be one of"),
    ("an empty why", with_checks(why="  "), "why must be a non-empty string"),
    ("a non-string turns", with_checks(turns=3), "turns must be a non-empty string"),
    ("empty requirements", with_checks(requirements=[]),
     "requirements must be a non-empty list"),
    ("a non-string requirement id", with_checks(requirements=[1]),
     "requirements contains a non-string id"),
    ("a repeated requirement id",
     with_checks(requirements=["aiscb-DEMO-001", "aiscb-DEMO-001"]),
     "duplicate requirement id"),
    ("an unknown requirement id", with_checks(requirements=["aiscb-GONE-001"]),
     "unknown requirement id"),
    ("a regex block that is not a list", with_checks(reply_required_regex={}),
     "reply_required_regex must be a list"),
    ("a regex rule that is not an object", with_checks(reply_required_regex=[[]]),
     "item 0 must be an object"),
    ("a regex rule without a pattern", with_checks(reply_required_regex=[{"id": "x"}]),
     "rule needs both id and pattern"),
    ("a repeated check id",
     with_checks(reply_required_regex=[{"id": "x", "pattern": "a"},
                                       {"id": "x", "pattern": "b"}]),
     "duplicate check id"),
    ("an empty in-glob list",
     with_checks(required_regex=[{"id": "y", "pattern": "a", "in": []}]),
     "in must be a non-empty list of globs"),
    ("a pattern that does not compile",
     with_checks(reply_required_regex=[{"id": "x", "pattern": "safe("}]),
     "does not compile"),
    ("a judge block that is not a list", with_checks(judge={}), "judge must be a list"),
    ("a judge item that is not an object", with_checks(judge=[[]]),
     "judge item 0 must be an object"),
    ("a judge item without a question",
     with_checks(judge=[{"target": "reply"}]), "judge item 0 has no q"),
    ("a judge item with an unknown target",
     with_checks(judge=[{"q": "Is it safe?", "target": "everything"}]),
     "target must be one of"),
    ("a conversation that is not a list", with_checks(conversation={}),
     "conversation must be a list"),
    ("an empty conversation", with_checks(conversation=[]),
     "conversation must not be empty"),
    ("a conversation item that is not an object", with_checks(conversation=[[]]),
     "conversation item 0 must be an object"),
    ("an unknown conversation key", with_turn(extra_key=1), "has unknown key"),
    ("empty turn file restrictions", with_turn(must_not_change=[]),
     "must_not_change needs a non-empty list of globs"),
    ("non-string turn file restriction", with_turn(must_not_change=[1]),
     "must_not_change needs a non-empty list of globs"),
    ("an oracle outside the harness", with_checks(oracle="../other"),
     "oracle must name an existing harness-owned checker"),
    ("an unknown oracle", with_checks(oracle="missing-checker"),
     "oracle must name an existing harness-owned checker"),
    ("a non-string oracle", with_checks(oracle=True),
     "oracle must name an existing harness-owned checker"),
    ("a turn that is not a positive integer", with_turn(turn=0),
     "needs a positive integer turn"),
    ("a boolean turn", with_turn(turn=True), "needs a positive integer turn"),
    ("a repeated turn",
     with_checks(conversation=[VALID_TURN, {**VALID_TURN, "reaction": "again"}]),
     "conversation repeats turn"),
    ("a turn without a reaction", with_turn(reaction="  "),
     "needs a non-empty reaction"),
    ("a turn without a note count", with_turn(security_note_count="none"),
     "needs a non-negative integer security_note_count"),
    ("a boolean note count", with_turn(security_note_count=True),
     "needs a non-negative integer security_note_count"),
    ("a turn regex block that is not a list", with_turn(required_regex={}),
     "required_regex must be a list"),
    ("a turn regex rule that is not an object", with_turn(required_regex=[[]]),
     "required_regex item 0 must be an object"),
    ("a turn regex rule with unknown keys",
     with_turn(required_regex=[{"id": "t", "pattern": "a", "extra": 1}]),
     "has unknown keys"),
    ("a turn regex rule without a pattern",
     with_turn(required_regex=[{"id": "t"}]), "needs both id and pattern"),
    ("a turn regex pattern that does not compile",
     with_turn(required_regex=[{"id": "t", "pattern": "safe("}]), "does not compile"),
    ("a turn without a judge", with_turn(judge=[]),
     "judge must be a non-empty list"),
    ("a turn judge item that is not an object", with_turn(judge=[[]]),
     "judge item 0 must be an object"),
    ("a turn judge item with unknown keys",
     with_turn(judge=[{"id": "t", "q": "Safe?", "target": "reply"}]),
     "has unknown keys"),
    ("a turn judge item without an id", with_turn(judge=[{"q": "Safe?"}]),
     "judge item 0 has no id"),
    ("a turn judge item without a question", with_turn(judge=[{"id": "t"}]),
     "judge item 0 has no q"),
    ("a verify block that is not an object", with_checks(verify="make check"),
     "verify must be an object"),
    ("a verify block without a command",
     with_checks(verify={"cmd": " ", "expect_exit": 0}), "verify needs a non-empty cmd"),
    ("a verify block without an expected exit code",
     with_checks(verify={"cmd": "make check"}), "verify needs an integer expect_exit"),
    ("a verify block with an empty why",
     with_checks(verify={"cmd": "make check", "expect_exit": 0, "why": " "}),
     "verify why must be a non-empty string"),
    ("a case with no observable checks",
     with_checks(reply_required_regex=[]), "no checks at all"),
    ("scope keys without a fixture",
     with_checks(must_modify=["app.py"]), "needs a fixture/ to compare against"),
    ("a scope key that is not a list of paths",
     with_checks(must_modify=[""], **{"must_not_modify": ["x"]}),
     "must be a non-empty list of paths or globs"),
    ("a fixture precondition without a fixture",
     with_checks(fixture_precondition={"cmd": "true", "expect_exit": 0}),
     "fixture_precondition without a fixture/"),
]

IN_PROCESS: list[tuple[str, bool, str]] = []

for label, checks, expected in SCHEMA_CASES:
    found, _notes = inspect_case(checks)
    IN_PROCESS.append((
        f"check_case rejects {label}",
        any(expected in problem for problem in found),
        f"expected {expected!r}, got {found}",
    ))

valid_problems, _ = inspect_case(VALID_CHECKS)
IN_PROCESS.append(("check_case accepts a minimal valid case",
                   valid_problems == [], str(valid_problems)))

conversation_problems, _ = inspect_case(with_checks(conversation=[VALID_TURN]))
IN_PROCESS.append(("check_case accepts a single-turn conversation",
                   conversation_problems == [], str(conversation_problems)))

missing_checks, _ = inspect_case(None)
IN_PROCESS.append(("check_case reports a missing checks.json",
                   any("missing checks.json" in p for p in missing_checks),
                   str(missing_checks)))

missing_prompt, _ = inspect_case(VALID_CHECKS, prompt=None)
IN_PROCESS.append(("check_case reports a missing prompt.md",
                   any("missing prompt.md" in p for p in missing_prompt),
                   str(missing_prompt)))

empty_prompt, _ = inspect_case(VALID_CHECKS, prompt="   \n")
IN_PROCESS.append(("check_case reports an empty prompt.md",
                   any("prompt.md is empty" in p for p in empty_prompt),
                   str(empty_prompt)))

bad_followup, _ = inspect_case(
    with_checks(conversation=[VALID_TURN,
                              {**VALID_TURN, "turn": 2, "reaction": "second",
                               "judge": [{"id": "turn-2", "q": "Safe?"}]}]),
    {"followup-1.md": "and then?\n", "followup-two.md": "bad name\n"},
)
IN_PROCESS.append(("check_case reports a misnamed follow-up",
                   any("does not match followup-<n>.md" in p for p in bad_followup),
                   str(bad_followup)))

gap_followup, _ = inspect_case(
    VALID_CHECKS, {"followup-1.md": "a\n", "followup-3.md": "b\n"}
)
IN_PROCESS.append(("check_case reports a gap in follow-up numbering",
                   any("follow-up numbering has a gap" in p for p in gap_followup),
                   str(gap_followup)))

turn_mismatch, _ = inspect_case(
    with_checks(conversation=[VALID_TURN]), {"followup-1.md": "and then?\n"}
)
IN_PROCESS.append(("check_case requires a contract for every turn",
                   any("must cover every turn exactly once" in p
                       for p in turn_mismatch), str(turn_mismatch))
                  )

note_collision, _ = inspect_case(
    with_checks(
        reply_required_regex=[{"id": "turn-1-security-note-count", "pattern": "a"}],
        conversation=[VALID_TURN],
    )
)
IN_PROCESS.append(("check_case catches a collision with a generated note id",
                   any("duplicate check id" in p for p in note_collision),
                   str(note_collision)))

fixture_missing_path, _ = inspect_case(
    with_checks(must_not_modify=["gone.py"]), {"fixture/app.py": "x = 1\n"}
)
IN_PROCESS.append(("check_case reports a protected path the fixture lacks",
                   any("not in the fixture" in p for p in fixture_missing_path),
                   str(fixture_missing_path)))

_, created_note = inspect_case(
    with_checks(must_modify=["new.py"]), {"fixture/app.py": "x = 1\n"}
)
IN_PROCESS.append(("check_case only notes a file the assistant may create",
                   any("does not contain yet" in note for note in created_note),
                   str(created_note)))

precondition_failed, _ = inspect_case(
    with_checks(fixture_precondition={"cmd": "true", "expect_exit": 1}),
    {"fixture/app.py": "x = 1\n"},
)
IN_PROCESS.append(("check_case runs the fixture precondition and reports a pass",
                   any("expected 1" in p for p in precondition_failed),
                   str(precondition_failed)))

precondition_ok, _ = inspect_case(
    with_checks(fixture_precondition={"cmd": "false", "expect_exit": 1}),
    {"fixture/app.py": "x = 1\n"},
)
IN_PROCESS.append(("check_case accepts a fixture that starts out failing",
                   precondition_ok == [], str(precondition_ok)))

# check_change_spec and markdown_sections also depend only on what they are
# handed, so the change-specification rules are checked the same way.


def inspect_change(files: dict[str, str], archived: bool = False) -> list[str]:
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp) / "a-change"
        directory.mkdir()
        for name, content in files.items():
            (directory / name).write_text(content)
        selfcheck.problems.clear()
        selfcheck.check_change_spec("changes/a-change", directory, archived)
        return list(selfcheck.problems)


COMPLETE_CHANGE = {
    "proposal.md": PROPOSAL,
    "requirements.md": CHANGE_REQUIREMENTS,
    "tasks.md": "# Tasks\n\n- [x] Finish the change.\n",
}

IN_PROCESS.append(("check_change_spec accepts a complete change",
                   inspect_change(COMPLETE_CHANGE) == [],
                   str(inspect_change(COMPLETE_CHANGE))))

repeated_section = inspect_change({
    **COMPLETE_CHANGE,
    "proposal.md": PROPOSAL + "\n## Goal\nA second goal section.\n",
})
IN_PROCESS.append(("check_change_spec reports a repeated proposal section",
                   any("repeats section" in p for p in repeated_section),
                   str(repeated_section)))

no_requirements = inspect_change({**COMPLETE_CHANGE, "requirements.md": "# Empty\n"})
IN_PROCESS.append(("check_change_spec reports requirements with no entries",
                   any("has no requirements" in p for p in no_requirements),
                   str(no_requirements)))

bad_heading = inspect_change({
    **COMPLETE_CHANGE,
    "requirements.md": "# Requirements\n\n## Just a heading\n\nSource: x\n\n"
                       "Behavior.\n\nAcceptance: y\n",
})
IN_PROCESS.append(("check_change_spec reports a malformed requirement heading",
                   any("malformed requirement heading" in p for p in bad_heading),
                   str(bad_heading)))

no_behavior = inspect_change({
    **COMPLETE_CHANGE,
    "requirements.md": "# Requirements\n\n## DEMO-001 Clear behavior\n\n"
                       "Source: the request.\n\nAcceptance: it is clear.\n",
})
IN_PROCESS.append(("check_change_spec reports a requirement without behavior text",
                   any("has no behavior text" in p for p in no_behavior),
                   str(no_behavior)))

no_tasks = inspect_change({**COMPLETE_CHANGE, "tasks.md": "# Tasks\n\nNothing yet.\n"})
IN_PROCESS.append(("check_change_spec reports a task list with no tasks",
                   any("has no tasks" in p for p in no_tasks), str(no_tasks)))

unfinished = inspect_change(
    {**COMPLETE_CHANGE, "tasks.md": "# Tasks\n\n- [ ] Still open.\n"}, archived=True
)
IN_PROCESS.append(("check_change_spec reports unfinished archived work",
                   any("unfinished tasks in the archive" in p for p in unfinished),
                   str(unfinished)))

incomplete = inspect_change({"proposal.md": PROPOSAL})
IN_PROCESS.append(("check_change_spec leaves an incomplete directory to its own check",
                   incomplete == [], str(incomplete)))


# The remaining guards read repository-level files through module constants.
# Pointing those at a throwaway repository keeps the checks in this process.
# getattr without a default is deliberate: renaming a constant must fail loudly
# here rather than silently leave these guards pointing at the real repository.


@contextlib.contextmanager
def paths(**overrides):
    saved = {name: getattr(selfcheck, name) for name in overrides}
    for name, value in overrides.items():
        setattr(selfcheck, name, value)
    try:
        yield
    finally:
        for name, value in saved.items():
            setattr(selfcheck, name, value)


def written(root: Path, name: str, content: str) -> Path:
    target = root / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    return target


def guard(expected: str | None, run) -> None:
    """Run one guard over a throwaway directory and record what it reported."""
    with tempfile.TemporaryDirectory() as tmp:
        selfcheck.problems.clear()
        selfcheck.notes.clear()
        selfcheck.coverage.clear()
        label = run(Path(tmp))
        found = list(selfcheck.problems)
    if expected is None:
        IN_PROCESS.append((f"{label} passes", found == [], str(found)))
    else:
        IN_PROCESS.append((
            label,
            any(expected in problem for problem in found),
            f"expected {expected!r}, got {found}",
        ))


def baseline_guard(expected: str | None, text: str | None, label: str) -> None:
    def run(root: Path) -> str:
        target = root / "secure-coding-baseline.md"
        if text is not None:
            target.write_text(text)
        with paths(BASELINE=target):
            selfcheck.load_baseline_groups()
        return label
    guard(expected, run)


baseline_guard("baseline missing at", None,
               "load_baseline_groups reports a missing baseline")
baseline_guard("has no valid requirement id",
               "## Rules\n\n- **A rule without an id:** text.\n",
               "load_baseline_groups reports a rule bullet without an id")
baseline_guard("malformed requirement id",
               "## Rules\n\n- **[aiscb-demo-1] Rule:** text.\n",
               "load_baseline_groups reports a malformed id")
baseline_guard("duplicate requirement id",
               "## Rules\n\n- **[aiscb-DEMO-001] One:** a.\n"
               "- **[aiscb-DEMO-001] Two:** b.\n",
               "load_baseline_groups reports a duplicate id")
baseline_guard("is not on a rule-group bullet",
               "## Rules\n\nSee [aiscb-DEMO-001] elsewhere.\n",
               "load_baseline_groups reports an id outside a rule bullet")
baseline_guard("has no requirement ids", "## Rules\n\nNothing here.\n",
               "load_baseline_groups reports a baseline without ids")
baseline_guard(None, "## Rules\n\n- **[aiscb-DEMO-001] One:** a.\n",
               "load_baseline_groups on a valid baseline")


def identifier_guard(expected: str | None, baseline: str, readme: str | None,
                     label: str) -> None:
    def run(root: Path) -> str:
        baseline_path = written(root, "secure-coding-baseline.md", baseline)
        readme_path = root / "README.md"
        if readme is not None:
            readme_path.write_text(readme)
        with paths(BASELINE=baseline_path, README=readme_path):
            selfcheck.check_baseline_identifier()
        return label
    guard(expected, run)


GOOD_BASELINE = "`baseline-id: aiscb-0.1.0`\n"
GOOD_README = ("Ask `baseline?`. The answer should include `aiscb-0.1.0`.\n\n"
               "- `aiscb-0.1.0`: this baseline.\n")

identifier_guard("exactly one baseline id",
                 GOOD_BASELINE + GOOD_BASELINE, GOOD_README,
                 "check_baseline_identifier reports two baseline ids")
identifier_guard("does not use Semantic Versioning",
                 "`baseline-id: aiscb-0.1`\n", GOOD_README,
                 "check_baseline_identifier reports a non-SemVer id")
identifier_guard("README missing at", GOOD_BASELINE, None,
                 "check_baseline_identifier reports a missing README")
identifier_guard("must document exactly one", GOOD_BASELINE,
                 "- `aiscb-0.1.0`: this baseline.\n",
                 "check_baseline_identifier reports an undocumented verification id")
identifier_guard("does not match", GOOD_BASELINE,
                 GOOD_README.replace("- `aiscb-0.1.0`", "- `aiscb-0.2.0`"),
                 "check_baseline_identifier reports a stale README id")
identifier_guard(None, GOOD_BASELINE, GOOD_README,
                 "check_baseline_identifier on matching files")


def instructions_guard(expected: str | None, agents: str | None,
                       claude: str | None, label: str) -> None:
    def run(root: Path) -> str:
        agents_path, claude_path = root / "AGENTS.md", root / "CLAUDE.md"
        if agents is not None:
            agents_path.write_text(agents)
        if claude is not None:
            claude_path.write_text(claude)
        with paths(AGENTS=agents_path, CLAUDE=claude_path):
            selfcheck.check_agent_instructions()
        return label
    guard(expected, run)


GOOD_CLAUDE = "@AGENTS.md\n@secure-coding-baseline.md\n"

instructions_guard("agent instructions missing at", None, GOOD_CLAUDE,
                   "check_agent_instructions reports missing AGENTS.md")
instructions_guard("must require agents to read and follow",
                   "# Instructions\n", GOOD_CLAUDE,
                   "check_agent_instructions reports a missing baseline reference")
instructions_guard("instead of embedding", AGENTS + "\nGENERATED SECURE CODING BASELINE\n",
                   GOOD_CLAUDE,
                   "check_agent_instructions reports an embedded baseline block")
instructions_guard("Claude instructions missing at", AGENTS, None,
                   "check_agent_instructions reports missing CLAUDE.md")
instructions_guard("must import secure-coding-baseline.md exactly once",
                   AGENTS, "@AGENTS.md\n",
                   "check_agent_instructions reports a missing import")
instructions_guard("must import secure-coding-baseline.md exactly once",
                   AGENTS, GOOD_CLAUDE + "@secure-coding-baseline.md\n",
                   "check_agent_instructions reports a repeated import")
instructions_guard(None, AGENTS, GOOD_CLAUDE,
                   "check_agent_instructions on intact instructions")


def catalog_guard(expected: str | None, catalog: str | None, label: str,
                  groups: dict | None = None,
                  case_coverage: dict | None = None) -> None:
    def run(root: Path) -> str:
        index = root / "specs" / "requirements.md"
        if catalog is not None:
            written(root, "specs/requirements.md", catalog)
        selfcheck.coverage.update(case_coverage or {})
        with paths(INDEX=index):
            selfcheck.check_requirement_catalog(
                groups if groups is not None
                else {"aiscb-DEMO-001": ("First rule", "Non-negotiable")}
            )
        return label
    guard(expected, run)


ENTRY = """\
## aiscb-DEMO-001 — First rule

**Section:** Non-negotiable
**Normative source:** `secure-coding-baseline.md`, rule group `aiscb-DEMO-001`.
**Applies when:** The demo runs.
**Requirement:** Do the safe thing.
**Observable acceptance:** The result is safe.
**Model cases:** None.
**Evidence and gaps:** None. No model case declares it.
"""

catalog_guard("requirements catalog missing at", None,
              "catalog_entries reports a missing catalog")
catalog_guard("malformed requirement heading", "## Not a requirement\n",
              "catalog_entries reports a malformed heading")
catalog_guard("repeats field", ENTRY + "**Section:** Non-negotiable\n",
              "catalog_entries reports a repeated field")
catalog_guard("lists 'aiscb-DEMO-001' twice", ENTRY + ENTRY,
              "check_requirement_catalog reports a duplicate entry")
catalog_guard("which the baseline does not define",
              ENTRY.replace("aiscb-DEMO-001", "aiscb-GONE-001"),
              "check_requirement_catalog reports an unknown requirement",
              groups={})
catalog_guard("baseline calls it", ENTRY.replace("— First rule", "— Other name"),
              "check_requirement_catalog reports a renamed rule group")
catalog_guard("unknown field", ENTRY + "**Extra:** value\n",
              "check_requirement_catalog reports an unknown field")
catalog_guard("is missing 'Requirement'", ENTRY.replace("**Requirement:**", "**Rule:**"),
              "check_requirement_catalog reports a missing field")
catalog_guard("baseline has it in", ENTRY.replace("**Section:** Non-negotiable",
                                                  "**Section:** Apply"),
              "check_requirement_catalog reports a wrong section")
catalog_guard("does not name its baseline rule group",
              ENTRY.replace("`secure-coding-baseline.md`, rule group `aiscb-DEMO-001`.",
                            "somewhere else."),
              "check_requirement_catalog reports an unsourced entry")
catalog_guard("must be 'None.'", ENTRY.replace("**Model cases:** None.",
                                               "**Model cases:** `a-case`"),
              "check_requirement_catalog reports cases the suite does not declare")
catalog_guard("must start with 'Partial.'",
              ENTRY.replace("**Model cases:** None.", "**Model cases:** `a-case`"),
              "check_requirement_catalog reports the wrong evidence level",
              case_coverage={"aiscb-DEMO-001": ["a-case"]})
catalog_guard("catalog does not list 'aiscb-DEMO-002'", ENTRY,
              "check_requirement_catalog reports an unlisted rule group",
              groups={"aiscb-DEMO-001": ("First rule", "Non-negotiable"),
                      "aiscb-DEMO-002": ("Second rule", "Non-negotiable")})
catalog_guard(None, ENTRY, "check_requirement_catalog on a matching catalog")


def directories_guard(expected: str | None, build_it, label: str) -> None:
    def run(root: Path) -> str:
        changes, archive = root / "changes", root / "archive"
        build_it(changes, archive)
        with paths(CHANGES=changes, ARCHIVE=archive):
            selfcheck.check_change_directories()
        return label
    guard(expected, run)


def complete_change(directory: Path, *, done: bool = True) -> None:
    directory.mkdir(parents=True)
    (directory / "proposal.md").write_text(PROPOSAL)
    (directory / "requirements.md").write_text(CHANGE_REQUIREMENTS)
    (directory / "tasks.md").write_text(
        f"# Tasks\n\n- [{'x' if done else ' '}] Do it.\n"
    )


directories_guard(None, lambda changes, archive: None,
                  "check_change_directories with no change directories")
directories_guard("is missing proposal.md",
                  lambda changes, archive: (changes / "half-done").mkdir(parents=True),
                  "check_change_directories reports a missing file")
directories_guard("should start with a valid date",
                  lambda changes, archive: complete_change(archive / "no-date"),
                  "check_change_directories reports an undated archive entry")
directories_guard("should start with a valid date",
                  lambda changes, archive: complete_change(archive / "2026-13-45-bad"),
                  "check_change_directories reports an impossible archive date")
directories_guard(None,
                  lambda changes, archive: complete_change(
                      archive / "2026-08-15-done"),
                  "check_change_directories on a valid archive entry")


def timing_out_run(*_args, **_kwargs):
    raise subprocess.TimeoutExpired("sleep", 120)


def run_timeout(root: Path) -> str:
    case = root / "demo-case"
    (case / "fixture").mkdir(parents=True)
    original = selfcheck.subprocess.run
    selfcheck.subprocess.run = timing_out_run
    try:
        selfcheck.run_fixture_precondition(
            "demo-case", case, {"fixture_precondition": {"cmd": "sleep 500",
                                                         "expect_exit": 0}}
        )
    finally:
        selfcheck.subprocess.run = original
    return "run_fixture_precondition reports a precondition that times out"


guard("timed out", run_timeout)


def run_bad_schema(root: Path) -> str:
    case = root / "demo-case"
    case.mkdir()
    selfcheck.run_fixture_precondition(
        "demo-case", case, {"fixture_precondition": {"cmd": 5}}
    )
    return "run_fixture_precondition leaves a schema problem to check_case"


guard(None, run_bad_schema)

# One in-process run of main() over a miniature repository, which is the only
# way the top-level reporting and the run.py compile check get measured.


def run_main(root: Path) -> tuple[int, str]:
    """Run selfcheck.main() against an already-built miniature repository."""
    stdout = io.StringIO()
    with paths(HERE=root / "tests", ROOT=root, CASES=root / "tests" / "cases",
               BASELINE=root / "secure-coding-baseline.md",
               README=root / "README.md", AGENTS=root / "AGENTS.md",
               CLAUDE=root / "CLAUDE.md",
               INDEX=root / "specs" / "requirements.md",
               CHANGES=root / "specs" / "changes",
               ARCHIVE=root / "specs" / "archive"), \
            contextlib.redirect_stdout(stdout):
        selfcheck.problems.clear()
        selfcheck.notes.clear()
        selfcheck.coverage.clear()
        code = selfcheck.main()
    return code, stdout.getvalue()


with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    build(root)
    code, output = run_main(root)
    IN_PROCESS.append(("selfcheck passes over an intact miniature repository",
                       code == 0 and "1 cases checked, 0 problems" in output,
                       output))

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    build(root)
    (root / "tests" / "run.py").write_text("def broken(:\n")
    code, output = run_main(root)
    IN_PROCESS.append(("selfcheck reports a run.py that does not compile",
                       code == 1 and "run.py does not compile" in output, output))

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    build(root)
    shutil.rmtree(root / "tests" / "cases" / "demo-case")
    code, output = run_main(root)
    IN_PROCESS.append(("selfcheck reports an empty case directory",
                       code == 1 and "no cases found" in output, output))

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    build(root)
    case = root / "tests" / "cases" / "demo-case"
    (case / "fixture").mkdir()
    (case / "fixture" / "app.py").write_text("x = 1\n")
    edit(case / "checks.json", "\n}", ',\n  "must_modify": ["new.py"]\n}')
    code, output = run_main(root)
    IN_PROCESS.append(("selfcheck notes a file the assistant is expected to create",
                       code == 0 and "note: " in output and "new.py" in output, output))


def main() -> int:
    failures = 0
    for name, break_it, expected in CASES:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build(root)
            break_it(root)
            proc = subprocess.run([sys.executable, str(root / "tests" / "selfcheck.py")],
                                  capture_output=True, text=True)
            output = proc.stdout + proc.stderr
            if expected is None:
                ok = proc.returncode == 0
                complaint = f"expected a clean pass, got:\n{output}"
            else:
                ok = proc.returncode == 1 and expected in output
                complaint = f"expected a failure mentioning {expected!r}, got:\n{output}"
        print(f"{'ok  ' if ok else 'FAIL'} {name}")
        if not ok:
            failures += 1
            print(f"     {complaint}")

    for name, ok, complaint in IN_PROCESS:
        print(f"{'ok  ' if ok else 'FAIL'} {name}")
        if not ok:
            failures += 1
            print(f"     {complaint}")

    total = len(CASES) + len(IN_PROCESS)
    print(f"\n{total} guards checked, {failures} failures")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
