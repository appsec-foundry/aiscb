# Review handoff

Fill each field from established requirements and repository evidence.
Use paths and identifiers instead of source copies or chat history.
Exclude secrets, private configuration values and sensitive test output.

| Field | Required information |
| --- | --- |
| Task | Requested outcome, requirement sources and observable acceptance criteria |
| Scope | Changed behavior, affected interfaces, existing or new component, exclusions |
| Code | Project and diff paths; base/head revisions. For uncommitted work: base, staged/unstaged changes and relevant untracked files, with content digests and a stable copy or paused edits |
| Context | Relevant callers, access controls, configuration and tests; unresolved assumptions |
| Policy | Baseline ID and installation mode; trusted release digest or reviewed source revision plus catalog digest; core/catalog paths and exact existing loader command |
| Overlays | Organization overlay/module identities and blueprint sources; otherwise none or unknown |
| Modules | Implementer's selection and reasons; reviewer checks selection independently |
| Decisions | Relevant approved design choices and their scope; otherwise none |
| Verification | Checks already run, results and limitations; authorized isolated checks available to the reviewer |
| Permissions | Read-only scope, permitted tools/resources and available host time/turn limits |

Take policy identifiers from the trusted installation or reviewed checkout.
A version label alone does not identify a development snapshot. Do not substitute
a newer release or the reviewer's user-level policy.

Send the completed record with the full contents of [reviewer.md](reviewer.md).
