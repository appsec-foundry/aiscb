# Close three common coding gaps

## Problem

A review of the requirements catalog against typical assistant mistakes found
three behaviors the baseline does not name: binding request data to every
model field and returning whole records, comparing secrets with ordinary
equality and acting on unsigned callbacks, and giving CI jobs and containers
more privilege than they need. Each is a frequent finding in generated code
and each has a mechanism the baseline can state in one sentence.

## Goal

Name the three mechanisms inside the rule groups that already own the
concern: field binding under `aiscb-INPUT-001`, constant-time comparison and
webhook verification under `aiscb-MECHANISMS-001`, and CI and container least
privilege under `aiscb-DEFAULTS-001`.

## Non-goals

No new rule group, no new ID, no change to any other rule. Data-protection
requirements for sensitive data beyond secrets stay out of scope; the README
says so. The baseline ID stays `aiscb-0.1.13` until the user approves a new
value.

## Compatibility

Existing rule IDs keep their behavior and gain one sentence each. The baseline
grows by about 90 tokens; the README records the new size and token count.
No test case observes the new sentences yet.
