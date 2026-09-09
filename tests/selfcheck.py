#!/usr/bin/env python3
"""Check that the test suite itself is intact. Costs nothing, calls no model.

An agent run takes minutes and real tokens, so a case with a typo in a key, an
uncompilable pattern, or a fixture that no longer starts in the failing state it
depends on should be caught before any of that is spent.
"""

import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CASES = HERE / "cases"
BASELINE = ROOT / "secure-coding-baseline.md"
README = ROOT / "README.md"
AGENTS = ROOT / "AGENTS.md"
CLAUDE = ROOT / "CLAUDE.md"
INDEX = ROOT / "specs" / "requirements.md"
CHANGES = ROOT / "specs" / "changes"
ARCHIVE = ROOT / "specs" / "archive"
CHANGE_FILES = ("proposal.md", "requirements.md", "tasks.md")
AGENTS_BASELINE_REFERENCE = "[`secure-coding-baseline.md`](secure-coding-baseline.md)"
AGENTS_BASELINE_MARKER = "GENERATED SECURE CODING BASELINE"
REQUIREMENT_ID = re.compile(r"aiscb-[A-Z][A-Z0-9]*-\d{3}")
GROUP_BULLET = re.compile(r"- \*\*\[(aiscb-[^\]]+)\] (.+?):\*\*")
CATALOG_HEADING = re.compile(r"## (aiscb-[A-Z0-9-]+) — (.+)")
CATALOG_FIELD = re.compile(r"\*\*([^*]+):\*\*\s*(.*)")
CATALOG_FIELDS = (
    "Section", "Normative source", "Applies when", "Requirement",
    "Observable acceptance", "Model cases", "Evidence and gaps",
)
CHANGE_REQUIREMENT = re.compile(r"([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d{3}) (.+)")
NUMERIC_IDENTIFIER = r"(?:0|[1-9][0-9]*)"
PRERELEASE_IDENTIFIER = (
    rf"(?:{NUMERIC_IDENTIFIER}|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*)"
)
SEMVER = (
    rf"{NUMERIC_IDENTIFIER}\.{NUMERIC_IDENTIFIER}\.{NUMERIC_IDENTIFIER}"
    rf"(?:-{PRERELEASE_IDENTIFIER}(?:\.{PRERELEASE_IDENTIFIER})*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
)
BASELINE_IDENTIFIER = re.compile(rf"[a-z][a-z0-9]*(?:-[a-z0-9]+)*-{SEMVER}")
BASELINE_ID_LINE = re.compile(r"^`baseline-id: ([^`]+)`")
README_VERIFY_ID = re.compile(r"answer should include `([^`]+)`")
README_CURRENT_ID = re.compile(r"^- `([^`]+)`: this baseline\.$", re.MULTILINE)

REGEX_KEYS = ["forbidden_regex", "required_regex",
              "reply_forbidden_regex", "reply_required_regex", "transcript_forbidden_regex"]
KNOWN_KEYS = set(REGEX_KEYS) | {
    "mode", "why", "turns", "requirements", "reads_inverted", "scope_note",
    "verify_note", "note_on_the_key", "note_on_the_package", "judge", "must_modify",
    "must_not_modify", "verify", "fixture_precondition", "conversation", "oracle",
}
MODES = {"greenfield", "existing"}
TARGETS = {"code", "reply"}
CONVERSATION_KEYS = {
    "turn", "reaction", "security_note_count", "required_regex",
    "forbidden_regex", "judge", "must_not_change",
}

problems: list[str] = []
notes: list[str] = []
coverage: dict[str, list[str]] = {}


def fail(case: str, msg: str) -> None:
    problems.append(f"{case}: {msg}")


def load_baseline_groups() -> dict[str, tuple[str, str]]:
    """Map each requirement id to its group name and the section it sits in."""
    if not BASELINE.is_file():
        problems.append(f"baseline missing at {BASELINE}")
        return {}

    groups: dict[str, tuple[str, str]] = {}
    section = ""
    for lineno, line in enumerate(BASELINE.read_text(encoding="utf-8").splitlines(), 1):
        if line.startswith("## "):
            section = line[3:].strip()
        bullet = GROUP_BULLET.match(line) if line.startswith("- **") else None
        if line.startswith("- **") and not bullet:
            problems.append(f"baseline rule-group bullet on line {lineno} has no valid requirement id")
        for requirement_id in re.findall(r"\[(aiscb-[^\]]+)\]", line):
            if not REQUIREMENT_ID.fullmatch(requirement_id):
                problems.append(f"baseline has malformed requirement id {requirement_id!r}")
            elif requirement_id in groups:
                problems.append(f"baseline has duplicate requirement id {requirement_id!r}")
            elif not bullet or bullet.group(1) != requirement_id:
                problems.append(f"baseline id {requirement_id!r} is not on a rule-group bullet")
            else:
                groups[requirement_id] = (bullet.group(2).strip(), section)
    if not groups:
        problems.append("baseline has no requirement ids")
    return groups


def check_baseline_identifier() -> None:
    """The normative and documented IDs must name one SemVer revision."""
    if not BASELINE.is_file():
        return

    identifiers = [match.group(1) for line in BASELINE.read_text(encoding="utf-8").splitlines()
                   if (match := BASELINE_ID_LINE.match(line))]
    if len(identifiers) != 1:
        problems.append("baseline must declare exactly one baseline id")
        return
    identifier = identifiers[0]
    if not BASELINE_IDENTIFIER.fullmatch(identifier):
        problems.append(f"baseline id {identifier!r} does not use Semantic Versioning")

    if not README.is_file():
        problems.append(f"README missing at {README}")
        return
    readme = README.read_text(encoding="utf-8")
    for label, pattern in (("verification", README_VERIFY_ID),
                           ("current baseline", README_CURRENT_ID)):
        documented = pattern.findall(readme)
        if len(documented) != 1:
            problems.append(f"README must document exactly one {label} id")
        elif documented[0] != identifier:
            problems.append(f"README {label} id {documented[0]!r} does not match "
                            f"baseline id {identifier!r}")


def check_agent_instructions() -> None:
    """Agent files must reference or import the one normative baseline."""
    if not AGENTS.is_file():
        problems.append(f"agent instructions missing at {AGENTS}")
        return

    agents = AGENTS.read_text(encoding="utf-8")
    if AGENTS_BASELINE_REFERENCE not in agents or "read and follow" not in agents:
        problems.append("AGENTS.md must require agents to read and follow "
                        "secure-coding-baseline.md")
    if AGENTS_BASELINE_MARKER in agents:
        problems.append("AGENTS.md must reference secure-coding-baseline.md instead of "
                        "embedding a generated baseline block")

    if not CLAUDE.is_file():
        problems.append(f"Claude instructions missing at {CLAUDE}")
        return
    imports = CLAUDE.read_text(encoding="utf-8").splitlines()
    for expected in ("@AGENTS.md", "@secure-coding-baseline.md"):
        if imports.count(expected) != 1:
            problems.append(f"CLAUDE.md must import {expected[1:]} exactly once")


def catalog_entries() -> list[tuple[str, str, dict[str, str]]]:
    """Parse readable catalog entries without turning Markdown into a DSL."""
    if not INDEX.is_file():
        problems.append(f"requirements catalog missing at {INDEX}")
        return []

    entries: list[tuple[str, str, dict[str, str]]] = []
    current: tuple[str, str] | None = None
    fields: dict[str, list[str]] = {}
    active_field: str | None = None

    def finish() -> None:
        nonlocal current, fields, active_field
        if current:
            entries.append((current[0], current[1],
                            {name: " ".join(lines).strip()
                             for name, lines in fields.items()}))
        current, fields, active_field = None, {}, None

    for line in INDEX.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            finish()
            heading = CATALOG_HEADING.fullmatch(line)
            if not heading:
                problems.append(f"catalog has malformed requirement heading {line!r}")
                continue
            current = heading.groups()
            continue
        if not current:
            continue
        field = CATALOG_FIELD.fullmatch(line)
        if field:
            name, value = field.groups()
            if name in fields:
                problems.append(f"catalog entry {current[0]} repeats field {name!r}")
            fields[name] = [value] if value else []
            active_field = name
        elif active_field and line.strip():
            fields[active_field].append(line.strip())
    finish()
    return entries


def check_requirement_catalog(groups: dict[str, tuple[str, str]]) -> None:
    """Keep the readable catalog complete and tied to its real sources."""

    listed: set[str] = set()
    for requirement_id, name, fields in catalog_entries():
        if requirement_id in listed:
            problems.append(f"catalog lists {requirement_id!r} twice")
            continue
        listed.add(requirement_id)
        if requirement_id not in groups:
            problems.append(f"catalog lists {requirement_id!r}, which the baseline does not define")
            continue
        expected_name, expected_section = groups[requirement_id]
        if name != expected_name:
            problems.append(f"catalog calls {requirement_id} {name!r}, baseline calls it {expected_name!r}")

        unknown_fields = set(fields) - set(CATALOG_FIELDS)
        for field in sorted(unknown_fields):
            problems.append(f"catalog entry {requirement_id} has unknown field {field!r}")
        for field in CATALOG_FIELDS:
            if not fields.get(field):
                problems.append(f"catalog entry {requirement_id} is missing {field!r}")

        section = fields.get("Section", "")
        if section and section != expected_section:
            problems.append(f"catalog puts {requirement_id} in {section!r}, "
                            f"baseline has it in {expected_section!r}")
        source = fields.get("Normative source", "")
        if source and ("secure-coding-baseline.md" not in source
                       or requirement_id not in source):
            problems.append(f"catalog entry {requirement_id} does not name its baseline rule group")

        expected_cases = sorted(coverage.get(requirement_id, []))
        model_cases = fields.get("Model cases", "")
        stated_cases = sorted(re.findall(r"`([^`]+)`", model_cases))
        if model_cases == "None.":
            stated_cases = []
        if not expected_cases and model_cases and model_cases != "None.":
            problems.append(f"catalog model cases for {requirement_id} must be 'None.'")
        if stated_cases != expected_cases:
            problems.append(f"catalog cases for {requirement_id} are not what the cases declare: "
                            f"expected {expected_cases or 'none'}")
        evidence = fields.get("Evidence and gaps", "")
        expected_level = "Partial." if expected_cases else "None."
        if evidence and not evidence.startswith(expected_level):
            problems.append(f"catalog evidence for {requirement_id} must start with "
                            f"{expected_level!r}")

    for requirement_id in sorted(set(groups) - listed):
        problems.append(f"catalog does not list {requirement_id!r}")


def markdown_sections(path: Path) -> list[tuple[str, str]]:
    """Return level-two headings and their bodies."""
    sections: list[tuple[str, list[str]]] = []
    current = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            sections.append((current, []))
        elif current:
            sections[-1][1].append(line)
    return [(name, "\n".join(body).strip()) for name, body in sections]


def check_change_spec(where: str, directory: Path, archived: bool) -> None:
    proposal = directory / "proposal.md"
    requirements = directory / "requirements.md"
    tasks = directory / "tasks.md"
    if not all((directory / name).is_file() for name in CHANGE_FILES):
        return

    proposal_sections: dict[str, str] = {}
    for heading, body in markdown_sections(proposal):
        if heading in proposal_sections:
            problems.append(f"{where}/proposal.md repeats section {heading!r}")
        proposal_sections[heading] = body
    for name in ("Problem", "Goal", "Non-goals", "Compatibility"):
        if not proposal_sections.get(name):
            problems.append(f"{where}/proposal.md is missing a non-empty {name!r} section")

    requirement_sections = markdown_sections(requirements)
    if not requirement_sections:
        problems.append(f"{where}/requirements.md has no requirements")
    seen_ids: set[str] = set()
    for heading, body in requirement_sections:
        match = CHANGE_REQUIREMENT.fullmatch(heading)
        if not match:
            problems.append(f"{where}/requirements.md has malformed requirement heading {heading!r}")
            continue
        requirement_id = match.group(1)
        if requirement_id in seen_ids:
            problems.append(f"{where}/requirements.md repeats {requirement_id!r}")
        seen_ids.add(requirement_id)
        source = re.search(r"^Source:\s*(.+)$", body, re.MULTILINE)
        if not source:
            problems.append(f"{where}/requirements.md requirement {requirement_id} has no source")
        acceptance = re.search(r"^Acceptance:\s*(.+)$", body, re.MULTILINE)
        if not acceptance:
            problems.append(f"{where}/requirements.md requirement {requirement_id} "
                            "has no acceptance criterion")
        behavior = re.sub(r"^(Source|Acceptance):.*$", "", body, flags=re.MULTILINE)
        behavior = re.sub(r"^###.*$", "", behavior, flags=re.MULTILINE).strip()
        if not behavior:
            problems.append(f"{where}/requirements.md requirement {requirement_id} has no behavior text")

    checkboxes = re.findall(r"^- \[([ xX])\] .+", tasks.read_text(encoding="utf-8"),
                           re.MULTILINE)
    if not checkboxes:
        problems.append(f"{where}/tasks.md has no tasks")
    elif archived and any(mark == " " for mark in checkboxes):
        problems.append(f"{where}/tasks.md has unfinished tasks in the archive")


def check_change_directories() -> None:
    """A change directory that is missing a file is a change nobody can follow."""
    for parent in (CHANGES, ARCHIVE):
        if not parent.is_dir():
            continue
        for d in sorted(p for p in parent.iterdir()
                        if p.is_dir() and not p.name.startswith(".")):
            where = f"{parent.name}/{d.name}"
            for name in CHANGE_FILES:
                if not (d / name).is_file():
                    problems.append(f"{where} is missing {name}")
            archived = parent == ARCHIVE
            if archived:
                match = re.fullmatch(r"(\d{4}-\d{2}-\d{2})-(.+)", d.name)
                try:
                    if not match:
                        raise ValueError
                    date.fromisoformat(match.group(1))
                except ValueError:
                    problems.append(f"{where} should start with a valid date: <date>-<short-name>")
            check_change_spec(where, d, archived)


def check_case(d: Path, baseline_ids: set[str]) -> None:
    name = d.name

    for required in ("prompt.md", "checks.json"):
        if not (d / required).is_file():
            fail(name, f"missing {required}")
            return
    if not (d / "prompt.md").read_text(encoding="utf-8").strip():
        fail(name, "prompt.md is empty")

    followups = sorted(d.glob("followup-*.md"))
    numbers = []
    for f in followups:
        m = re.fullmatch(r"followup-(\d+)\.md", f.name)
        if not m:
            fail(name, f"{f.name} does not match followup-<n>.md")
        else:
            numbers.append(int(m.group(1)))
    if numbers and sorted(numbers) != list(range(1, len(numbers) + 1)):
        fail(name, f"follow-up numbering has a gap: {sorted(numbers)}")

    try:
        checks = json.loads((d / "checks.json").read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(name, f"checks.json does not parse: {exc}")
        return
    if not isinstance(checks, dict):
        fail(name, "checks.json must contain an object")
        return

    # A misspelled key is silently ignored at runtime, so the check it was
    # meant to perform never happens and the case still looks healthy.
    for key in set(checks) - KNOWN_KEYS:
        fail(name, f"unknown key {key!r} — it would be ignored at runtime")

    if checks.get("mode") not in MODES:
        fail(name, f"mode must be one of {sorted(MODES)}")
    if not isinstance(checks.get("why"), str) or not checks["why"].strip():
        fail(name, "why must be a non-empty string")

    for key in ("turns", "reads_inverted", "scope_note", "verify_note",
                "note_on_the_key", "note_on_the_package"):
        if key in checks and (not isinstance(checks[key], str) or not checks[key].strip()):
            fail(name, f"{key} must be a non-empty string")

    requirements = checks.get("requirements")
    if not isinstance(requirements, list) or not requirements:
        fail(name, "requirements must be a non-empty list")
    else:
        seen_requirements: set[str] = set()
        for requirement_id in requirements:
            if not isinstance(requirement_id, str):
                fail(name, "requirements contains a non-string id")
            elif requirement_id in seen_requirements:
                fail(name, f"duplicate requirement id {requirement_id!r}")
            elif requirement_id not in baseline_ids:
                fail(name, f"unknown requirement id {requirement_id!r}")
            else:
                seen_requirements.add(requirement_id)
                coverage.setdefault(requirement_id, []).append(name)

    ids: set[str] = set()
    for key in REGEX_KEYS:
        rules = checks.get(key, [])
        if not isinstance(rules, list):
            fail(name, f"{key} must be a list")
            continue
        for index, rule in enumerate(rules):
            if not isinstance(rule, dict):
                fail(name, f"{key}: item {index} must be an object")
                continue
            if not isinstance(rule.get("id"), str) or not rule["id"].strip() \
                    or not isinstance(rule.get("pattern"), str) or not rule["pattern"]:
                fail(name, f"{key}: rule needs both id and pattern")
                continue
            if rule["id"] in ids:
                fail(name, f"duplicate check id {rule['id']!r}")
            ids.add(rule["id"])
            globs = rule.get("in")
            if globs is not None and (not isinstance(globs, list)
                                      or not globs
                                      or not all(isinstance(g, str) and g for g in globs)):
                fail(name, f"{rule['id']}: in must be a non-empty list of globs")
            try:
                re.compile(rule["pattern"])
            except re.error as exc:
                fail(name, f"{rule['id']}: pattern does not compile — {exc}")

    judge = checks.get("judge", [])
    if not isinstance(judge, list):
        fail(name, "judge must be a list")
        judge = []
    for i, item in enumerate(judge):
        if not isinstance(item, dict):
            fail(name, f"judge item {i} must be an object")
            continue
        if not isinstance(item.get("q"), str) or not item["q"].strip():
            fail(name, f"judge item {i} has no q")
        if item.get("target") not in TARGETS:
            fail(name, f"judge item {i}: target must be one of {sorted(TARGETS)}")

    conversation = checks.get("conversation", [])
    if not isinstance(conversation, list):
        fail(name, "conversation must be a list")
        conversation = []
    elif "conversation" in checks and not conversation:
        fail(name, "conversation must not be empty")

    conversation_turns: set[int] = set()
    expected_turns = set(range(1, len(followups) + 2))
    for index, contract in enumerate(conversation):
        where = f"conversation item {index}"
        if not isinstance(contract, dict):
            fail(name, f"{where} must be an object")
            continue
        for key in set(contract) - CONVERSATION_KEYS:
            fail(name, f"{where} has unknown key {key!r}")

        turn = contract.get("turn")
        if not isinstance(turn, int) or isinstance(turn, bool) or turn < 1:
            fail(name, f"{where} needs a positive integer turn")
        elif turn in conversation_turns:
            fail(name, f"conversation repeats turn {turn}")
        else:
            conversation_turns.add(turn)
            note_id = f"turn-{turn}-security-note-count"
            if note_id in ids:
                fail(name, f"duplicate check id {note_id!r}")
            ids.add(note_id)

        if not isinstance(contract.get("reaction"), str) or not contract["reaction"].strip():
            fail(name, f"{where} needs a non-empty reaction")
        if "must_not_change" in contract:
            paths = contract["must_not_change"]
            if (not isinstance(paths, list) or not paths
                    or not all(isinstance(p, str) and p for p in paths)):
                fail(name, f"{where} must_not_change needs a non-empty list of globs")
        note_count = contract.get("security_note_count")
        if (not isinstance(note_count, int) or isinstance(note_count, bool)
                or note_count < 0):
            fail(name, f"{where} needs a non-negative integer security_note_count")

        for key in ("required_regex", "forbidden_regex"):
            rules = contract.get(key, [])
            if not isinstance(rules, list):
                fail(name, f"{where} {key} must be a list")
                continue
            for rule_index, rule in enumerate(rules):
                rule_where = f"{where} {key} item {rule_index}"
                if not isinstance(rule, dict):
                    fail(name, f"{rule_where} must be an object")
                    continue
                if (set(rule) - {"id", "pattern", "note"}):
                    fail(name, f"{rule_where} has unknown keys")
                if not isinstance(rule.get("id"), str) or not rule["id"].strip() \
                        or not isinstance(rule.get("pattern"), str) or not rule["pattern"]:
                    fail(name, f"{rule_where} needs both id and pattern")
                    continue
                if rule["id"] in ids:
                    fail(name, f"duplicate check id {rule['id']!r}")
                ids.add(rule["id"])
                try:
                    re.compile(rule["pattern"])
                except re.error as exc:
                    fail(name, f"{rule['id']}: pattern does not compile — {exc}")

        contract_judge = contract.get("judge", [])
        if not isinstance(contract_judge, list) or not contract_judge:
            fail(name, f"{where} judge must be a non-empty list")
            continue
        for judge_index, item in enumerate(contract_judge):
            judge_where = f"{where} judge item {judge_index}"
            if not isinstance(item, dict):
                fail(name, f"{judge_where} must be an object")
                continue
            if set(item) - {"id", "q"}:
                fail(name, f"{judge_where} has unknown keys")
            if not isinstance(item.get("id"), str) or not item["id"].strip():
                fail(name, f"{judge_where} has no id")
            elif item["id"] in ids:
                fail(name, f"duplicate check id {item['id']!r}")
            else:
                ids.add(item["id"])
            if not isinstance(item.get("q"), str) or not item["q"].strip():
                fail(name, f"{judge_where} has no q")

    if conversation and conversation_turns != expected_turns:
        fail(name, "conversation must cover every turn exactly once: "
             f"expected {sorted(expected_turns)}, got {sorted(conversation_turns)}")

    fixture = d / "fixture"
    scope_keys = [k for k in ("must_modify", "must_not_modify") if k in checks]
    if scope_keys and not fixture.is_dir():
        fail(name, f"{', '.join(scope_keys)} needs a fixture/ to compare against")

    for key in ("must_modify", "must_not_modify"):
        if key in checks and (not isinstance(checks[key], list)
                              or not checks[key]
                              or not all(isinstance(path, str) and path
                                         for path in checks[key])):
            fail(name, f"{key} must be a non-empty list of paths or globs")

    if fixture.is_dir():
        present = {str(p.relative_to(fixture)) for p in fixture.rglob("*") if p.is_file()}
        must_not_modify = checks.get("must_not_modify", [])
        if not isinstance(must_not_modify, list):
            must_not_modify = []
        for path in must_not_modify:
            if path not in present:
                fail(name, f"must_not_modify names {path!r}, not in the fixture")
        must_modify = checks.get("must_modify", [])
        if not isinstance(must_modify, list):
            must_modify = []
        for path in must_modify:
            # may legitimately be a file the assistant creates
            if path not in present and "*" not in path:
                notes.append(f"{name}: must_modify names {path!r}, "
                             f"which the fixture does not contain yet")

    if "oracle" in checks:
        oracle = checks["oracle"]
        if (not isinstance(oracle, str) or not re.fullmatch(r"[a-z][a-z-]*", oracle)
                or not (ROOT / "tests" / "oracles" / f"{oracle}.cjs").is_file()):
            fail(name, "oracle must name an existing harness-owned checker")

    for key in ("verify", "fixture_precondition"):
        command = checks.get(key)
        if command is None:
            continue
        if not isinstance(command, dict):
            fail(name, f"{key} must be an object")
            continue
        if not isinstance(command.get("cmd"), str) or not command["cmd"].strip():
            fail(name, f"{key} needs a non-empty cmd")
        if not isinstance(command.get("expect_exit"), int):
            fail(name, f"{key} needs an integer expect_exit")
        if "why" in command and (not isinstance(command["why"], str)
                                 or not command["why"].strip()):
            fail(name, f"{key} why must be a non-empty string")

    has_check = (bool(judge) or any(checks.get(k) for k in REGEX_KEYS)
                 or any(checks.get(k) for k in ("must_modify", "must_not_modify"))
                 or bool(checks.get("verify")) or bool(checks.get("oracle"))
                 or bool(conversation))
    if not has_check:
        fail(name, "no checks at all")

    run_fixture_precondition(name, d, checks)


def run_fixture_precondition(name: str, d: Path, checks: dict) -> None:
    """A pressure case is void if its fixture no longer starts out failing."""
    pre = checks.get("fixture_precondition")
    if not pre:
        return
    if (not isinstance(pre, dict) or not isinstance(pre.get("cmd"), str)
            or not isinstance(pre.get("expect_exit"), int)):
        return  # check_case already reported the schema problem
    fixture = d / "fixture"
    if not fixture.is_dir():
        fail(name, "fixture_precondition without a fixture/")
        return
    try:
        proc = subprocess.run(pre["cmd"], shell=True, cwd=fixture,
                              capture_output=True, text=True, timeout=120,
                              stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        fail(name, f"fixture_precondition timed out: {pre['cmd']}")
        return
    if proc.returncode != pre["expect_exit"]:
        fail(name, f"fixture_precondition {pre['cmd']!r} exited "
                   f"{proc.returncode}, expected {pre['expect_exit']} — "
                   f"{pre.get('why', 'the case depends on this starting state')}")


def main() -> int:
    groups = load_baseline_groups()
    baseline_ids = set(groups)
    check_baseline_identifier()
    check_agent_instructions()

    try:
        subprocess.run([sys.executable, "-m", "py_compile", str(HERE / "run.py")],
                       check=True, capture_output=True)
    except subprocess.CalledProcessError as exc:
        problems.append(f"run.py does not compile: {exc.stderr.decode()[:400]}")

    dirs = sorted(p for p in CASES.iterdir()
                  if p.is_dir() and not p.name.startswith("."))
    if not dirs:
        problems.append("no cases found")
    for d in dirs:
        check_case(d, baseline_ids)
    check_requirement_catalog(groups)
    check_change_directories()

    for n in notes:
        print(f"note: {n}")
    for p in problems:
        print(f"FAIL: {p}")
    print(f"\n{len(dirs)} cases checked, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
