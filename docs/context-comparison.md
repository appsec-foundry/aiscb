# Compare complete and modular context

Run six small existing-project tasks with no baseline, complete policy and
modular policy, using the same model and restricted fixture tools:

```bash
make test-context ARGS=--dry-run
make test-context ARGS="--cases documentation,files --repeats 1 --no-judge"
```

Choose cases for a concrete question before making model calls. The example uses
six task runs to inspect irrelevant versus relevant module loading and its token
cost. Use judges only when answer wording is part of the question. Do not run the
full matrix merely because it is available.

The default is Claude Sonnet 4.6, three repeats and randomized order with seed
2309: 54 task runs, 63 user turns, three preflight calls and up to 54 judge calls.
This is an opt-in paid experiment. The source and catalog are snapshotted before
preflight; the experiment does not change the installed user baseline. A separate
smoke run must not be pooled into the comparison.

Tasks cover a documentation typo, label normalization, an owner-bound order
endpoint, an existing session-store adapter, untrusted export filenames, and a
documentation task subsequently expanded to an order endpoint in the same session.
Each task states a concrete contract. This measures routing and workflow overhead
on specified tasks, not whether the baseline supplies every unstated requirement.

## Requirements and execution boundary

Requires the existing Claude CLI login, Python, the installed `tiktoken` package,
and `/usr/bin/bwrap` with working user namespaces. No dependency is downloaded.
Review the local Bubblewrap version and relevant security advisories before use.
The runner first verifies that generated code cannot read an outside sentinel,
write the project, or connect to a host loopback listener.

The isolated CLI profile reuses the existing credential file through the same
mechanism as the confirmation experiment; the runner does not read its contents.
Only the CLI can access that profile. Its model tools are limited to a local
[MCP stdio server](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports)
with three [tools](https://modelcontextprotocol.io/specification/2025-06-18/server/tools):
read a fixture file, replace a fixture source/test file, and run either the
installed policy loader or `python3 -m unittest -q`. Arguments are allow-listed;
there is no shell interpreter. Each server allows at most 80 tool calls.

The tool server runs without network access or credentials. Its config, script
and policy are read-only; file tools cannot access them for writing. Generated
code runs in a second sandbox with a read-only project, private temporary storage,
no network, and CPU, memory, process, output and wall-clock limits. Symlinks in the
project are rejected before sandbox setup. In particular, do not generalize these
fixed mounts to attacker-selected mount layouts: Bubblewrap's
[CVE-2026-87766](https://github.com/containers/bubblewrap/security/advisories/GHSA-pxhw-h44j-8pfx)
affects setup through attacker-controlled symlink destinations. This harness
accepts neither mount arguments nor symlinks from the model.

The installed modular instruction block and verified loader are the production
ones. The constrained command tool is an experimental adapter, so this is not
an unrestricted native-shell client integration test.

## Evidence

`tests/results/context-*/plan.json` records model, matrix, seed and policy hashes.
Raw CLI traces, per-turn acceptance results, tool audits, final fixture files,
`runs.json` and `report.md` stay beside it. The independent acceptance checks are
outside the writable fixture and exercise success and representative malformed,
unauthorized, cross-user, expiry, traversal, symlink and size-boundary inputs.
They do not prove every baseline control. Scope checks cover unrelated fixture
files; the permission boundary separately rejects edits outside the fixture.

Reported token totals sum input, cache-creation input, cache-read input and output
from each CLI result. They therefore include prompts and tool exchanges, not just
policy text; missing usage stays unknown. These totals sum all model requests,
including repeated cached context; they are not peak context-window occupancy. Initial installed policy bytes and
`o200k_base` tokens are separate measurements, including its discovery/loader text.
They are not total session context or the model's native tokenizer count.

The module oracle records task-required modules before the first affected source
write. It cannot observe internal design reasoning. Data-handling and supply-chain
loads can also be justified by executing tools; extra loads are review candidates,
not automatically unnecessary. Complete mode starts with all modules loaded.

Semantic friction checks use one model-judge vote for unnecessary questions,
blockers and unsupported warnings. Keep these judgments separate from executable
checks, inspect disputed traces and report unscored judgments. Retain incomplete
runs in denominators. Three repeats provide exploratory evidence, not a claim of
reliable behavior or statistical superiority. Module splitting, path triggers,
compaction, large repositories and other clients need separate experiments.

## Pilot stopped on 2026-09-23

The initial 54-run campaign was stopped after 22 saved task results; the next
task was interrupted and has only a raw trace. Results remain in
`tests/results/context-comparison-20260923/`. This is an incomplete, unbalanced
pilot, not a completed comparison. Do not infer relative success rates or token
savings from its aggregate results.

The original order fixture did not specify the identity shape or whether repository
rows were already filtered. Its endpoint and scope-change functional results are
therefore unsuitable for quality comparisons. The session fixture also needed an
explicit distinction between missing and malformed stored records. These visible
contracts have since been clarified; existing traces retain their original case
hash and must not be presented as results of the revised fixtures. No replacement
model campaign was run. Loader events remain observations of those original runs;
one scope-change trace omitted both task-required modules, which warrants a focused
routing check rather than another broad matrix.
