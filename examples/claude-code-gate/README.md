# Claude Code gate example

This example uses a Claude Code `PreToolUse` hook to block two narrowly defined
security regressions before an edit is written. The patterns are kept in
[`rules.py`](rules.py); [`gate.py`](gate.py) handles the hook protocol.

It is an optional extension for teams that want to go beyond behavioral
instructions with a small deterministic check. It is not an implementation of
the baseline and does not inspect existing code, shell commands, or the
surrounding application.

## Checks

| Baseline rule | Blocked edit |
| --- | --- |
| [`aiscb-PRESERVE-001`](../../secure-coding-baseline.md#non-negotiable) | Disabling TLS certificate verification, for example `verify=False`, `rejectUnauthorized: false`, or `curl -k` |
| [`aiscb-PRESERVE-001`](../../secure-coding-baseline.md#non-negotiable) | Adding a switch that disables authentication, authorization, or CSRF protection, for example `SKIP_AUTH` or `WTF_CSRF_ENABLED = False` |

Only text added through Claude Code's `Write`, `Edit`, and `NotebookEdit` tools
is checked. The example directory itself is excluded so its patterns and tests
can be maintained.

## Try it

Run the local tests:

```bash
python3 examples/claude-code-gate/test_gate.py
```

Then merge [`settings.example.json`](settings.example.json) into the project's
`.claude/settings.json` and restart Claude Code. An edit containing
`requests.get(url, verify=False)` should be denied with the matching baseline
rule ID.

## Limits

The gate uses regular expressions and deliberately covers only these two
constructs, in the spellings listed in `rules.py`. It matches text, not
meaning: a comment or test that quotes `verify=False` is blocked, while a
configuration key the rules do not list, such as `verify: false` in YAML,
passes. File changes made through `Bash`, changes to the gate itself, and
existing code are outside its scope. Malformed hook input is blocked, but
Claude Code treats a hook that cannot start or times out as non-blocking; test
the installation after changing it. Use review, tests, SAST, dependency and
secret scanning, and CI controls for wider coverage.
