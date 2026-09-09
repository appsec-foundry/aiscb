# Repository instructions

This repository publishes `secure-coding-baseline.md`. That file is the product:
the rules an assistant follows. Everything else exists to keep it correct.

Before doing any repository work, read and follow
[`secure-coding-baseline.md`](secure-coding-baseline.md). It is the normative
source for assistant behavior: it governs the code you write or change here
exactly as in any project that installs it. It is referenced, not embedded —
open it, or the rules are not in your context at all.

[`README.md`](README.md) explains why the baseline exists and what it covers.
Keep it clear, concise, and written for users: lead with the action and outcome,
avoid implementation details or extended explanations unless they are needed
for safe use, a necessary decision, or troubleshooting, and do not duplicate
the code's internal workflow.

Four limits from it bind every edit to the baseline text:

- It stays compact. Size is a criterion, not only correctness; the README states
  the current budget. After every change to `secure-coding-baseline.md`,
  recompute its file size and GPT token count with the `o200k_base` encoding and
  update both values in `README.md`; never carry the previous measurements
  forward by assumption.
- It stays tool-neutral. The same text ships to Claude Code, Copilot, Codex, and
  anything else that reads an `AGENTS.md`, so no rule may depend on one tool.
- Every rule names a mechanism, not a goal. "Authorize on the server" works;
  "be security-aware" does not.
- It governs how an assistant behaves. It is not a security specification for
  the application being built, and application-specific requirements do not
  belong in it.

Use specification-driven development for every change to
`secure-coding-baseline.md` that could alter how an assistant behaves. Read
[`specs/README.md`](specs/README.md) before changing the baseline—it describes
how baseline changes run here. Changes limited to repository tooling,
configuration, workflow, documentation, the harness, or tests do not get a
change specification when the normative baseline stays unchanged.

Four rules hold no matter how small the baseline change looks:

- Requirements come only from an explicit user request, existing repository
  documentation, or commit history that clearly establishes the behavior. Name
  the source. If none of them settles a question, ask instead of deciding it.
- Normative rule text lives in `secure-coding-baseline.md`. The readable
  requirements catalog and change specifications live under `specs/`; they may
  explain behavior but must not add or change it.
- Nothing under `specs/` is written without the user's explicit approval.
  Propose the entry — the requirement, its source, the file it lands in — and
  wait for an answer. Reading the specs, and pointing out that one is wrong or
  missing, needs no approval. `scripts/spec_guard.py` turns that sentence into a
  permission prompt for identifiable writes from tools that support hooks.
  `.claude/settings.json` registers it for Claude Code when Claude Code is
  launched from the repository root; a session launched below the root does not
  inherit that project hook. A command hook that cannot start or times out
  produces no decision, so the instruction remains authoritative where the
  hook or its normal permission fallback cannot establish the effect.
- Do not change the baseline ID or version unless the user explicitly approves
  the exact new value. A request to change the baseline text is not version
  approval.

Run `make check` after changing the baseline, the specs, test metadata, or the
harness. It calls no model, takes seconds, and also holds this file to its own
contract: `AGENTS.md` must require agents to read and follow the baseline
through the reference above, must not carry a generated copy of it, and
`CLAUDE.md` must import both files exactly once.

The remote quick start is a two-level verified distribution path. `README.md`
pins and hashes `setup.sh`; remote `setup.sh` pins one versioned bundle and
checks the size and SHA-256 of `secure-coding-baseline.md`,
`scripts/install.py`, and `scripts/show_baseline_version.py` before executing
anything from it. Remote setup must install that checked bundle without
substituting content fetched from `main` or a release at runtime.

An installed copy updates itself only through the signed bundle manifest.
`bundle.json` pins the size and SHA-256 of the three bundled files;
`bundle.json.sig` is an OpenSSH signature over it by a release key whose
public half is listed in `ALLOWED_SIGNERS` in `scripts/install.py`.
`install.py --update` fetches both from the latest release tag, verifies the
signature with `ssh-keygen`, requires the manifest version to match the tag and
to exceed the installed version, checks every file against the manifest, and
only then runs the guided setup of the staged bundle. It never installs a file
the manifest does not pin, and a refusal points at the current Quick start.
The private key never enters the repository, CI, or an assistant's context.

Whenever any of the three bundled files changes, run
`make sign-bundle KEY=<release key>` so `bundle.json` and `bundle.json.sig`
describe the committed files, then create a new bundle tag; never move or reuse
a published bundle tag. Recompute every bundle hash in `setup.sh` from the exact
commit the tag names, retain download size limits, and update the tests that
identify the bundle. The release sequence is: sign, commit and check the bundle
files with the manifest and signature, create the bundle tag on that commit,
then change `setup.sh` to the new tag and hashes. A documentation-only commit
does not need a new bundle, and the release tag may point at one as long as its
tree carries the signed manifest for the bundled files it contains.
[`docs/releasing.md`](docs/releasing.md) spells the sequence out with its
commands, the key setup, and the rotation; signing needs the maintainer's key,
so an assistant prepares a release up to that step and reports it.

Every published baseline release must update the complete Quick start command
block in `README.md`, even though its command structure stays the same. It must
name the bootstrap commit for that release and the exact SHA-256 of `setup.sh`
in that commit; `scripts/test_install.py` enforces the hash match. Do not publish
a release while the README command still installs the previous bundle. Because
the bootstrap commit is only known after it is created, commit `setup.sh` first
and update the command block in a follow-up documentation commit. Do not publish
or merge the intermediate state where the README hash and bootstrap commit do
not yet form a working pair.

The model targets are a different matter: they run the cases against real
models. `make test` is 108 agent runs and hours of tokens, `make test-all`
twice that. Run them when the user asks, or for the cases a change affects —
never as a routine check. They are evidence, not a gate. For a narrower
question there is `make test-smoke` (does the harness work at all),
`make test-quick`, and `make test-rule RULE=<id>` for the cases covering one
rule group. They refuse to start unless the control arm carries no baseline
and the baseline arm carries this one, which requires the baseline not to be
installed at user level for the tool under test.
