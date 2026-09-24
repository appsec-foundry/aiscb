# Tasks

- [x] Verify the five recommendations against generated code, test definitions, and technical documentation.
- [x] Update the two modules and catalog; keep core and version unchanged.
- [x] Add positive and negative model cases and update the requirements catalog.
- [x] Regenerate complete output and update all byte/token measurements.
- [x] Run make check and review the final diff (passed with loopback access;
  the sandbox prevents the existing CSRF oracle listener).
- [x] Record why affected model cases were not run: this change verifies the
  recommendations against saved outputs and upstream test definitions, and adds
  two cases to the existing semantic-judge suite. No new model comparison was
  run; the unresolved evaluator anomalies make a new aggregate CWEval score
  unsuitable as acceptance evidence. The new cases still require model runs
  to measure adherence; local checks establish structure only.
- [x] Archive this directory.

All cataloged modules and core were remeasured with o200k_base: core stays
8,019 bytes / 1,594 tokens; web is 1,945 / 415; data-handling is 2,706 / 518;
complete output is 28,346 / 5,543 (171 additional tokens). Other modules are
unchanged. README and current measurements in both architecture documents
were updated. New text was shortened after the session-loader capacity check
rejected the first draft; the final artifact fits the existing 28,400-character
limit without changing that control. Discovery adds response serialization;
rule-text measurements exclude discovery and overlays.

The exact-text conservation test retains its full digest assertion, updated
only for the approved WEB-001 and WEBTESTS-001 additions. No behavioral
test was removed, skipped, or weakened. New model cases use the existing
semantic judge; their dry-run matrix is four runs plus at most twelve judge
calls and two preflights at one repeat.
