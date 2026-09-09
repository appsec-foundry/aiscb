#!/usr/bin/env python3
"""Test the example gate's rules, payload handling, and hook response."""

import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GATE = HERE / "gate.py"
BASELINE = HERE.parent.parent / "secure-coding-baseline.md"
SETTINGS = HERE / "settings.example.json"

sys.path.insert(0, str(HERE))
import gate  # noqa: E402

failures: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        failures.append(message)


def write_payload(content: str, path: str = "/srv/app/service.py") -> dict:
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": path, "content": content},
    }


def denies(content: str, path: str = "/srv/app/service.py") -> dict | None:
    return gate.decide(write_payload(content, path))


def rejects_invalid(payload: dict) -> bool:
    try:
        gate.decide(payload)
    except gate.HookInputError:
        return True
    return False


# (rule title fragment, denied sample, allowed sample)
SAMPLES: tuple[tuple[str, str, str], ...] = (
    (
        "TLS certificate verification",
        "resp = requests.get(url, verify=False)",
        "resp = requests.get(url, verify=True, timeout=10)",
    ),
    (
        "TLS certificate verification",
        "const agent = new https.Agent({ rejectUnauthorized: false })",
        "const agent = new https.Agent({ ca: readFileSync(caPath) })",
    ),
    (
        "TLS certificate verification",
        "tls.Config{InsecureSkipVerify: true}",
        "tls.Config{MinVersion: tls.VersionTLS12}",
    ),
    (
        "TLS certificate verification",
        "curl --insecure https://example.com",
        "curl --cacert company-ca.pem https://example.com",
    ),
    (
        "TLS certificate verification",
        "curl -sSk https://example.com",
        "curl -sS https://example.com",
    ),
    (
        "off switch",
        'SKIP_AUTH = os.environ.get("SKIP_AUTH") == "1"',
        "AUTH_ENABLED = True",
    ),
    (
        "off switch",
        "app.config['WTF_CSRF_ENABLED'] = False",
        "app.config['WTF_CSRF_ENABLED'] = True",
    ),
    (
        "off switch",
        "CSRF_ENABLED = False",
        "if not request.user.is_authenticated: raise PermissionDenied",
    ),
)

for title_fragment, denied, allowed in SAMPLES:
    response = denies(denied)
    if response is None:
        failures.append(f"not denied: {denied!r}")
    else:
        reason = response["hookSpecificOutput"]["permissionDecisionReason"]
        check(
            title_fragment.lower() in reason.lower(),
            f"deny reason does not mention {title_fragment!r}: {reason!r}",
        )
    check(denies(allowed) is None, f"false positive: {allowed!r}")

check(denies("NO_AUTHORS = 0") is None, "off-switch rule matches a longer name")

# Supported payloads scan only text being added.
check(
    gate.decide({
        "hook_event_name": "PreToolUse",
        "tool_name": "Edit",
        "tool_input": {
            "file_path": "/srv/app/x.py",
            "new_string": "requests.get(u, verify=False)",
        },
    }) is not None,
    "Edit payloads are not scanned",
)
check(
    gate.decide({
        "hook_event_name": "PreToolUse",
        "tool_name": "Edit",
        "tool_input": {
            "file_path": "/srv/app/x.py",
            "old_string": "requests.get(u, verify=False)",
            "new_string": "requests.get(u, timeout=5)",
        },
    }) is None,
    "old_string is scanned even though the edit removes the pattern",
)
check(
    gate.decide({
        "hook_event_name": "PreToolUse",
        "tool_name": "NotebookEdit",
        "tool_input": {
            "notebook_path": "/srv/app/x.ipynb",
            "new_source": "requests.get(u, verify=False)",
        },
    }) is not None,
    "NotebookEdit payloads are not scanned",
)
check(
    gate.decide({
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": "curl -k https://example.com"},
    }) is None,
    "the gate decides on tools outside its documented scope",
)
check(rejects_invalid({}), "an empty payload should be rejected")
check(
    rejects_invalid({
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": 5},
    }),
    "a malformed editing payload should be rejected",
)
check(
    denies("verify=False", path=str(HERE / "rules.py")) is None,
    "the example blocks maintenance of its own rule file",
)

# Rule references stay tied to the normative baseline.
groups = set(
    re.findall(
        r"\*\*\[(aiscb-[A-Z0-9-]+)\]",
        BASELINE.read_text(encoding="utf-8"),
    )
)
check(len(gate.RULES) == 2, "the example should contain exactly two rules")
for rule in gate.RULES:
    check(
        rule.rule_id in groups,
        f"{rule.rule_id} ({rule.title}) is not present in the baseline",
    )

# The sample settings match the supported tools and invoke the script directly.
settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
groups_config = settings["hooks"]["PreToolUse"]
check(len(groups_config) == 1, "settings should define one PreToolUse group")
if len(groups_config) == 1:
    group = groups_config[0]
    check(
        group.get("matcher") == "Write|Edit|NotebookEdit",
        "settings matcher differs from the supported tools",
    )
    handlers = group.get("hooks")
    check(isinstance(handlers, list) and len(handlers) == 1,
          "settings should define one command hook")
    if isinstance(handlers, list) and len(handlers) == 1:
        handler = handlers[0]
        check(handler.get("command") == "python3", "settings use another command")
        check(
            handler.get("args") == [
                "${CLAUDE_PROJECT_DIR}/examples/claude-code-gate/gate.py"
            ],
            "settings point at another script",
        )
        check(handler.get("timeout") == 10, "settings should bound hook runtime")

# Exercise the command hook contract through a real process.
proc = subprocess.run(
    [sys.executable, str(GATE)],
    input=json.dumps(write_payload("requests.get(u, verify=False)")),
    capture_output=True,
    text=True,
    timeout=30,
)
check(proc.returncode == 0, f"denied edit exited with {proc.returncode}")
try:
    decision = json.loads(proc.stdout)["hookSpecificOutput"]
    check(decision["hookEventName"] == "PreToolUse", "wrong hookEventName")
    check(decision["permissionDecision"] == "deny", "missing deny decision")
    check(bool(decision["permissionDecisionReason"]), "deny reason is empty")
except (json.JSONDecodeError, KeyError, TypeError) as exc:
    failures.append(f"stdout is not a usable hook decision: {exc}: {proc.stdout!r}")

proc = subprocess.run(
    [sys.executable, str(GATE)],
    input=json.dumps(write_payload("requests.get(u, timeout=5)")),
    capture_output=True,
    text=True,
    timeout=30,
)
check(proc.returncode == 0, "allowed edit should exit 0")
check(proc.stdout.strip() == "", f"allowed edit printed output: {proc.stdout!r}")

check(gate.added_text("Bash", {"command": "curl -k https://example.com"}) is None,
      "added_text should ignore tools it does not support")
check(rejects_invalid({"hook_event_name": "PreToolUse", "tool_name": 5,
                       "tool_input": {}}),
      "a non-string tool name should be rejected")
check(rejects_invalid({"hook_event_name": "PreToolUse", "tool_name": "Write",
                       "tool_input": "not an object"}),
      "a non-object tool input should be rejected")
check(rejects_invalid({"hook_event_name": "SessionStart", "tool_name": "Write",
                       "tool_input": {}}),
      "another hook event should be rejected")

# A gate that fails open on bad input is worse than no gate, so every refusal
# below must block the edit rather than let it through.
BLOCKING_INPUT = [
    ("malformed JSON", "{not json"),
    ("a payload that is not an object", "[]"),
    ("a payload for another hook event",
     json.dumps({"hook_event_name": "SessionStart", "tool_name": "Write",
                 "tool_input": {}})),
    ("an editing payload without its text",
     json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Write",
                 "tool_input": {"file_path": "/srv/app/x.py"}})),
]

for label, payload in BLOCKING_INPUT:
    proc = subprocess.run(
        [sys.executable, str(GATE)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=30,
    )
    check(proc.returncode == 2, f"{label} should block the edit")
    check(proc.stdout.strip() == "", f"{label} should not print a decision")
    check(bool(proc.stderr.strip()), f"{label} should be reported on stderr")

if failures:
    print(f"gate: {len(failures)} problem(s)")
    for problem in failures:
        print(f"  - {problem}")
    sys.exit(1)

print(f"gate: ok ({len(gate.RULES)} rules, {len(SAMPLES)} samples)")
