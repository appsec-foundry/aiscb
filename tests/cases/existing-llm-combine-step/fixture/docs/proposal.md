# Combine what each method found

Status: approved by the maintainer on 2026-10-24.

## Change

When a survey finding and a verification finding describe the same issue
(`same_issue` in `register.py`), the register keeps one entry instead of two.
The code sets its IDs (survey first), its methods, the higher severity, and the
union of locations. The merge role writes the combined title, scenario, and
remediation from the two finding texts. The reply must pass `admit_text`; if it
is rejected, the entry keeps the verification finding's texts.

## Risks and side effects

- Cost: one merge call per combined issue.
- Data sent: the merge prompt carries the two finding texts and their
  locations, no source code, to the merge role of the configured provider.
  That role already receives finding titles to group duplicates, and the survey
  and verification roles send source excerpts to the same provider.
- Model output: the finding texts were written by models from repository
  content, so the merge reply can carry manipulated wording into the combined
  title, scenario, and remediation. Severity, locations, IDs, and methods stay
  with the code.

## Decision

The maintainer accepted the merge call, the data it sends, and the risk of
manipulated combined wording.
