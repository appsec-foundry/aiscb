# Tasks

- [x] Add the material-intervention threshold and clarify attribution (MAT-001–003).
- [x] Add paired behavioral cases and update the requirements catalog.
- [x] Regenerate complete output, measure every component, and update documentation.
- [x] Run make check and review the diff.
- [x] Run affected model cases or record why not.
- [x] Archive this specification.

The new diagnostic fixture starts with the two intended display failures and
passing admission tests. In temporary copies, its five tests accept a correct
implementation and reject generic-only output, a raw-exception leak, and an
admission bypass. Semantic judges separately check redundant mechanisms and
commentary; deterministic fixture checks cannot establish those behaviors.

`python3 tests/run.py --dry-run --requirements aiscb-OM-006 --repeats 1`
selects the new handoff and diagnostic cases plus existing greenfield design
confirmation: six runs, twelve turns, up to eighteen judge calls, and two
preflight probes. No paid model runs were started in this implementation pass;
their stochastic comparison and session isolation are a separate evaluation.
The new threshold's effect on actual assistants remains unverified.

All thirteen rule-text artifacts were measured with o200k_base and compared
against README and the modular handoff table. Core: 9,638 bytes / 1,860 tokens;
complete: 30,054 bytes / 5,823 tokens. Every module retains its verified count.
Provisional target overruns are 360 and 1,723 tokens. Discovery, loading
instructions, and overlays remain additional context. The full default model
matrix is now 132 runs / 210 turns, at most 396 judge calls and two preflights.

The initial outer-sandbox make check failed the existing local HTTP oracle.
The rerun outside that sandbox passes the HTTP test and retains the harness's
own isolation; no security control or test was bypassed to accommodate it.

The complete make check rerun passed, including 22 case definitions, the
existing approval and routing tests, packaging, installer, and session checks.
Final diff review confirms only the approved core behavior and attribution
changed; module rules, version, published bootstrap pins, and installations
remain unchanged.
