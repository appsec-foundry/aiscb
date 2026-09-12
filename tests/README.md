# Testing the baseline

Run `make check` first. It checks the repository, fixtures, and test code without
calling a model. CI runs this target on every push and pull request.

For assistant behavior, choose the smallest run that answers your question:

```bash
make test-fast                         # four small baseline cases, no judge
make test-organization                 # overlay and lazy loading, no judge
make test-rule RULE=aiscb-REPORT-001    # compare both arms for one rule group
make test-quick                        # four cases, both arms, three repeats
make test                              # all baseline cases
```

Model targets run `make check` before starting. They require the selected
assistant CLI on `PATH`. The default is Claude; the existing comparison suite
also supports Codex. A judge is a separate model call that assesses an answer
or code where a fixed check is insufficient.

## Cost and scope

| Target | Agent turns | Judge calls, at most | Preflight calls |
| --- | ---: | ---: | ---: |
| `make check` | 0 | 0 | 0 |
| `make test-fast` | 6 | 0 | 1 |
| `make test-organization` | 4 | 0 | 1 |
| `make test-confirmation` | 9 | 9 | 2 |
| `make test-smoke` | 2 | 6 | 2 |
| `make test-quick` | 24 | 72 | 2 |
| `make test` | 162 | 324 | 2 |

These are the default matrices. An agent turn can make several model requests,
so the counts are not token or dollar limits. `test-fast` and `test-organization`
allow 180 seconds per agent turn. Their tasks use small local fixtures and need
no package installation. Other targets retain their existing timeouts.

Inspect the matrix without starting an assistant:

```bash
make test-fast ARGS=--dry-run
make test-organization ARGS=--dry-run
python3 tests/design_confirmation.py --dry-run
make dry-run ARGS="--requirements aiscb-REPORT-001"
```

`test-fast` covers an owner-bound endpoint, CSRF under repeated pressure,
instructions embedded in an issue, and a focused fixture repair. It runs once
with the baseline. A failure warrants inspection; a pass does not establish
reliable baseline compliance. Semantic checks are skipped and reported as such.

Use `test-rule` or `test-quick` to compare the same prompts with and without the
baseline. Three repeats are the default. Repeat an affected case when a result
is unclear; decide the cases and repeat count in advance when reporting an
effect. Do not mix selectively repeated failures into that comparison.

`test-smoke` checks that the whole runner works. `test-all` runs the full suite
with both Claude and Codex. Neither is needed for routine edits.

## Overlay and lazy loading

`test-organization` runs four short tasks with the baseline and a test overlay:

- **Overlay:** a query must respect both user and tenant identity.
- **Matching work:** load the access pack and its blueprint before editing,
  then use the approved group value.
- **Unrelated work:** fix text normalization without loading the access pack.
- **Missing policy:** leave access denied and complete the independent text fix.

The loader records which artifact was requested and the source hash at that
moment. Fixed checks inspect these records and execute the resulting functions.
The blueprint uses a fresh synthetic group ID, so a remembered value cannot
satisfy the test. No judge is needed.

This tests the routing contract described in
[Adapting the baseline in an organization](../docs/adapting-in-an-organization.md).
It uses a named local loader, not native skill discovery or an HTTPS gateway.
It does not test context compaction, changing scope, multiple matching packs,
or live release changes. Those need separate integration cases.

```bash
make test-organization ARGS="--cases matching,missing"
make test-organization ARGS="--tool codex"
```

Results and fixtures remain in the temporary directory printed at completion.
A failed or incomplete case makes this target return a nonzero exit status.
The baseline requirement catalog describes the main suite; these organization
integration cases are separate and make no claim of a baseline effect.

## Design confirmation dialogs

`make test-confirmation` checks `aiscb-OM-005` and `aiscb-ATTR-001` against
the three-digit email-login planning prompt. It offers Claude's native
`AskUserQuestion` through a test permission host, then captures the actual
tool call and question. A separate run removes that tool to check text fallback.
The other runs simulate silence, timeout, an unsubmitted preselection, and
explicit acceptance. The host never authorizes another tool.
A sixth case checks a secure automated, persistent-secret design: attribution
belongs in the explanation, no separate aiscb footer is appended, and the
Security note stays reserved for qualifying residual risks.
Three browser HTTP Basic cases use the risk explicitly named in
`aiscb-AUTH-001`: text fallback, an unanswered dialog, and an accepted choice.
They separate risk recognition from the choice of confirmation mechanism.

```bash
make test-confirmation
make test-confirmation ARGS="--cases unavailable,timeout --judge-votes 3"
make test-confirmation ARGS=--isolated-profile
make test-confirmation ARGS="--isolated-profile --cases basic-unavailable,basic-silence,basic-accepted"
```

The adapter uses the CLI's bidirectional control protocol as used by the
[official Agent SDK](https://github.com/anthropics/claude-agent-sdk-python/blob/main/src/claude_agent_sdk/_internal/query.py).
The [Claude hooks reference](https://code.claude.com/docs/en/hooks#pretooluse-decision-control)
explains why a non-interactive run needs a permission host to offer this tool.
No additional SDK package is required. CLI versions that do not offer the
expected tool or complete the protocol produce incomplete evidence, not a pass.

Structural checks distinguish a real question-tool request from prose saying
a dialog was used. A model judge assesses the question's risk, alternative,
cost, and whether the assistant waits or proceeds appropriately. Missing or
unclear judge results do not pass. `make check` tests the adapter and checker
against synthetic good and faulty streams without calling a model.

The two preflight runs must show no baseline in the control session and the
current baseline in the baseline session. The nine cases then run once with
the baseline; this is targeted compliance evidence, not a measured baseline
effect. Evidence stays in the printed temporary directory. The test simulates
dialog outcomes: it does not render a terminal UI, measure real timeout timers,
or establish behavior in Codex, Copilot, or other tools.

If a user-level baseline contaminates the control run, `--isolated-profile`
uses a private temporary [CLAUDE_CONFIG_DIR](https://code.claude.com/docs/en/env-vars)
for both test arms and the judge. It links the existing Linux `.credentials.json` for the CLI to read,
without reading its values in the harness or changing user instructions.
The temporary profile is removed after the run, including on errors. This
option requires a file-based CLI login; it does not configure a new login or
support the macOS Keychain. The two baseline preflights still apply.

## What the local checks establish

`make check` validates case metadata, requirement mappings, repository tooling,
and fixture preconditions. It also tests the independent behavioral checkers
against working implementations and deliberate defects: missing ownership or
tenant checks, disabled CSRF, guessed policy values, and blanket denial.

The organization checks verify that policy stays out of the initial overlay,
that the loader rejects missing or altered content, and that scoring catches
late or unnecessary loads. These tests use prepared code, not a model. They
verify the test machinery; only assistant runs show whether an assistant
selects and follows the policy.

The CSRF checks open a temporary listener on `127.0.0.1`. Run the local suite
in an environment that permits loopback networking.

## Running comparisons

The `control` arm carries no project baseline; `baseline` carries the current
`secure-coding-baseline.md`. Preflight asks `baseline?` and stops if these
conditions do not hold. Remove a user-level baseline installation from the tool
under test before comparing arms. Other user-level instructions still affect
both arms. A successful preflight shows visibility, not compliance.

Pass runner options through `ARGS`:

```bash
make test-rule RULE=aiscb-LIMITS-001 ARGS="--repeats 5"
make test-quick ARGS="--judge-votes 1"
make test-fast ARGS="--tools codex"
```

Claude and the judge default to `claude-sonnet-4-6`; Codex uses its tool default.
Pin a model with `--model` for comparisons over time. Use `--judge-model` to
change the judge separately. Codex multi-turn runs must remain sequential
because the current adapter resumes the newest session process-wide.

The judge normally votes up to three times, stopping after two agreeing votes.
It sees replies and final text files, capped at 200 KB of code. It does not see
all tool events. Unclear votes and errors remain unscored.

## Reading results

The main suite writes `report.md` and `runs.json` under `tests/results/`.
Failed or incomplete working directories are retained; `--keep` retains all.
Each round records file hashes, a diff from the starting project, and elapsed
time. This can expose code written before approval or restored in a later
round. It cannot detect an edit undone within the same round.

Report cells show `violations / scored runs`. Both arms near zero may mean the
model already handles the task. Both high means the baseline did not reliably
help. More violations with the baseline may indicate a regression. Incomplete
runs and unscored judgments are listed separately.

The reported p-value is a one-sided Fisher exact test for fewer violations with
the baseline. Even `3/3` versus `0/3` only reaches `p = 0.05`; it does not test
regressions. Read small runs as a reason to investigate, not proof of an effect.

## Adding a case

A main-suite case lives in `tests/cases/<name>/` and contains `prompt.md`,
`checks.json`, and optionally `fixture/` and numbered `followup-1.md` files.
Write an ordinary task prompt without announcing the behavior being tested.

`checks.json` needs a mode, rationale, requirement IDs, and observable checks.
Use patterns for exact code or data, scope checks for protected files, and
`verify` for project tests. A `fixture_precondition` should prove that a repair
case starts broken. The requirement catalog must agree with case mappings;
changes under `specs/` require approval under the repository instructions.

An `oracle` names a checker in `tests/oracles/`, outside the agent's fixture.
It runs after each round and checks both successful use and representative
rejections. Keep project tests as well: passing an independent check does not
show that the assistant added the requested tests.

Use `transcript_forbidden_regex` for artificial markers that must not appear in
captured CLI output or replies. What tool activity is captured depends on the
assistant adapter.

Conversation contracts cover every turn. They can check reply patterns,
security-note counts, and semantic questions. `must_not_change` adds file globs
that must still match the initial state at that turn, including newly created
files. Use it when an implementation must wait for approval.

Test a new checker against a correct solution and a realistic faulty one before
spending model calls on it. Avoid requiring a particular coding style when
several implementations satisfy the task.
