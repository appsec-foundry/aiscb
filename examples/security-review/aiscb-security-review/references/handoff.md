# Review handoff

- [ ] Fill each field from established requirements and repository evidence.
- [ ] Use paths and identifiers. Do not paste source code or chat history.
- [ ] Exclude secrets, private configuration values and sensitive test output.
- [ ] Take policy identifiers from the trusted installation or reviewed checkout.
      A version label alone does not identify a development snapshot.
- [ ] Do not substitute a newer release or the reviewer's user-level policy.

| Field | Required information |
| --- | --- |
| Task | Requested outcome, requirement sources and observable acceptance criteria |
| Scope | Changed behavior, affected interfaces, existing or new component, exclusions |
| Code | Project and diff paths; base and head revisions |
| Uncommitted work | Base, staged and unstaged changes, relevant untracked files, content digests, and a stable copy or paused edits; otherwise none |
| Context | Relevant callers, access controls, configuration and tests; unresolved assumptions |
| Policy | Baseline ID and installation mode; trusted release digest or reviewed source revision plus catalog digest; core and catalog paths; exact existing loader command |
| Overlays | Organization overlay/module identities and blueprint sources; otherwise none or unknown |
| Modules | Implementer's selection and reasons; reviewer checks selection independently |
| Decisions | Relevant approved design choices with scope and approval source; otherwise none |
| Verification | Checks already run, results and limitations |
| Permissions | Read-only scope; permitted tools and resources; isolated checks the reviewer may run; available host time/turn limits; enforced or **not enforced** |
| Previous review | Re-review only: earlier snapshot and findings; otherwise none |
