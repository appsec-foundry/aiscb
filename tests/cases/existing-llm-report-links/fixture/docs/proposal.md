# Verify AuthZ at standard depth

Status: approved by the maintainer on 2026-10-22.

## Change

Standard assessments run the AuthZ verification after the survey, as thorough
assessments already do. The verification table shows each verification finding
together with the survey findings it confirms, for example `V-001 (as T-003)`.

## Risks and side effects

- Cost: about nine additional model calls per standard run on a mid-sized
  repository.
- Data sent to the model provider: each verification job sends excerpts of
  source files the survey already sends, to the same configured provider. No
  new provider, host, or data category is involved.

## Decision

The maintainer accepted the additional cost and the larger volume of excerpts
sent to the configured provider.
