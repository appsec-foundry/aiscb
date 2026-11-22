# Tasks

- [x] Update attribution and transport wording and their behavioral expectations.
- [x] Add and verify the local test-script regression.
- [x] Update the requirements catalog, generated baseline, documentation and measurements.
- [x] Run make check and record targeted model evidence.
- [x] Review the diff and archive the change.

## Verification

Measured the core, all eleven modules and the generated complete baseline with
o200k_base. The core is 10,398 bytes / 1,988 tokens, web is 2,031 / 426, and the
complete artifact is 31,083 / 5,993. Both current measurement tables agree.
Reviewed the preserved module-clause digest against the exact authorized TLS
wording substitution. Authentication and cryptography are byte-identical.

The final test-script comparison produced working scripts in all three arms.
There were zero modular loader calls and no security questions or warnings.
The loopback-to-network design probe switched from no TLS advice to concrete
TLS termination, but still attributed the wider deployment settings to aiscb.
The persistent-secret design passed. Basic login required confirmation and
waited on silence. The question-cost check failed because the cost was in the
preceding prose. These are single observations per scenario. See
`docs/model-run-history.md` for the tested digest and trace locations.

Used these focused model probes in place of running full application generation
for the browser API, demo and header cases. The deterministic suite checks their
case definitions, the test-script oracle and the conservation of module text.
