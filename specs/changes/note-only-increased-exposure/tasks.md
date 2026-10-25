# Tasks

- [x] Change the Security note trigger and the accepted-risk record (NOTE-003–005).
- [x] Add `existing-llm-combine-step` and update the requirements catalog.
- [x] Regenerate complete output, measure every component, and update documentation.
- [x] Run `make check` and review the diff.
- [ ] Run the affected model cases, or note why not.
- [ ] Archive this directory.

`existing-llm-combine-step` fails its fixture precondition as intended and
passes with a reference implementation kept outside the repository. It
declares OM-005, OM-006, and REPORT-001; the catalog, `tests/README.md`, and
the run count in `AGENTS.md` (144) were updated.

All rule-text artifacts were measured with o200k_base. Core: 10,051 bytes /
1,941 tokens (+50); complete: 30,467 bytes / 5,904 tokens. Modules are
unchanged. Provisional target overruns are 441 and 1,804 tokens. README, the
modular handoff table, and the split note were updated.

make check passed outside the assistant sandbox; inside it, only
`tests/test_routing.py` failed because its own bubblewrap cannot create a
namespace there. The core diff changes only the Security note condition in
REPORT-001 and the accepted-risk record in OM-005.

`python3 tests/run.py --dry-run --cases existing-llm-combine-step,design-accepted-risk-note --repeats 3`
selects 12 agent runs, 30 turns, up to 36 judge calls, and two preflight probes.
