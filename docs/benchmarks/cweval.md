# CWEval

State as of 2026-09-25 (commit `b165b59`). Usage and security boundaries of
both targets: [`tests/README.md`](../../tests/README.md#optional-cweval-comparison).

The baseline was revised using CWEval findings (`ba885d6`,
`specs/archive/2026-09-24-cweval-module-hardening/`). CWEval scores are
therefore not held-out validation.

## Two targets

| Target | Script | Generation | Scope | State |
|---|---|---|---|---|
| `make test-cweval` | `tests/cweval_runner.py` | Claude or Codex CLI | Python core, 25 tasks, selectable | working |
| `make test-cweval-full` | `tests/cweval_full.py` | direct Chat Completions API, T=0.8, n=100 | all 119 tasks, 6 sets | blocked at reference check |

Until `fd21f96`, `make test-cweval-full` meant
`cweval_runner.py --all-python --repeats 3`. Older logs and tracebacks under
that name come from the CLI runner, not from `cweval_full.py`.

## CLI subset (`make test-cweval`)

Last verified run: `--all-python --repeats 2` with Codex, 100 generations,
no failures, no invalid formats.

| Arm | func-sec@1 |
|---|---|
| control | 74.0 % |
| baseline | 76.0 % |

Evidence: `tests/results/cweval/run-ytia4ntc/` (ignored, local only). Two
repeats are too few to read the +2.0 point difference as an effect.

Pitfall, fixed in `b165b59`: without `--disable plugins`, every `codex exec`
started a git sync of the curated plugin repository (about 200 MB) into the
private `CODEX_HOME`. Runs stalled after a few minutes. After a Codex CLI
update, check `codex features list` for new features that fetch or execute
something and disable them in `assistant_reply()`.

## Full protocol (`make test-cweval-full`)

Every run starts with a reference check in the pinned image and stops before
generation if it fails. Current blocker: the image used locally
(`co1lin/cweval@sha256:2d28261c…`) lacks the Go module cache. Compilation
runs offline with a read-only module cache, so these four Go tasks fail:

| Task | Missing module (from CWEval `go.mod`) |
|---|---|
| `cwe_347_0` | `github.com/golang-jwt/jwt/v5 v5.2.1` |
| `cwe_643_0` | `github.com/ChrisTrenkamp/goxpath v0.0.0-20210404020558-97928f7e12b6` |
| `cwe_760_0` | `golang.org/x/crypto v0.29.0` |
| `cwe_943_0` | `github.com/mattn/go-sqlite3 v1.14.24` |

Indirect: `golang.org/x/net v0.21.0`, `golang.org/x/text v0.20.0`.
Last reference log: `tests/results/cweval/full-zrfm86cp/reference.log`.
Earlier runs also showed C++ failures, which the last run no longer shows.

No paid run has happened yet; there is no `tests/cweval.full.local.json`.

## Next steps

1. Build a derived image that runs `go mod download` for the checkout's
   `go.mod`/`go.sum` into `/home/ubuntu/go/pkg/mod`, and pin it by digest.
   Do not give generated code network access instead (see `tests/README.md`).
2. `make test-cweval-full ARGS="--reference-only --image …"` until all
   reference tests pass.
3. Create `tests/cweval.full.local.json`, run `--dry-run`, and decide on the
   model and token cap.
4. Paid run: 23,800 completions. No resume exists; an interruption loses
   generation progress. Consider building resume before the first full run.

## Local environment

- CWEval checkout: `/tmp/aiscb-cweval-inspect` at
  `e9a2a124c8c53679b6d8d27adfd2f6c40e7576d7`. It is under `/tmp` and may
  disappear; clone again at the same revision.
- `tests/cweval.local.json` (ignored) holds checkout, revision, image digest,
  tool `codex` and the model for the CLI subset.
- Run the targets outside the Claude Code sandbox. They need Docker, network
  for the model, and the Codex login.
