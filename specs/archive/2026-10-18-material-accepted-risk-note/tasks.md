# Tasks

- [x] Limit the accepted-risk note to material risks, once per scope (NOTE-001–002).
- [x] Update the paired behavioral case and the requirements catalog.
- [x] Regenerate complete output, measure every component, and update documentation.
- [x] Run make check and review the diff.
- [x] Run affected model cases or record why not.
- [x] Archive this specification.

`design-accepted-risk-note` turn 3 now expects no Security note and a judge
rejects restating the unchanged accepted risk. No case yet covers an accepted
risk that fails the materiality test; the catalog records that gap.

`python3 tests/run.py --dry-run --cases design-accepted-risk-note --repeats 1`
selects two runs, eight turns, up to six judge calls, and two preflight probes.
No paid model run was started in this pass; the change's effect on actual
assistants remains unverified.

All thirteen rule-text artifacts were measured with o200k_base. Core: 9,798
bytes / 1,891 tokens; complete: 30,214 bytes / 5,854 tokens. Every module
retains its verified count. Provisional target overruns are 391 and 1,754
tokens. README, the modular handoff table, and the split note were updated.

make check passed. Final diff review confirms only the accepted-risk note
condition in the core changed; module rules, version, published bootstrap
pins, and installations remain unchanged.
