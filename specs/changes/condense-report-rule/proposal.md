# Condense the review and report rule

## Problem

`aiscb-REPORT-001` has grown one clause per observed reporting failure. At
614 tokens it is the largest rule group, 12 of 18 model cases depend on it,
and 10 of 29 archived changes adjusted it. SCOPE-003 already asked that the
reporting rules read as general statements; the text has drifted back.

## Goal

Restate the group as a review checklist, one materiality threshold, one rule
for when the note appears, and one rule for what the note contains, in about
three quarters of the current size, without dropping any behavior an archived
change established.

## Non-goals

No change to the note heading, the threshold, or when a note appears. No new
ID and no ID moved. No change to other rule groups.

## Compatibility

Replies keep the same heading and the same decision rules. The harness matches
the heading only. Model cases that grade reporting behavior keep grading the
same behavior; they were not rerun for this wording change.
